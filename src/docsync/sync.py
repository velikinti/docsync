"""SyncEngine — orchestrates diff → convert → upsert/archive pipeline."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional

import httpx
import structlog

from docsync.config import DocSyncConfig
from docsync.confluence_client import ConfluenceClient
from docsync.converter import convert, apply_attachment_urls
from docsync.github_client import ChangeType, ChangedFile, GitHubClient
from docsync.hierarchy import HierarchyManager
from docsync.space_router import SpaceRouter

log = structlog.get_logger()


class SyncStatus(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    ARCHIVED = "archived"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class SyncResult:
    path: str
    status: SyncStatus
    space_key: Optional[str] = None
    page_id: Optional[str] = None
    error: Optional[str] = None
    fallback_used: bool = False


@dataclass
class SyncReport:
    results: List[SyncResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def created_count(self) -> int:
        return sum(1 for r in self.results if r.status == SyncStatus.CREATED)

    @property
    def updated_count(self) -> int:
        return sum(1 for r in self.results if r.status == SyncStatus.UPDATED)

    @property
    def archived_count(self) -> int:
        return sum(1 for r in self.results if r.status == SyncStatus.ARCHIVED)

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status == SyncStatus.SKIPPED)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == SyncStatus.FAILED)

    # Backward-compatible aliases
    @property
    def success_count(self) -> int:
        return self.created_count + self.updated_count + self.archived_count

    @property
    def failure_count(self) -> int:
        return self.error_count

    @property
    def skip_count(self) -> int:
        return self.skipped_count

    def summary_dict(self) -> dict:
        """Return aggregate summary as a plain dict suitable for JSON serialisation."""
        return {
            "created": self.created_count,
            "updated": self.updated_count,
            "archived": self.archived_count,
            "skipped": self.skipped_count,
            "errors": self.error_count,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }

    def by_space(self) -> Dict[str, List[SyncResult]]:
        """Group results by space_key; results with no space_key go under ''."""
        grouped: Dict[str, List[SyncResult]] = {}
        for r in self.results:
            key = r.space_key or ""
            grouped.setdefault(key, []).append(r)
        return grouped

    def log_jsonlines(self) -> None:
        for r in self.results:
            print(
                json.dumps({
                    "path": r.path,
                    "status": r.status,
                    "space_key": r.space_key,
                    "page_id": r.page_id,
                    "error": r.error,
                    "fallback_used": r.fallback_used,
                }),
                flush=True,
            )

    def write_github_step_summary(self) -> None:
        summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary_file:
            return
        lines = [
            "## DocSync Results\n",
            f"| Metric | Count |\n|--------|-------|\n",
            f"| Synced | {self.success_count} |\n",
            f"| Skipped | {self.skip_count} |\n",
            f"| Failed | {self.failure_count} |\n\n",
        ]

        by_space = self.by_space()
        unmapped = by_space.pop("", [])

        if by_space:
            for space, results in sorted(by_space.items()):
                lines.append(f"### Space: {space}\n\n")
                lines.append("| File | Status | Page ID | Notes |\n|------|--------|---------|-------|\n")
                for r in results:
                    notes = r.error or ("fallback used" if r.fallback_used else "")
                    lines.append(f"| `{r.path}` | {r.status} | {r.page_id or '-'} | {notes} |\n")
                lines.append("\n")
        else:
            lines.append("### Details\n\n| File | Status | Page ID | Notes |\n|------|--------|---------|-------|\n")
            for r in self.results:
                notes = r.error or ("fallback used" if r.fallback_used else "")
                lines.append(f"| `{r.path}` | {r.status} | {r.page_id or '-'} | {notes} |\n")

        no_mapping = [r for r in unmapped if r.error == "no space_mapping for path"]
        if no_mapping:
            lines.append("\n### Attention: Unmapped Files\n\n")
            lines.append("The following files have no `space_mappings` entry and were skipped:\n\n")
            for r in no_mapping:
                lines.append(f"- `{r.path}`\n")

        with open(summary_file, "a", encoding="utf-8") as fh:
            fh.writelines(lines)


def _matches_globs(path: str, include: List[str], exclude: List[str]) -> bool:
    if not any(fnmatch.fnmatch(path, g) for g in include):
        return False
    if any(fnmatch.fnmatch(path, g) for g in exclude):
        return False
    return True


def _derive_title(path: str, docs_root: str) -> str:
    rel = PurePosixPath(path)
    if docs_root:
        try:
            rel = rel.relative_to(docs_root)
        except ValueError:
            pass
    stem = rel.stem
    return stem.replace("-", " ").replace("_", " ").title()


def _derive_parent_title(path: str, docs_root: str) -> Optional[str]:
    rel = PurePosixPath(path)
    if docs_root:
        try:
            rel = rel.relative_to(docs_root)
        except ValueError:
            pass
    if rel.parent and str(rel.parent) != ".":
        return str(rel.parent).replace("/", " > ").replace("-", " ").replace("_", " ").title()
    return None


class SyncEngine:
    def __init__(
        self,
        config: DocSyncConfig,
        github: GitHubClient,
        confluence: ConfluenceClient,
        space_router: Optional[SpaceRouter] = None,
    ) -> None:
        self._cfg = config
        self._gh = github
        self._cf = confluence
        self._space_router = space_router

    def run(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
        active_spaces: Optional[List[str]] = None,
        continue_on_error: bool = False,
    ) -> SyncReport:
        start = time.perf_counter()
        report = asyncio.run(
            self._run_async(owner, repo, commit_sha, active_spaces, continue_on_error)
        )
        report.elapsed_seconds = time.perf_counter() - start
        return report

    async def _run_async(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
        active_spaces: Optional[List[str]] = None,
        continue_on_error: bool = False,
    ) -> SyncReport:
        report = SyncReport()

        if active_spaces is None:
            active_spaces = self._cfg.resolve_active_spaces()

        router = self._space_router
        use_routing = router is not None and not router.is_empty

        # Pre-flight space access checks (multi-space mode only)
        if use_routing:
            valid_spaces: List[str] = []
            for space in active_spaces:
                access = self._cf.check_space_access(space)
                if not access.exists or not access.can_write:
                    msg = f"Pre-flight failed for space {space!r}: {access.error}"
                    if continue_on_error:
                        log.warning("preflight_skip", space=space, reason=access.error)
                    else:
                        raise RuntimeError(msg)
                else:
                    valid_spaces.append(space)
            active_spaces = valid_spaces

            # Warn about active_spaces that have no mapped files (GAP-04 / DD-13)
            mapped_spaces = set(router.all_spaces)
            for space in active_spaces:
                if space not in mapped_spaces:
                    log.warning(
                        "space_not_in_mappings",
                        space=space,
                        msg="no entries in space_mappings will sync to this space",
                    )

        # Build HierarchyManager per active space; prefetch page cache (T-15)
        hierarchy_map: Dict[str, HierarchyManager] = {}
        root_ids = self._cfg.root_page_ids
        for sk in active_spaces:
            hm = HierarchyManager(
                confluence=self._cf,
                space_key=sk,
                root_page_id=root_ids.get(sk, self._cfg.root_page_id or ""),
                dry_run=self._cfg.dry_run,
                batch_size=self._cfg.batch_size,
            )
            hm.prefetch_page_cache()
            hierarchy_map[sk] = hm

        changed_files = await self._gh.list_changed_files(owner, repo, commit_sha)
        filtered = [
            f for f in changed_files
            if _matches_globs(f.path, self._cfg.include_globs, self._cfg.exclude_globs)
        ]

        if not filtered:
            log.info("no_markdown_changes", commit=commit_sha)
            return report

        # Fetch content for non-deleted files
        to_fetch = [f.path for f in filtered if f.change_type != ChangeType.DELETED]
        contents = await self._gh.fetch_files_batch(owner, repo, to_fetch, commit_sha)

        for changed in filtered:
            if use_routing:
                file_space = router.resolve(changed.path)
                if file_space is None:
                    log.warning("no_space_mapping", path=changed.path)
                    report.results.append(
                        SyncResult(
                            path=changed.path,
                            status=SyncStatus.SKIPPED,
                            error="no space_mapping for path",
                        )
                    )
                    continue
                if file_space not in active_spaces:
                    report.results.append(
                        SyncResult(
                            path=changed.path,
                            status=SyncStatus.SKIPPED,
                            space_key=file_space,
                            error="space not in --spaces filter",
                        )
                    )
                    continue
            else:
                file_space = active_spaces[0] if active_spaces else (self._cfg.space_key or "")

            result = await self._process_file(
                changed, contents, file_space, hierarchy_map.get(file_space)
            )
            report.results.append(result)
            log.info(
                "file_synced",
                path=changed.path,
                status=result.status,
                space_key=result.space_key,
                page_id=result.page_id,
            )

        return report

    async def _process_file(
        self,
        changed: ChangedFile,
        contents: dict[str, bytes],
        space_key: str,
        hierarchy: Optional[HierarchyManager] = None,
    ) -> SyncResult:
        path = changed.path
        try:
            if changed.change_type == ChangeType.DELETED:
                return await self._handle_delete(path, space_key, hierarchy)

            raw = contents.get(path)
            if raw is None:
                return SyncResult(
                    path=path,
                    status=SyncStatus.SKIPPED,
                    space_key=space_key,
                    error="Content unavailable",
                )

            return await self._handle_upsert(path, raw, space_key, hierarchy)

        except Exception as exc:
            log.error("sync_failed", path=path, error=str(exc))
            return SyncResult(
                path=path,
                status=SyncStatus.FAILED,
                space_key=space_key,
                error=str(exc),
            )

    async def _handle_upsert(
        self, path: str, raw: bytes, space_key: str,
        hierarchy: Optional[HierarchyManager] = None,
    ) -> SyncResult:
        if self._cfg.dry_run:
            return SyncResult(
                path=path, status=SyncStatus.SKIPPED, space_key=space_key, error="dry-run"
            )

        md_text = raw.decode("utf-8", errors="replace")
        base_path = str(PurePosixPath(path).parent)
        conversion = convert(md_text, base_path)

        # Resolve parent page ID via hierarchy (falls back to root_page_id if no hierarchy)
        if hierarchy is not None:
            parent_id = await hierarchy.resolve_parent_id(path)
        else:
            parent_id = self._cfg.root_page_id or ""

        # Upload images
        for img in conversion.images:
            if img.resolved_path:
                img_data = await self._fetch_image(img.resolved_path)
                if img_data:
                    attach = self._cf.upload_attachment(
                        page_id="PLACEHOLDER",
                        filename=PurePosixPath(img.original_src).name,
                        data=img_data,
                    )
                    img.attachment_url = attach.download_url

        if conversion.images:
            conversion = apply_attachment_urls(conversion)

        title = _derive_title(path, self._cfg.docs_root)
        existing = self._cf.find_page(space_key, path)

        if existing is None:
            page = self._cf.create_page(
                space_key=space_key,
                parent_id=parent_id,
                title=title,
                body=conversion.body,
                source_path=path,
                path_type="file",
            )
            return SyncResult(
                path=path,
                status=SyncStatus.CREATED,
                space_key=space_key,
                page_id=page.id,
                fallback_used=conversion.fallback_used,
            )
        else:
            page = self._cf.update_page(
                page_id=existing.id,
                version=existing.version,
                title=title,
                body=conversion.body,
            )
            return SyncResult(
                path=path,
                status=SyncStatus.UPDATED,
                space_key=space_key,
                page_id=page.id,
                fallback_used=conversion.fallback_used,
            )

    async def _handle_delete(
        self, path: str, space_key: str,
        hierarchy: Optional[HierarchyManager] = None,
    ) -> SyncResult:
        if self._cfg.dry_run:
            return SyncResult(
                path=path, status=SyncStatus.SKIPPED, space_key=space_key, error="dry-run"
            )

        # Find the page by source_path property (DD-01)
        existing_id = self._cf.find_page_by_property(
            space_key, "docsync:source_path", path
        )
        if not existing_id:
            log.warning("page_not_found_for_delete", path=path, space_key=space_key)
            return SyncResult(
                path=path,
                status=SyncStatus.SKIPPED,
                space_key=space_key,
                error="Page not found in Confluence",
            )

        # Determine file vs directory via stored docsync:path_type property (DD-TC004-02)
        path_type = self._cf.get_page_property(existing_id, "docsync:path_type") or "file"

        if path_type == "directory" and hierarchy is not None:
            archived_ids = await hierarchy.archive_directory(path)
            if not archived_ids:
                return SyncResult(
                    path=path,
                    status=SyncStatus.SKIPPED,
                    space_key=space_key,
                    error="Directory page not found in Confluence",
                )
            return SyncResult(
                path=path,
                status=SyncStatus.ARCHIVED,
                space_key=space_key,
                page_id=archived_ids[0],
            )

        # File delete — archive the single page
        self._cf.archive_page(existing_id)
        return SyncResult(
            path=path, status=SyncStatus.ARCHIVED, space_key=space_key, page_id=existing_id
        )

    async def _fetch_image(self, resolved_path: str) -> Optional[bytes]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(resolved_path)
                resp.raise_for_status()
                return resp.content
        except Exception as exc:
            log.warning("image_fetch_failed", path=resolved_path, error=str(exc))
            return None
