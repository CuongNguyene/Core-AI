"""Deterministic, eval-only source-block adapter for HRM job source HTML."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from html.parser import HTMLParser

from pydantic import BaseModel, ConfigDict, Field

SOURCE_HTML_FIELDS = {
    "JOB_DESCRIPTION": "job_description_html",
    "JOB_REQUIREMENTS": "job_requirements_html",
}
ALLOWED_SOURCE_FIELDS = frozenset(
    {
        "source_application_ref",
        "job_description_html",
        "job_requirements_html",
        "job_posting_url",
    }
)
BLOCK_TAGS = frozenset({"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li"})


class JobSourceBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    block_id: str = Field(min_length=1, max_length=128)
    source_field: str = Field(pattern=r"^(JOB_DESCRIPTION|JOB_REQUIREMENTS)$")
    source_order: int = Field(gt=0)
    text: str = Field(min_length=1)


class _TextViewParser(HTMLParser):
    """Implement the exact non-browser text-view behavior frozen in EVAL-00."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() in BLOCK_TAGS or tag.lower() == "br":
            self.parts.append(None)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in BLOCK_TAGS:
            self.parts.append(None)

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(html.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.parts.append(html.unescape(f"&#{name};"))


def html_text_blocks(value: str) -> tuple[str, ...]:
    """Return ordered visible-text blocks under the frozen EVAL-00 HTML rules."""
    parser = _TextViewParser()
    parser.feed(value)
    parser.close()
    blocks: list[str] = []
    current: list[str] = []
    for part in (*parser.parts, None):
        if part is None:
            normalized = re.sub(r"\s+", " ", "".join(current).replace("\u00a0", " ")).strip()
            current.clear()
            if normalized:
                blocks.append(normalized)
        else:
            current.append(part)
    return tuple(blocks)


def build_source_blocks(target_job_source: object) -> tuple[JobSourceBlock, ...]:
    """Project only non-empty visible text; source refs and URLs remain local provenance."""
    if target_job_source is None:
        return ()
    if not isinstance(target_job_source, Mapping):
        raise ValueError("target_job_source must be an object or null")
    unknown = set(target_job_source) - ALLOWED_SOURCE_FIELDS
    if unknown:
        names = ", ".join(sorted(str(name) for name in unknown))
        raise ValueError(f"unknown target_job_source field(s): {names}")

    blocks: list[JobSourceBlock] = []
    for source_field, html_field in SOURCE_HTML_FIELDS.items():
        source_value = target_job_source.get(html_field)
        if source_value is None:
            continue
        if not isinstance(source_value, str):
            raise ValueError(f"{html_field} must be a string or null")
        for source_order, text in enumerate(html_text_blocks(source_value), start=1):
            blocks.append(
                JobSourceBlock(
                    block_id=f"jdblock:{source_field}:{source_order:04d}",
                    source_field=source_field,
                    source_order=source_order,
                    text=text,
                )
            )
    return tuple(blocks)
