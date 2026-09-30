import asyncio
import hashlib
import json
import mimetypes
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.capability_analysis.models import (
    CapabilityGapAuditEventRecord,
    CapabilityGapPortfolioRecord,
    GapOverlapLinkRecord,
    RequirementAssessmentRecord,
    TargetGapRecord,
)
from app.documents.models import DocumentRecord
from app.documents.storage import DocumentBlobStore
from app.extraction.models import (
    ExtractionAuditEventRecord,
    ExtractionJobRecord,
    ExtractionProfileRecord,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_KEYS = {
    "candidate_profile",
    "content",
    "document_content",
    "model_response",
    "prompt",
    "raw_document",
    "source_excerpt",
}
SENTINEL_REQUIREMENT_ID = "seed-integration-unavailable-signal"


class IntegrationPreflightError(ValueError):
    pass


class IntegrationHTTPError(RuntimeError):
    def __init__(self, status_code: int, error_code: str) -> None:
        super().__init__(f"integration API failed: status={status_code} code={error_code}")
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True, slots=True)
class RealCVIntegrationConfig:
    api_base_url: str
    cv_path: Path
    expected_sha256: str
    target_profile_id: str
    poll_attempts: int = 120
    poll_delay_seconds: float = 1.0
    request_timeout_seconds: float = 30.0


@dataclass(frozen=True, slots=True)
class SafeIntegrationResult:
    document_id: str | None = None
    document_status: str | None = None
    job_id: str | None = None
    job_status: str | None = None
    profile_id: str | None = None
    profile_status: str | None = None
    portfolio_id: str | None = None
    current_gap_count: int | None = None
    cleanup_completed: bool = False


def validate_real_cv_input(path: Path, expected_sha256: str) -> str:
    if not path.is_file():
        raise IntegrationPreflightError("PAI_REAL_CV_PATH must point to a file")
    if path.suffix.lower() not in {".pdf", ".docx"}:
        raise IntegrationPreflightError("CV must be a PDF or DOCX")
    if not _SHA256_PATTERN.fullmatch(expected_sha256):
        raise IntegrationPreflightError("PAI_REAL_CV_SHA256 must be a lowercase sha256")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        raise IntegrationPreflightError("CV sha256 does not match PAI_REAL_CV_SHA256")
    return actual


def safe_result(**values: object) -> dict[str, object]:
    allowed = set(SafeIntegrationResult.__dataclass_fields__)
    return {key: value for key, value in values.items() if key in allowed and value is not None}


