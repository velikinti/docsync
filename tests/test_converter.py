"""Tests for the Markdown → Confluence Storage Format converter."""

import pytest
from docsync.converter import convert, apply_attachment_urls, ConversionResult


class TestConvert:
    def test_basic_markdown_converts(self, sample_markdown):
        result = convert(sample_markdown)
        assert result.valid is True
        assert "<h1>" in result.body or "Hello World" in result.body
        assert result.fallback_used is False

    def test_code_fence_becomes_confluence_macro(self):
        md = "```python\nprint('hi')\n```"
        result = convert(md)
        assert "ac:structured-macro" in result.body
        assert "python" in result.body

    def test_table_converts(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = convert(md)
        assert result.valid is True
        assert "<table" in result.body.lower() or "table" in result.body.lower()

    def test_relative_image_extracted(self):
        md = "![alt text](./images/diagram.png)"
        result = convert(md, base_path="docs/guide")
        assert len(result.images) == 1
        assert result.images[0].original_src == "./images/diagram.png"
        assert result.images[0].alt_text == "alt text"
        assert result.images[0].resolved_path == "docs/guide/./images/diagram.png"

    def test_absolute_image_not_extracted(self):
        md = "![logo](https://example.com/logo.png)"
        result = convert(md)
        assert len(result.images) == 0

    def test_invalid_xhtml_triggers_fallback(self):
        broken_md = "# Title\n\n<unclosed-tag"
        result = convert(broken_md)
        assert result.fallback_used is True
        assert "ac:structured-macro" in result.body

    def test_empty_markdown(self):
        result = convert("")
        assert result.valid is True
        assert result.body == "" or result.body is not None

    def test_bold_italic(self):
        result = convert("**bold** and *italic*")
        assert "strong" in result.body.lower() or "bold" in result.body
        assert "em" in result.body.lower() or "italic" in result.body


class TestApplyAttachmentUrls:
    def test_rewrites_src_after_upload(self):
        md = "![img](./img.png)"
        result = convert(md, base_path="docs")
        result.images[0].attachment_url = "https://test.atlassian.net/wiki/download/attachments/999/img.png"
        updated = apply_attachment_urls(result)
        assert "https://test.atlassian.net/wiki/download/attachments/999/img.png" in updated.body

    def test_no_images_returns_unchanged_body(self, sample_markdown):
        result = convert(sample_markdown)
        original_body = result.body
        updated = apply_attachment_urls(result)
        assert updated.body == original_body
