"""SpaceRouter — resolves repository file paths to Confluence space keys."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


class SpaceRouter:
    """Longest-prefix router mapping repository folder prefixes to space keys.

    Mapping keys are normalised to a trailing slash on construction (DD-12).
    """

    def __init__(self, mappings: Dict[str, str]) -> None:
        normalised: Dict[str, str] = {
            (k if k.endswith("/") else k + "/"): v
            for k, v in mappings.items()
        }
        self._mappings: List[Tuple[str, str]] = sorted(
            normalised.items(), key=lambda kv: len(kv[0]), reverse=True
        )

    @property
    def is_empty(self) -> bool:
        return len(self._mappings) == 0

    @property
    def all_spaces(self) -> List[str]:
        """Unique space keys referenced by this router, in definition order."""
        return list(dict.fromkeys(v for _, v in self._mappings))

    def resolve(self, path: str) -> Optional[str]:
        """Return the space key for *path*, or None if no prefix matches."""
        for prefix, space_key in self._mappings:
            if path.startswith(prefix):
                return space_key
        return None