def _assert_no_forbidden_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise AssertionError(f"portfolio response contains redacted field: {key}")
            _assert_no_forbidden_fields(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_forbidden_fields(child)


def assert_portfolio_contract(payload: Mapping[str, Any]) -> None:
    _assert_no_forbidden_fields(payload)
    if "combined_score" in payload or "readiness_score" in payload:
        raise AssertionError("portfolio must not contain a combined score")
    current = payload.get("current_role")
    if not isinstance(current, Mapping):
        raise AssertionError("portfolio current_role is missing")
    if current.get("target_type") != "current_role":
        raise AssertionError("portfolio current_role target type is invalid")
    if current.get("usage_mode") != "official":
        raise AssertionError("seeded active target must use official mode")
    assessments = current.get("assessments")
    gaps = current.get("gaps")
    if not isinstance(assessments, list) or not assessments:
        raise AssertionError("current-role assessments are missing")
    if not isinstance(gaps, list) or not gaps:
        raise AssertionError("current-role gaps are missing")
    if any(
        item.get("target_type") != "current_role"
        for item in assessments
        if isinstance(item, Mapping)
    ):
        raise AssertionError("assessment target type is not local to current role")
    if any(item.get("target_type") != "current_role" for item in gaps if isinstance(item, Mapping)):
        raise AssertionError("gap target type is not local to current role")
    if not any(
        item.get("requirement_id") == SENTINEL_REQUIREMENT_ID
        for item in gaps
        if isinstance(item, Mapping)
    ):
        raise AssertionError("sentinel current-role gap is missing")


async def cleanup_live_data(
    session_factory: async_sessionmaker[AsyncSession],
    blob_store: DocumentBlobStore,
    result: Mapping[str, object],
    *,
    enabled: bool,
) -> dict[str, object]:
    """Delete only the exact CV run identified by the result."""

    if not enabled:
        return dict(result)
    required = ("document_id", "job_id", "profile_id", "portfolio_id")
    if any(not isinstance(result.get(key), str) for key in required):
        raise IntegrationPreflightError("cleanup requires all run-scoped IDs")
    document_id = str(result["document_id"])
    job_id = str(result["job_id"])
    profile_id = str(result["profile_id"])
    portfolio_id = str(result["portfolio_id"])
    document_uuid = UUID(document_id)
    async with session_factory() as session:
        document = await session.get(DocumentRecord, document_uuid)
        if document is None:
            raise IntegrationPreflightError("cleanup document was not found")
        object_key = document.object_key
    await blob_store.delete(object_key)
    async with session_factory() as session, session.begin():
        await session.execute(
            delete(GapOverlapLinkRecord).where(GapOverlapLinkRecord.portfolio_id == portfolio_id)
        )
        await session.execute(
            delete(RequirementAssessmentRecord).where(
                RequirementAssessmentRecord.portfolio_id == portfolio_id
            )
        )
        await session.execute(
            delete(TargetGapRecord).where(TargetGapRecord.portfolio_id == portfolio_id)
        )
        await session.execute(
            delete(CapabilityGapAuditEventRecord).where(
                CapabilityGapAuditEventRecord.portfolio_id == portfolio_id
            )
        )
        await session.execute(
            delete(ExtractionAuditEventRecord).where(ExtractionAuditEventRecord.job_id == job_id)
        )
        await session.execute(
            delete(ExtractionProfileRecord).where(ExtractionProfileRecord.id == profile_id)
        )
        await session.execute(delete(ExtractionJobRecord).where(ExtractionJobRecord.id == job_id))
        await session.execute(delete(DocumentRecord).where(DocumentRecord.id == document_uuid))
        await session.execute(
            delete(CapabilityGapPortfolioRecord).where(
                CapabilityGapPortfolioRecord.id == portfolio_id
            )
        )
    return {**result, "cleanup_completed": True}


async def _request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    actor_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    response = await client.request(
        method,
        path,
        headers={"X-PAI-Actor-ID": actor_id},
        **kwargs,
    )
    if response.status_code >= 400:
        error_code = "http_error"
        try:
            body = response.json()
            error = body.get("error", {}) if isinstance(body, dict) else {}
            if isinstance(error, dict) and isinstance(error.get("code"), str):
                error_code = error["code"]
        except ValueError:
            pass
        raise IntegrationHTTPError(response.status_code, error_code)
    body = response.json()
    if not isinstance(body, dict):
        raise IntegrationHTTPError(response.status_code, "invalid_json_object")
    return body


async def run_integration(config: RealCVIntegrationConfig) -> dict[str, object]:
    cleanup_flag = os.environ.get("PAI_REAL_CV_CLEANUP", "false").lower()
    if cleanup_flag not in {"true", "false"}:
        raise IntegrationPreflightError("PAI_REAL_CV_CLEANUP must be true or false")
    validate_real_cv_input(config.cv_path, config.expected_sha256)
    correlation_id = f"real-cv-run-{uuid4().hex[:16]}"
    content_type = mimetypes.guess_type(config.cv_path.name)[0] or "application/octet-stream"
    async with httpx.AsyncClient(
        base_url=config.api_base_url.rstrip("/"), timeout=config.request_timeout_seconds
    ) as client:
        with config.cv_path.open("rb") as handle:
            document = await _request(
                client,
                "POST",
                "/documents",
                str(LEARNER_ID),
                files={"file": ("cv", handle, content_type)},
                data={"document_kind": "cv"},
            )
        document_id = str(document["id"])
        if document.get("status") != "clean":
            raise IntegrationHTTPError(502, "document_not_clean")
        job = await _request(
            client,
            "POST",
            "/extraction-jobs",
            str(LEARNER_ID),
            json={"document_id": document_id, "document_kind": "cv"},
        )
        job_id = str(job["id"])
        profile_id: str | None = None
        latest_job = job
        for _ in range(config.poll_attempts):
            latest_job = await _request(
                client, "GET", f"/extraction-jobs/{job_id}", str(LEARNER_ID)
            )
            if latest_job.get("status") == "succeeded":
                profile_id = str(latest_job["profile_id"])
                break
            if latest_job.get("status") == "failed":
                raise IntegrationHTTPError(502, "extraction_failed")
            await asyncio.sleep(config.poll_delay_seconds)
        if profile_id is None:
            raise IntegrationHTTPError(504, "extraction_timeout")
        profile = await _request(
            client, "GET", f"/extraction-profiles/{profile_id}", str(LEARNER_ID)
        )
        if profile.get("review_state") != "pending_review" or not profile.get("candidate_profile"):
            raise IntegrationHTTPError(502, "candidate_profile_not_reviewable")
        accepted = await _request(
            client,
            "POST",
            f"/extraction-profiles/{profile_id}/accept",
            str(REVIEWER_ID),
            json={"expected_version": profile["version"]},
        )
        if accepted.get("review_state") != "accepted":
            raise IntegrationHTTPError(502, "candidate_profile_not_accepted")
        portfolio = await _request(
            client,
            "POST",
            "/capability-gap-portfolios",
            str(LEARNER_ID),
            json={
                "cv_profile_id": profile_id,
                "current_target_profile_id": config.target_profile_id,
                "correlation_id": correlation_id,
            },
        )
        assert_portfolio_contract(portfolio)
        restored = await _request(
            client,
            "GET",
            f"/capability-gap-portfolios/{portfolio['id']}",
            str(LEARNER_ID),
        )
        assert_portfolio_contract(restored)
        current_role = restored["current_role"]
        gap_count = len(current_role["gaps"]) if isinstance(current_role, Mapping) else None
        result = safe_result(
            document_id=document_id,
            document_status=document.get("status"),
            job_id=job_id,
            job_status=latest_job.get("status"),
            profile_id=profile_id,
            profile_status=accepted.get("review_state"),
            portfolio_id=str(portfolio["id"]),
            current_gap_count=gap_count,
            cleanup_completed=False,
        )
    if cleanup_flag == "true":
        from app.main import create_app

        app = create_app()
        try:
            result = await cleanup_live_data(
                app.state.database.session_factory,
                app.state.document_blob_store,
                result,
                enabled=True,
            )
        finally:
            await app.state.database.dispose()

    return result


def _config_from_environment() -> RealCVIntegrationConfig:
    required = {
        name: os.environ.get(name, "")
        for name in (
            "PAI_API_BASE_URL",
            "PAI_REAL_CV_PATH",
            "PAI_REAL_CV_SHA256",
            "PAI_TARGET_PROFILE_ID",
        )
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise IntegrationPreflightError(f"missing integration environment: {','.join(missing)}")
    return RealCVIntegrationConfig(
        api_base_url=required["PAI_API_BASE_URL"],
        cv_path=Path(required["PAI_REAL_CV_PATH"]),
        expected_sha256=required["PAI_REAL_CV_SHA256"],
        target_profile_id=required["PAI_TARGET_PROFILE_ID"],
    )


def main() -> None:
    result = asyncio.run(run_integration(_config_from_environment()))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
