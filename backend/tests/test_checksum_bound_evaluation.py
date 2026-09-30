import asyncio

import pytest
from pytest import mark

from app.extraction.evaluation_binding import (
    EvaluationFixtureIntegrityError,
    EvaluationManifest,
    evaluate_education_recall,
    run_bound_evaluation,
    validate_fixture_integrity,
)
from app.extraction.fixture_integrity import SafeDocumentFingerprint, fingerprint_bytes


def _manifest(**overrides: object) -> EvaluationManifest:
    values: dict[str, object] = {
        "fixture_id": "cv-nguyen-vu-minh-thien",
        "document_id": "40584171-3e68-4e6e-8497-089f830797fc",
        "reference_sha256": "a" * 64,
        "mime_type": "application/pdf",
        "page_count": 3,
        "manifest_version": "1.0",
        "expected_education": ["MBA of eCommerce", "Bachelor"],
        "expected_capability_families": ["eCommerce"],
        "experience_minimum": 4,
    }
    values.update(overrides)
    return EvaluationManifest.model_validate(values)


def _actual(
    *, sha256: str = "a" * 64, page_count: int = 3, mime_type: str = "application/pdf"
) -> SafeDocumentFingerprint:
    return fingerprint_bytes(
        fixture_name="cv-nguyen-vu-minh-thien",
        document_id="40584171-3e68-4e6e-8497-089f830797fc",
        storage_key="documents/reference",
        filename="reference.pdf",
        mime_type=mime_type,
        content=b"reference",
        page_count=page_count,
        input_mode="native_pdf",
    ).model_copy(update={"sha256": sha256})


@mark.parametrize(
    ("field", "value"),
    [("reference_sha256", "b" * 64), ("page_count", 2), ("mime_type", "text/plain")],
)
def test_integrity_mismatch_fails_before_provider(field: str, value: object) -> None:
    manifest = _manifest(**{field: value})
    calls = 0

    with pytest.raises(EvaluationFixtureIntegrityError):
        validate_fixture_integrity(manifest, _actual())
    assert calls == 0


def test_integrity_match_is_accepted() -> None:
    validate_fixture_integrity(_manifest(), _actual())


def test_integrity_failure_makes_zero_provider_calls() -> None:
    calls = 0

    async def provider() -> str:
        nonlocal calls
        calls += 1
        return "unexpected"

    with pytest.raises(EvaluationFixtureIntegrityError):
        asyncio.run(run_bound_evaluation(_manifest(), _actual(page_count=2), provider))
    assert calls == 0


def test_manifest_requires_sha256() -> None:
    with pytest.raises(ValueError):
        _manifest(reference_sha256="abc123")


def test_education_recall_uses_bounded_normalization() -> None:
    assert evaluate_education_recall(["Bachelor of Engineering"], ["MBA", "Bachelor"]) == {
        "matched": 1,
        "expected": 2,
        "recall": 0.5,
    }
