"""GitHub REST API client for listing changed files and fetching content."""

from __future__ import annotations

import asyncio
import base64
import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import httpx


class ChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class ChangedFile:
    path: str
    change_type: ChangeType
    previous_path: Optional[str] = None


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None, batch_size: int = 10) -> None:
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._batch_size = batch_size
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    def _sanitised_headers(self) -> dict:
        """Return headers with auth redacted — safe for logging."""
        h = dict(self._headers)
        if "Authorization" in h:
            h["Authorization"] = "Bearer ***"
        return h

    async def list_changed_files(self, owner: str, repo: str, sha: str) -> List[ChangedFile]:
        """Return all files changed in the commit identified by sha."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{sha}"
        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"GitHub API error {exc.response.status_code} fetching commit {sha}"
                ) from exc
            data = resp.json()

        files = data.get("files", [])
        changed: List[ChangedFile] = []
        for f in files:
            status = f.get("status", "modified")
            change_type = {
                "added": ChangeType.ADDED,
                "modified": ChangeType.MODIFIED,
                "removed": ChangeType.DELETED,
                "renamed": ChangeType.RENAMED,
            }.get(status, ChangeType.MODIFIED)
            changed.append(
                ChangedFile(
                    path=f["filename"],
                    change_type=change_type,
                    previous_path=f.get("previous_filename"),
                )
            )
        return changed

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> bytes:
        """Fetch raw file bytes at path@ref."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}"
        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            try:
                resp = await client.get(url, params={"ref": ref})
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise FileNotFoundError(f"File not found in GitHub: {path}@{ref}") from exc
                raise RuntimeError(
                    f"GitHub API error {exc.response.status_code} fetching {path}"
                ) from exc
            data = resp.json()

        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"])
        return data["content"].encode()

    async def fetch_files_batch(
        self,
        owner: str,
        repo: str,
        paths: List[str],
        ref: str,
    ) -> dict[str, bytes]:
        """Fetch multiple files concurrently, respecting batch_size."""
        semaphore = asyncio.Semaphore(self._batch_size)
        results: dict[str, bytes] = {}

        async def fetch_one(path: str) -> None:
            async with semaphore:
                try:
                    content = await self.get_file_content(owner, repo, path, ref)
                    results[path] = content
                except FileNotFoundError:
                    pass  # skip deleted / missing files

        await asyncio.gather(*[fetch_one(p) for p in paths])
        return results
