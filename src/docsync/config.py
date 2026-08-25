"""Configuration model for .docsync.yml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class DocSyncConfig(BaseModel):
    confluence_base_url: str = Field(..., description="https://your-org.atlassian.net")
    space_key: Optional[str] = Field(default=None, description="Legacy: single Confluence space key")
    space_keys: Optional[List[str]] = Field(default=None, description="List of Confluence space keys")
    space_mappings: Dict[str, str] = Field(default={}, description="Folder prefix to space key mapping")
    root_page_id: str = Field(..., description="Confluence page ID to use as parent for top-level docs")
    space_root_page_ids: Dict[str, str] = Field(default={}, description="Per-space root page IDs, e.g. {DOCS: '123', ENG: '456'}")
    docs_root: str = Field(default="docs", description="Repo-relative path to the docs folder")
    include_globs: List[str] = Field(default=["**/*.md"], description="Glob patterns to include")
    exclude_globs: List[str] = Field(default=[], description="Glob patterns to exclude")
    batch_size: int = Field(default=10, ge=1, le=50, description="Concurrent GitHub API fetch limit")
    dry_run: bool = Field(default=False, description="Preview mode — no writes to Confluence")

    @field_validator("confluence_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @model_validator(mode="after")
    def coerce_space_key(self) -> "DocSyncConfig":
        if self.space_key and not self.space_keys:
            self.space_keys = [self.space_key]
        if not self.space_key and not self.space_keys and not self.space_mappings:
            raise ValueError(
                "At least one of space_key, space_keys, or space_mappings is required"
            )
        return self

    @model_validator(mode="after")
    def validate_env_vars(self) -> "DocSyncConfig":
        required = ["CONFLUENCE_API_TOKEN", "CONFLUENCE_USER"]
        missing = [v for v in required if not os.environ.get(v)]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        return self

    @property
    def confluence_user(self) -> str:
        return os.environ["CONFLUENCE_USER"]

    @property
    def confluence_token(self) -> str:
        return os.environ["CONFLUENCE_API_TOKEN"]

    def resolve_active_spaces(self, cli_override: Optional[List[str]] = None) -> List[str]:
        """Return space keys to use for this run (CLI > space_keys > space_key > mappings)."""
        if cli_override:
            return list(cli_override)
        if self.space_keys:
            return list(self.space_keys)
        if self.space_key:
            return [self.space_key]
        return list(dict.fromkeys(self.space_mappings.values()))

    @property
    def root_page_ids(self) -> Dict[str, str]:
        """Return effective root_page_id per active space key.
        Uses space_root_page_ids per space; falls back to global root_page_id."""
        result: Dict[str, str] = {}
        for sk in self.resolve_active_spaces():
            result[sk] = self.space_root_page_ids.get(sk) or self.root_page_id or ""
        return result


def load_config(path: Optional[str] = None) -> DocSyncConfig:
    config_path = Path(path) if path else Path(".docsync.yml")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open() as fh:
        data = yaml.safe_load(fh) or {}
    return DocSyncConfig(**data)
