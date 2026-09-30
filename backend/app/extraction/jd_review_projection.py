"""Reviewer-safe normalized projection for requirement-oriented JD extraction."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict

from app.extraction.locators import SourceLocator
from app.extraction.schemas import (
    ExtractionProfile,
    JDRequirementExtractionOutputV2,
    JDRequirementExtractionV2,
    JDRequirementModality,
    JDReviewCorrectionRequest,
    NativePdfLocator,
    ProviderPdfLocator,
    ReviewState,
)


class JDReviewEvidenceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["pdf_page", "text_span"]
    display_label: str
    page_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None


class JDReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    review_item_id: str
    requirement_id: str | None
    statement: str | None
    modality: str | None
    criterion_dimension: str | None
    evidence_status: str
    source_excerpt: str | None
    evidence_location: JDReviewEvidenceLocation | None
    logical_group: str | None
    logical_operator: str
    priority: str | None
    target_level: str | None
    observable_behaviors: list[str]
    evidence_constraints: list[str]


class JDReviewGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    key: Literal["responsibilities", "required", "preferred", "scope_exclusions"]
    label: str
    items: list[JDReviewItem]


class JDReviewProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str
    document_id: str
    document_kind: Literal["jd"]
    source_format: Literal["pdf", "text"]
    version: int
    review_state: ReviewState
    created_at: datetime | None = None
    requirement_count: int
    groups: list[JDReviewGroup]
    requirements: list[JDReviewItem]
    safe_metadata: dict[str, str | int | float | bool]


def build_jd_review_projection(
    profile: ExtractionProfile,
    *,
    source_format: Literal["pdf", "text"] | None = None,
) -> JDReviewProjection:
    if profile.document_kind.value != "jd" or not isinstance(
        profile.output, JDRequirementExtractionOutputV2
    ):
        raise ValueError("JD extraction profile is required")

    output = profile.output
    requirements = [
        _project_item(profile, index, item) for index, item in enumerate(output.requirements)
    ]
    grouped: dict[str, list[JDReviewItem]] = {
        "responsibilities": [],
        "required": [],
        "preferred": [],
        "scope_exclusions": [],
    }
    for item in requirements:
        grouped[_group_key(item)].append(item)

    labels = {
        "responsibilities": "Responsibilities",
        "required": "Required criteria",
        "preferred": "Preferred criteria",
        "scope_exclusions": "Scope / exclusions",
    }
    groups = [
        JDReviewGroup(
            key=cast(Literal["responsibilities", "required", "preferred", "scope_exclusions"], key),
            label=labels[key],
            items=items,
        )
        for key, items in grouped.items()
        if items
    ]
    safe_metadata = {
        key: value
        for key, value in profile.audit.items()
        if key in {"pipeline_mode", "capability_mode", "taxonomy_id", "taxonomy_version", "schema_version"}
        and isinstance(value, (str, int, float, bool))
    }
    resolved_source_format = source_format or ("pdf" if any(
        isinstance(item.source_locator, (NativePdfLocator, ProviderPdfLocator))
        for item in output.requirements
    ) else "text")
    return JDReviewProjection(
        profile_id=profile.id,
        document_id=profile.document_id,
        document_kind="jd",
        source_format=resolved_source_format,
        version=profile.version,
        review_state=profile.review_state,
        created_at=profile.created_at,
        requirement_count=len(requirements),
        groups=groups,
        requirements=requirements,
        safe_metadata=safe_metadata,
    )


def apply_jd_review_correction(
    profile: ExtractionProfile, request: JDReviewCorrectionRequest
) -> JDRequirementExtractionOutputV2:
    """Apply a bounded review edit to a complete JD output copy."""
    projection = build_jd_review_projection(profile)
    matches = [
        index
        for index, item in enumerate(projection.requirements)
        if item.review_item_id == request.review_item_id
    ]
    if len(matches) != 1:
        raise ValueError("JD review item was not found in the current profile version")
    index = matches[0]
    payload = profile.output.model_dump(mode="json")
    requirements = payload["requirements"]
    if request.operation == "remove":
        requirements.pop(index)
    else:
        if request.statement is None and request.modality is None and request.criterion_dimension is None:
            raise ValueError("JD correction has no editable fields")
        current = dict(requirements[index])
        if request.statement is not None:
            current["statement"] = request.statement.strip()
        if request.modality is not None:
            current["modality"] = request.modality.value
            if request.modality in {
                JDRequirementModality.RESPONSIBILITY,
                JDRequirementModality.UNSPECIFIED,
            }:
                current["criterion_dimension"] = None
        if request.criterion_dimension is not None:
            current["criterion_dimension"] = request.criterion_dimension
        requirements[index] = current
    return JDRequirementExtractionOutputV2.model_validate(payload, strict=False)


def _project_item(profile: ExtractionProfile, index: int, item: JDRequirementExtractionV2) -> JDReviewItem:
    locator = item.source_locator
    if locator is not None and getattr(locator, "document_id", None) != profile.document_id:
        raise ValueError("JD review evidence belongs to another document")
    return JDReviewItem(
        review_item_id=_review_item_id(profile, index, item),
        requirement_id=item.requirement_id,
        statement=item.statement,
        modality=item.modality.value if item.modality else None,
        criterion_dimension=item.criterion_dimension,
        evidence_status=item.evidence_status.value,
        source_excerpt=item.source_excerpt,
        evidence_location=_project_location(locator),
        logical_group=item.logical_group,
        logical_operator=item.logical_operator,
        priority=item.priority,
        target_level=item.target_level,
        observable_behaviors=list(item.observable_behaviors),
        evidence_constraints=list(item.evidence_constraints),
    )


def _project_location(locator: object | None) -> JDReviewEvidenceLocation | None:
    if isinstance(locator, (NativePdfLocator, ProviderPdfLocator)):
        return JDReviewEvidenceLocation(
            kind="pdf_page",
            display_label=f"Page {locator.page_number}",
            page_number=locator.page_number,
        )
    if isinstance(locator, SourceLocator):
        return JDReviewEvidenceLocation(
            kind="text_span",
            display_label="JD text",
            start_offset=locator.start_offset,
            end_offset=locator.end_offset,
        )
    return None


def _review_item_id(profile: ExtractionProfile, index: int, item: JDRequirementExtractionV2) -> str:
    payload = json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()[:12]
    return f"{profile.id}:v{profile.version}:requirement:{index}:{digest}"


def _group_key(item: JDReviewItem) -> Literal["responsibilities", "required", "preferred", "scope_exclusions"]:
    if item.modality == JDRequirementModality.RESPONSIBILITY.value:
        return "responsibilities"
    if item.modality == JDRequirementModality.PREFERRED.value:
        return "preferred"
    if item.modality == JDRequirementModality.UNSPECIFIED.value:
        return "scope_exclusions"
    return "required"
