"""docsync — Automated GitHub ↔ Confluence documentation sync."""

__version__ = "1.0.0"
__author__ = "Capstone Team"

from docsync.config import DocSyncConfig, load_config
from docsync.confluence_client import SpaceAccessResult
from docsync.hierarchy import HierarchyManager
from docsync.space_router import SpaceRouter
from docsync.sync import SyncEngine, SyncResult

__all__ = [
    "DocSyncConfig",
    "load_config",
    "HierarchyManager",
    "SpaceAccessResult",
    "SpaceRouter",
    "SyncEngine",
    "SyncResult",
]
