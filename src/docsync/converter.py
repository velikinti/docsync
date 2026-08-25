"""Markdown to Confluence Storage Format converter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

import markdown2
from lxml import etree as lxml_etree


@dataclass
class ImageRef:
    original_src: str
    alt_text: str
    resolved_path: Optional[str] = None
    attachment_url: Optional[str] = None


@dataclass
class ConversionResult:
    body: str
    valid: bool
    images: List[ImageRef] = field(default_factory=list)
    fallback_used: bool = False


_IMG_PATTERN = re.compile(r'<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"[^>]*/>', re.IGNORECASE)


def _extract_images(html: str) -> List[ImageRef]:
    refs: List[ImageRef] = []
    for match in _IMG_PATTERN.finditer(html):
        src, alt = match.group(1), match.group(2)
        if not src.startswith(("http://", "https://")):
            refs.append(ImageRef(original_src=src, alt_text=alt))
    return refs


def _rewrite_image_urls(body: str, images: List[ImageRef]) -> str:
    for img in images:
        if img.attachment_url:
            body = body.replace(
                f'src="{img.original_src}"',
                f'src="{img.attachment_url}"',
            )
    return body


_CSF_NS_WRAPPER = (
    '<root xmlns:ac="http://www.atlassian.com/schema/confluence/4/ac/"'
    ' xmlns:ri="http://www.atlassian.com/schema/confluence/4/ri/">'
    "{body}"
    "</root>"
)


def _is_valid_xhtml(html: str) -> bool:
    try:
        parser = lxml_etree.XMLParser(recover=False)
        lxml_etree.fromstring(_CSF_NS_WRAPPER.format(body=html).encode(), parser)
        return True
    except lxml_etree.XMLSyntaxError:
        return False


_FENCE_RE = re.compile(r"^```(\w*)\n(.*?)^```", re.MULTILINE | re.DOTALL)


def _md_to_csf(md_text: str) -> str:
    # Extract fenced code blocks before markdown2 sees them so Pygments
    # syntax-highlighting doesn't obscure the language tag or raw content.
    # Use an HTML-tag placeholder so markdown2 passes it through verbatim.
    blocks: list[str] = []

    def _stash(m: re.Match) -> str:
        lang = m.group(1) or "none"
        code = m.group(2).rstrip("\n")
        macro = (
            '<ac:structured-macro ac:name="code">'
            f'<ac:parameter ac:name="language">{lang}</ac:parameter>'
            f'<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>'
            "</ac:structured-macro>"
        )
        idx = len(blocks)
        blocks.append(macro)
        # Wrap in a div so markdown2 treats it as a block-level HTML element
        # and passes it through without modification.
        return f'<div id="docsync-code-{idx}"></div>'

    md_no_fences = _FENCE_RE.sub(_stash, md_text)

    html = markdown2.markdown(
        md_no_fences,
        extras=[
            "tables",
            "strike",
            "task_list",
            "header-ids",
            "footnotes",
        ],
    )

    for idx, macro in enumerate(blocks):
        html = html.replace(f'<div id="docsync-code-{idx}"></div>', macro)

    return html


def _make_fallback(md_text: str) -> str:
    escaped = md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<ac:structured-macro ac:name="code">'
        '<ac:parameter ac:name="language">none</ac:parameter>'
        f'<ac:plain-text-body><![CDATA[{escaped}]]></ac:plain-text-body>'
        "</ac:structured-macro>"
    )


def convert(md_text: str, base_path: str = "") -> ConversionResult:
    """Convert markdown text to Confluence Storage Format."""
    try:
        body = _md_to_csf(md_text)
    except Exception:
        body = _make_fallback(md_text)
        return ConversionResult(body=body, valid=False, fallback_used=True)

    images = _extract_images(body)
    for img in images:
        if base_path:
            img.resolved_path = f"{base_path.rstrip('/')}/{img.original_src}"

    valid = _is_valid_xhtml(body)
    if not valid:
        body = _make_fallback(md_text)
        return ConversionResult(body=body, valid=False, images=[], fallback_used=True)

    return ConversionResult(body=body, valid=True, images=images)


def apply_attachment_urls(result: ConversionResult) -> ConversionResult:
    """Rewrite image src attributes to uploaded Confluence attachment URLs."""
    new_body = _rewrite_image_urls(result.body, result.images)
    return ConversionResult(
        body=new_body,
        valid=result.valid,
        images=result.images,
        fallback_used=result.fallback_used,
    )
