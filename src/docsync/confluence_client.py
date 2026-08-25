"""Confluence REST API v2 client."""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import structlog

log = structlog.get_logger()

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

DOCSYNC_PROPERTY_KEY = "docsync:source_path"
DOCSYNC_PATH_TYPE_KEY = "docsync:path_type"

_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(RuntimeError),
    reraise=True,
)


@dataclass
class Page:
    id: str
    title: str
    version: int
    space_key: str


@dataclass
class AttachmentRef:
    id: str
    filename: str
    download_url: str


@dataclass
class SpaceAccessResult:
    space_key: str
    exists: bool
    can_read: bool
    can_write: bool
    error: Optional[str] = None


class ConfluenceClient:
    def __init__(self, base_url: str, user: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (user, token)

    def _client(self) -> httpx.Client:
        return httpx.Client(
            auth=self._auth,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

    def _sanitised_error(self, exc: httpx.HTTPStatusError) -> RuntimeError:
        return RuntimeError(
            f"Confluence API error {exc.response.status_code}: "
            f"{exc.response.text[:200]}"
        )

    @_RETRY
    def find_page(self, space_key: str, source_path: str) -> Optional[Page]:
        """Find a page by its docsync:source_path property (idempotency key)."""
        url = f"{self._base_url}/wiki/rest/api/content"
        params = {
            "type": "page",
            "spaceKey": space_key,
            "expand": "version,space,metadata.properties",
        }
        with self._client() as client:
            try:
                resp = client.get(url, params=params)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise self._sanitised_error(exc) from exc

        results = resp.json().get("results", [])
        for page in results:
            props = page.get("metadata", {}).get("properties", {}).get("results", [])
            for prop in props:
                if prop.get("key") == DOCSYNC_PROPERTY_KEY and prop.get("value") == source_path:
                    return Page(
                        id=page["id"],
                        title=page["title"],
                        version=page["version"]["number"],
                        space_key=space_key,
                    )
        return None

    @_RETRY
    def create_page(
        self,
        space_key: str,
        parent_id: str,
        title: str,
        body: str,
        source_path: str,
        path_type: str = "file",
    ) -> Page:
        url = f"{self._base_url}/wiki/rest/api/content"
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "ancestors": [{"id": parent_id}],
            "body": {"storage": {"value": body, "representation": "storage"}},
            "metadata": {
                "properties": {
                    DOCSYNC_PROPERTY_KEY: {"value": source_path},
                    DOCSYNC_PATH_TYPE_KEY: {"value": path_type},
                }
            },
        }
        with self._client() as client:
            try:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise self._sanitised_error(exc) from exc

        data = resp.json()
        return Page(
            id=data["id"],
            title=data["title"],
            version=data["version"]["number"],
            space_key=space_key,
        )

    @_RETRY
    def update_page(
        self,
        page_id: str,
        version: int,
        title: str,
        body: str,
    ) -> Page:
        url = f"{self._base_url}/wiki/rest/api/content/{page_id}"
        payload = {
            "type": "page",
            "title": title,
            "version": {"number": version + 1},
            "body": {"storage": {"value": body, "representation": "storage"}},
        }
        with self._client() as client:
            try:
                resp = client.put(url, json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise self._sanitised_error(exc) from exc

        data = resp.json()
        return Page(
            id=data["id"],
            title=data["title"],
            version=data["version"]["number"],
            space_key=data["space"]["key"],
        )

    @_RETRY
    def archive_page(self, page_id: str) -> None:
        """Move a page to Confluence trash (recoverable)."""
        url = f"{self._base_url}/wiki/rest/api/content/{page_id}"
        with self._client() as client:
            try:
                resp = client.delete(url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return  # already gone — idempotent
                raise self._sanitised_error(exc) from exc

    def check_space_access(self, space_key: str) -> SpaceAccessResult:
        """Check that *space_key* exists and is writable with the current credentials."""
        spaces_url = f"{self._base_url}/wiki/api/v2/spaces"
        with self._client() as client:
            try:
                resp = client.get(spaces_url, params={"keys": space_key})
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                return SpaceAccessResult(
                    space_key=space_key,
                    exists=False,
                    can_read=False,
                    can_write=False,
                    error=f"Space {space_key!r}: HTTP {status}",
                )

        results = resp.json().get("results", [])
        if not results:
            return SpaceAccessResult(
                space_key=space_key,
                exists=False,
                can_read=False,
                can_write=False,
                error=f"Space {space_key!r} not found",
            )

        space_id = results[0]["id"]
        perms_url = f"{self._base_url}/wiki/api/v2/spaces/{space_id}/permissions"
        with self._client() as client:
            try:
                resp = client.get(perms_url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                return SpaceAccessResult(
                    space_key=space_key,
                    exists=True,
                    can_read=True,
                    can_write=False,
                    error=f"Space {space_key!r} permissions check failed: HTTP {status}",
                )

        can_write = any(
            p.get("operation", {}).get("operation") == "create"
            for p in resp.json().get("results", [])
        )
        return SpaceAccessResult(
            space_key=space_key,
            exists=True,
            can_read=True,
            can_write=can_write,
        )

    @_RETRY
    def get_child_page_ids(self, page_id: str) -> List[str]:
        """Return immediate child page IDs for the given parent page_id."""
        results: List[str] = []
        url = f"{self._base_url}/wiki/api/v2/pages/{page_id}/children"
        params: dict = {"limit": 250}
        while url:
            with self._client() as client:
                try:
                    resp = client.get(url, params=params)
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise self._sanitised_error(exc) from exc
            data = resp.json()
            results.extend(p["id"] for p in data.get("results", []))
            next_link = data.get("_links", {}).get("next")
            url = f"{self._base_url}{next_link}" if next_link else ""
            params = {}
        return results

    @_RETRY
    def find_page_by_property(
        self,
        space_key: str,
        property_key: str,
        property_value: str,
    ) -> Optional[str]:
        """Return page_id matching a custom property value, or None.
        Paginates all results. If multiple matches, returns the most recently modified.
        Logs WARNING for duplicates (DD-TC004-06)."""
        base_url = f"{self._base_url}/wiki/rest/api/content"
        params: dict = {
            "type": "page",
            "spaceKey": space_key,
            "expand": "version,metadata.properties",
            "limit": 250,
        }
        url: str = base_url
        matches = []
        while url:
            with self._client() as client:
                try:
                    resp = client.get(url, params=params)
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise self._sanitised_error(exc) from exc
            data = resp.json()
            for page in data.get("results", []):
                props = page.get("metadata", {}).get("properties", {}).get("results", [])
                for prop in props:
                    if prop.get("key") == property_key and prop.get("value") == property_value:
                        matches.append(page)
                        break
            # _links.next is a relative URL with all query params included
            next_link = data.get("_links", {}).get("next")
            url = f"{self._base_url}{next_link}" if next_link else ""
            params = {}

        if not matches:
            return None
        if len(matches) > 1:
            log.warning(
                "duplicate_property_pages",
                property_key=property_key,
                property_value=property_value,
                page_ids=[p["id"] for p in matches],
            )
            matches.sort(
                key=lambda p: p.get("version", {}).get("when", ""),
                reverse=True,
            )
        return matches[0]["id"]

    @_RETRY
    def list_all_pages_with_property(
        self,
        space_key: str,
        property_key: str,
    ) -> Dict[str, str]:
        """Return {property_value: page_id} for all pages in space_key that have property_key.
        Used by HierarchyManager.prefetch_page_cache() (DD-TC004-03)."""
        mapping: Dict[str, str] = {}
        url = f"{self._base_url}/wiki/rest/api/content"
        params: dict = {
            "type": "page",
            "spaceKey": space_key,
            "expand": "metadata.properties",
            "limit": 250,
        }
        while url:
            with self._client() as client:
                try:
                    resp = client.get(url, params=params)
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise self._sanitised_error(exc) from exc
            data = resp.json()
            for page in data.get("results", []):
                props = page.get("metadata", {}).get("properties", {}).get("results", [])
                for prop in props:
                    if prop.get("key") == property_key:
                        mapping[prop["value"]] = page["id"]
                        break
            next_url = data.get("_links", {}).get("next")
            url = f"{self._base_url}{next_url}" if next_url else ""
            params = {}
        return mapping

    @_RETRY
    def get_page_property(self, page_id: str, property_key: str) -> Optional[str]:
        """Return the value of a single custom property on a page, or None if not set."""
        url = f"{self._base_url}/wiki/rest/api/content/{page_id}/property/{property_key}"
        with self._client() as client:
            try:
                resp = client.get(url)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise self._sanitised_error(exc) from exc
        return resp.json().get("value")

    def upload_attachment(
        self, page_id: str, filename: str, data: bytes
    ) -> AttachmentRef:
        url = f"{self._base_url}/wiki/rest/api/content/{page_id}/child/attachment"
        mime, _ = mimetypes.guess_type(filename)
        mime = mime or "application/octet-stream"
        with httpx.Client(auth=self._auth, timeout=60) as client:
            try:
                resp = client.post(
                    url,
                    files={"file": (filename, data, mime)},
                    headers={"X-Atlassian-Token": "no-check"},
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise self._sanitised_error(exc) from exc

        result = resp.json()["results"][0]
        download_url = (
            f"{self._base_url}{result['_links']['download']}"
        )
        return AttachmentRef(id=result["id"], filename=filename, download_url=download_url)
