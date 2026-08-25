"""HierarchyManager — mirrors GitHub repo directory structure as nested Confluence pages."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Dict, List, Optional

import structlog

from docsync.confluence_client import ConfluenceClient

log = structlog.get_logger()


class HierarchyManager:
    """Resolves, creates, and archives the Confluence page tree mirroring repo directories."""

    def __init__(
        self,
        confluence: ConfluenceClient,
        space_key: str,
        root_page_id: str,
        dry_run: bool = False,
        max_archive_depth: int = 50,
        batch_size: int = 5,
    ) -> None:
        self._confluence = confluence
        self._space_key = space_key
        self._root_page_id = root_page_id
        self._dry_run = dry_run
        self._max_archive_depth = max_archive_depth
        # Cache: dir_path -> confluence_page_id (pre-filled by prefetch_page_cache)
        self._page_id_cache: Dict[str, str] = {}
        # Per-path locks to prevent concurrent duplicate page creation (DD-TC004-01)
        self._creation_locks: Dict[str, asyncio.Lock] = {}
        self._semaphore = asyncio.Semaphore(batch_size)

    def prefetch_page_cache(self) -> None:
        """Synchronously pre-fill _page_id_cache from Confluence (called once per space).
        Fetches all pages with docsync:source_path in one batch (DD-TC004-03)."""
        mapping = self._confluence.list_all_pages_with_property(
            self._space_key, "docsync:source_path"
        )
        self._page_id_cache.update(mapping)
        log.info(
            "hierarchy_cache_prefetched",
            space_key=self._space_key,
            page_count=len(mapping),
        )

    async def resolve_parent_id(self, file_path: str) -> str:
        """Return the Confluence page_id that file_path should be a child of.
        Creates intermediate directory pages as needed (unless dry_run)."""
        parts = PurePosixPath(file_path).parts[:-1]  # drop filename
        if not parts:
            return self._root_page_id

        current_parent = self._root_page_id
        accumulated = ""
        for segment in parts:
            accumulated = f"{accumulated}/{segment}".lstrip("/")
            current_parent = await self._ensure_directory_page(
                accumulated, current_parent, segment
            )
        return current_parent

    async def _ensure_directory_page(
        self,
        dir_path: str,
        parent_page_id: str,
        segment: str,
    ) -> str:
        """Find or create a directory placeholder page; return its page_id.

        Uses asyncio.Lock keyed on dir_path to prevent concurrent duplicate creation (DD-TC004-01).
        Sets docsync:path_type='directory' on the created page (DD-TC004-02).
        In dry_run: returns synthetic ID 'dry-run-{hex8}' (DD-TC004-05).
        """
        if dir_path not in self._creation_locks:
            self._creation_locks[dir_path] = asyncio.Lock()

        async with self._creation_locks[dir_path]:
            if dir_path in self._page_id_cache:
                return self._page_id_cache[dir_path]

            if self._dry_run:
                digest = hashlib.sha256(dir_path.encode()).hexdigest()[:8]
                synthetic = f"dry-run-{digest}"
                self._page_id_cache[dir_path] = synthetic
                log.info("dry_run_intermediate_page", dir_path=dir_path, synthetic_id=synthetic)
                return synthetic

            # Try to find an existing page by source_path property
            page_id = self._confluence.find_page_by_property(
                self._space_key, "docsync:source_path", dir_path
            )
            if not page_id:
                page = self._confluence.create_page(
                    space_key=self._space_key,
                    parent_id=parent_page_id,
                    title=segment,
                    body="",
                    source_path=dir_path,
                    path_type="directory",
                )
                page_id = page.id
                log.info(
                    "created_directory_page",
                    dir_path=dir_path,
                    page_id=page_id,
                    space_key=self._space_key,
                )

            self._page_id_cache[dir_path] = page_id
            return page_id

    async def archive_directory(self, dir_path: str) -> List[str]:
        """Recursively archive all Confluence pages under dir_path.
        Uses semaphore for throttling and respects max_archive_depth (DD-TC004-04).
        Returns list of archived page_ids."""
        root_page_id = self._confluence.find_page_by_property(
            self._space_key, "docsync:source_path", dir_path
        )
        if not root_page_id:
            log.info("no_page_for_directory_skip", dir_path=dir_path)
            return []

        descendants = await self._collect_descendants(root_page_id)
        # Archive in reverse order (deepest first), then root
        all_ids = list(reversed(descendants)) + [root_page_id]

        archived: List[str] = []
        for page_id in all_ids:
            async with self._semaphore:
                if not self._dry_run:
                    self._confluence.archive_page(page_id)
                log.info("archived_page", page_id=page_id, dir_path=dir_path, dry_run=self._dry_run)
                archived.append(page_id)
        return archived

    async def _collect_descendants(self, page_id: str, depth: int = 0) -> List[str]:
        """BFS over Confluence child pages; return all descendant page_ids.
        Stops and logs WARNING when depth >= max_archive_depth (DD-TC004-04)."""
        if depth >= self._max_archive_depth:
            log.warning(
                "archive_depth_limit_reached",
                page_id=page_id,
                depth=depth,
                max_depth=self._max_archive_depth,
            )
            return []

        child_ids = self._confluence.get_child_page_ids(page_id)
        all_descendants: List[str] = list(child_ids)
        for child_id in child_ids:
            all_descendants.extend(
                await self._collect_descendants(child_id, depth + 1)
            )
        return all_descendants
