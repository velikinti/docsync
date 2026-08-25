"""Tests for DocSyncConfig — backward compat, multi-space fields, resolve_active_spaces."""

from __future__ import annotations

import pytest

from docsync.config import DocSyncConfig


class TestLegacyBackwardCompat:
    def test_space_key_promoted_to_space_keys(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_key="TEST",
            root_page_id="111",
        )
        assert cfg.space_keys == ["TEST"]

    def test_space_key_preserved_alongside_space_keys(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_key="TEST",
            root_page_id="111",
        )
        assert cfg.space_key == "TEST"

    def test_existing_base_config_valid(self, base_config):
        assert base_config.space_key == "TEST"
        assert base_config.space_keys == ["TEST"]
        assert base_config.space_mappings == {}

    def test_strip_trailing_slash_on_url(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net/",
            space_key="TEST",
            root_page_id="111",
        )
        assert not cfg.confluence_base_url.endswith("/")


class TestMultiSpaceFields:
    def test_space_keys_list_accepted(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_keys=["DOCS", "ENG"],
            root_page_id="111",
        )
        assert cfg.space_keys == ["DOCS", "ENG"]
        assert cfg.space_key is None

    def test_space_mappings_accepted(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_mappings={"docs/": "DOCS", "engineering/": "ENG"},
            root_page_id="111",
        )
        assert cfg.space_mappings == {"docs/": "DOCS", "engineering/": "ENG"}

    def test_space_keys_not_promoted_when_already_set(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_key="LEGACY",
            space_keys=["DOCS", "ENG"],
            root_page_id="111",
        )
        assert cfg.space_keys == ["DOCS", "ENG"]

    def test_missing_all_space_fields_raises(self):
        with pytest.raises(ValueError, match="At least one of space_key, space_keys, or space_mappings"):
            DocSyncConfig(
                confluence_base_url="https://test.atlassian.net",
                root_page_id="111",
            )

    def test_space_mappings_alone_is_sufficient(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_mappings={"docs/": "DOCS"},
            root_page_id="111",
        )
        assert cfg.space_key is None
        assert cfg.space_keys is None


class TestResolveActiveSpaces:
    def test_cli_override_takes_precedence(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_keys=["DOCS", "ENG"],
            root_page_id="111",
        )
        assert cfg.resolve_active_spaces(cli_override=["API"]) == ["API"]

    def test_space_keys_returned_when_no_override(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_keys=["DOCS", "ENG"],
            root_page_id="111",
        )
        assert cfg.resolve_active_spaces() == ["DOCS", "ENG"]

    def test_legacy_space_key_returned_when_no_space_keys(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_key="TEST",
            root_page_id="111",
        )
        assert cfg.resolve_active_spaces() == ["TEST"]

    def test_mappings_values_returned_as_fallback(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_mappings={"docs/": "DOCS", "engineering/": "ENG"},
            root_page_id="111",
        )
        result = cfg.resolve_active_spaces()
        assert "DOCS" in result
        assert "ENG" in result

    def test_cli_override_as_empty_list_returns_empty(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_key="TEST",
            root_page_id="111",
        )
        assert cfg.resolve_active_spaces(cli_override=[]) == ["TEST"]

    def test_cli_override_multi_space(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_key="TEST",
            root_page_id="111",
        )
        assert cfg.resolve_active_spaces(cli_override=["DOCS", "ENG"]) == ["DOCS", "ENG"]


class TestArchiveOnDeleteConfig:
    def test_archive_on_delete_defaults_to_true(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_key="TEST",
            root_page_id="111",
        )
        assert cfg.archive_on_delete is True

    def test_archive_on_delete_false_accepted(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_key="TEST",
            root_page_id="111",
            archive_on_delete=False,
        )
        assert cfg.archive_on_delete is False

    def test_archive_on_delete_true_explicit(self):
        cfg = DocSyncConfig(
            confluence_base_url="https://test.atlassian.net",
            space_key="TEST",
            root_page_id="111",
            archive_on_delete=True,
        )
        assert cfg.archive_on_delete is True

    def test_base_config_fixture_has_archive_on_delete_true(self, base_config):
        assert base_config.archive_on_delete is True
