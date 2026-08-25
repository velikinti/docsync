"""Tests for SpaceRouter — prefix matching, normalisation, edge cases."""

from __future__ import annotations

import pytest

from docsync.space_router import SpaceRouter


class TestEmptyRouter:
    def test_is_empty_true(self):
        router = SpaceRouter({})
        assert router.is_empty is True

    def test_resolve_returns_none(self):
        router = SpaceRouter({})
        assert router.resolve("docs/intro.md") is None

    def test_all_spaces_empty(self):
        router = SpaceRouter({})
        assert router.all_spaces == []


class TestBasicRouting:
    def test_resolve_exact_prefix(self):
        router = SpaceRouter({"docs/": "DOCS"})
        assert router.resolve("docs/intro.md") == "DOCS"

    def test_resolve_nested_path(self):
        router = SpaceRouter({"docs/": "DOCS"})
        assert router.resolve("docs/api/reference.md") == "DOCS"

    def test_resolve_no_match_returns_none(self):
        router = SpaceRouter({"docs/": "DOCS"})
        assert router.resolve("engineering/setup.md") is None

    def test_all_spaces_unique_ordered(self):
        router = SpaceRouter({"docs/": "DOCS", "api/": "DOCS", "eng/": "ENG"})
        spaces = router.all_spaces
        assert spaces.count("DOCS") == 1
        assert "ENG" in spaces


class TestKeyNormalisation:
    def test_key_without_trailing_slash_normalised(self):
        router = SpaceRouter({"docs": "DOCS"})
        assert router.resolve("docs/intro.md") == "DOCS"

    def test_key_with_trailing_slash_unchanged(self):
        router = SpaceRouter({"docs/": "DOCS"})
        assert router.resolve("docs/intro.md") == "DOCS"

    def test_both_forms_equivalent(self):
        r1 = SpaceRouter({"docs": "DOCS"})
        r2 = SpaceRouter({"docs/": "DOCS"})
        assert r1.resolve("docs/foo.md") == r2.resolve("docs/foo.md")


class TestLongestPrefixMatching:
    def test_longer_prefix_wins(self):
        router = SpaceRouter({"docs/": "DOCS", "docs/api/": "API"})
        assert router.resolve("docs/api/overview.md") == "API"

    def test_shorter_prefix_matches_non_api_path(self):
        router = SpaceRouter({"docs/": "DOCS", "docs/api/": "API"})
        assert router.resolve("docs/intro.md") == "DOCS"

    def test_three_levels_longest_wins(self):
        router = SpaceRouter({
            "docs/": "DOCS",
            "docs/api/": "API",
            "docs/api/v2/": "APIV2",
        })
        assert router.resolve("docs/api/v2/spec.md") == "APIV2"
        assert router.resolve("docs/api/v1/spec.md") == "API"
        assert router.resolve("docs/guide.md") == "DOCS"

    def test_identical_length_prefixes_different_spaces(self):
        router = SpaceRouter({"aaa/": "AAA", "bbb/": "BBB"})
        assert router.resolve("aaa/doc.md") == "AAA"
        assert router.resolve("bbb/doc.md") == "BBB"


class TestEdgeCases:
    def test_path_with_no_slash_does_not_match_prefix(self):
        router = SpaceRouter({"docs/": "DOCS"})
        assert router.resolve("docs_extra.md") is None

    def test_is_empty_false_when_has_mappings(self):
        router = SpaceRouter({"docs/": "DOCS"})
        assert router.is_empty is False

    def test_multiple_spaces_all_spaces_deduped(self):
        router = SpaceRouter({
            "docs/": "DOCS",
            "api/": "DOCS",
            "eng/": "ENG",
        })
        spaces = router.all_spaces
        assert len([s for s in spaces if s == "DOCS"]) == 1
        assert len(spaces) == 2
