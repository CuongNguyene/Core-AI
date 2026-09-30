"""Checksum-bound evaluation contracts and deterministic preflight helpers."""

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.extraction.fixture_integrity import SafeDocumentFingerprint


class EvaluationManifest(BaseModel):
    fixture_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    reference_sha256: str = Field(min_length=64, max_length=64)
    mime_type: str = Field(min_length=1)
    page_count: int = Field(gt=0)
    manifest_version: str = Field(min_length=1)
    expected_education: list[str] = Field(default_factory=list)
    expected_capability_families: list[str] = Field(default_factory=list)
    experience_minimum: int = Field(default=0, ge=0)

    @field_validator("reference_sha256")
    @classmethod
    def _sha256_hex(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            raise ValueError("reference_sha256 must be a SHA-256 hex digest")
        return value.lower()


class EvaluationFixtureIntegrityError(ValueError):
    """The labelled evaluation source does not match its manifest."""

    code = "EVALUATION_FIXTURE_INTEGRITY_FAILED"

    def __init__(self, mismatches: Mapping[str, tuple[object, object]]) -> None:
        self.mismatches = mismatches
        super().__init__(self.code)


def validate_fixture_integrity(
    manifest: EvaluationManifest,
    actual: SafeDocumentFingerprint,
) -> None:
    expected = {
        "document_id": manifest.document_id,
        "sha256": manifest.reference_sha256,
        "page_count": manifest.page_count,
        "mime_type": manifest.mime_type,
    }
    observed = {
        "document_id": actual.document_id,
        "sha256": actual.sha256,
        "page_count": actual.page_count,
        "mime_type": actual.mime_type,
    }
    mismatches = {
        field: (expected[field], observed[field])
        for field in expected
        if expected[field] != observed[field]
    }
    if mismatches:
        raise EvaluationFixtureIntegrityError(mismatches)


async def run_bound_evaluation[T](
    manifest: EvaluationManifest,
    actual: SafeDocumentFingerprint,
    provider_call: Callable[[], Awaitable[T]],
) -> T:
    """Validate the source before allowing a provider call to execute."""

    validate_fixture_integrity(manifest, actual)
    return await provider_call()


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def evaluate_education_recall(
    actual: Sequence[str], expected: Sequence[str]
) -> dict[str, int | float]:
    actual_values = [_normalized(value) for value in actual]
    matched = sum(
        1
        for expected_value in expected
        if any(
            _normalized(expected_value) in actual_value
            or actual_value in _normalized(expected_value)
            for actual_value in actual_values
        )
    )
    return {
        "matched": matched,
        "expected": len(expected),
        "recall": matched / len(expected) if expected else 1.0,
    }


def result_binding(manifest: EvaluationManifest) -> dict[str, Any]:
    return {
        "fixture_id": manifest.fixture_id,
        "reference_sha256": manifest.reference_sha256,
        "page_count": manifest.page_count,
        "mime_type": manifest.mime_type,
        "manifest_version": manifest.manifest_version,
    }
