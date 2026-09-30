import asyncio
import hashlib
import json
import mimetypes
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

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
from app.matching.models import RoleCompetencyProfileRecord
from app.role_profile_authoring.models import (
    RoleProfileDraftAuditRecord,
    RoleProfileDraftRecord,
    RoleProfileDraftVersionRecord,
)


class E2EPreflightError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class E2EConfig:
    api_base_url: str
    cv_path: Path
    cv_sha256: str
    jd_path: Path
    jd_sha256: str
    poll_attempts: int = 120
    poll_delay_seconds: float = 1.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_e2e_inputs(config: E2EConfig) -> None:
    for label, path, expected in (
        ("CV", config.cv_path, config.cv_sha256),
        ("JD", config.jd_path, config.jd_sha256),
    ):
        if not path.is_file():
            raise E2EPreflightError(f"{label} path is not a file")
        if path.suffix.lower() not in {".pdf", ".docx"}:
            raise E2EPreflightError(f"{label} must be a PDF or DOCX")
        if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
            raise E2EPreflightError(f"{label} hash must be lowercase sha256")
        if _sha256(path) != expected:
            raise E2EPreflightError(f"{label} sha256 mismatch")


async def _request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    actor_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    response = await client.request(method, path, headers={"X-PAI-Actor-ID": actor_id}, **kwargs)
    if response.status_code >= 400:
        body = response.json()
        code = (
            body.get("error", {}).get("code", "http_error")
            if isinstance(body, dict)
            else "http_error"
        )
        raise E2EPreflightError(f"API failed: {response.status_code}:{code}")
    body = response.json()
    if not isinstance(body, dict):
        raise E2EPreflightError("API returned a non-object response")
    return body


async def _upload_and_accept(
    client: httpx.AsyncClient,
    path: Path,
    kind: str,
) -> tuple[str, str, str]:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as handle:
        document = await _request(
            client,
            "POST",
            "/documents",
            str(LEARNER_ID),
            files={"file": ("document", handle, content_type)},
            data={"document_kind": kind},
        )
    if document.get("status") != "clean":
        raise E2EPreflightError(f"{kind} document is not clean")
    job = await _request(
        client,
        "POST",
        "/extraction-jobs",
        str(LEARNER_ID),
        json={"document_id": str(document["id"]), "document_kind": kind},
    )
    for _ in range(120):
        current = await _request(client, "GET", f"/extraction-jobs/{job['id']}", str(LEARNER_ID))
        if current.get("status") == "succeeded":
            profile_id = str(current["profile_id"])
            break
        if current.get("status") == "failed":
            raise E2EPreflightError(f"{kind} extraction failed")
        await asyncio.sleep(1)
    else:
        raise E2EPreflightError(f"{kind} extraction timed out")
    profile = await _request(client, "GET", f"/extraction-profiles/{profile_id}", str(LEARNER_ID))
    accepted = await _request(
        client,
        "POST",
        f"/extraction-profiles/{profile_id}/accept",
        str(REVIEWER_ID),
        json={"expected_version": profile["version"]},
    )
    if accepted.get("review_state") != "accepted":
        raise E2EPreflightError(f"{kind} profile was not accepted")
    return str(document["id"]), str(job["id"]), profile_id


async def cleanup_e2e_data(
    session_factory: async_sessionmaker[AsyncSession],
    blob_store: DocumentBlobStore,
    result: Mapping[str, Any],
    *,
    enabled: bool,
) -> dict[str, object]:
    if not enabled:
        return dict(result)
    document_ids = [str(result["cv_document_id"]), str(result["jd_document_id"])]
    job_ids = [str(result["cv_job_id"]), str(result["jd_job_id"])]
    profile_ids = [str(result["cv_profile_id"]), str(result["jd_profile_id"])]
    scenarios = result.get("scenarios")
    if not isinstance(scenarios, Mapping):
        raise E2EPreflightError("cleanup requires scenario IDs")
    draft_ids = [str(item["draft_id"]) for item in scenarios.values() if isinstance(item, Mapping)]
    role_ids = [
        str(item["role_profile_id"]) for item in scenarios.values() if isinstance(item, Mapping)
    ]
    portfolio_ids = [
        str(item["portfolio_id"]) for item in scenarios.values() if isinstance(item, Mapping)
    ]
    object_keys: list[str] = []
    from uuid import UUID

    async with session_factory() as session:
        for document_id in document_ids:
            document = await session.get(DocumentRecord, UUID(document_id))
            if document is None:
                raise E2EPreflightError("cleanup document was not found")
            object_keys.append(document.object_key)
    for object_key in object_keys:
        await blob_store.delete(object_key)
    async with session_factory() as session, session.begin():
        for portfolio_id in portfolio_ids:
            await session.execute(
                delete(GapOverlapLinkRecord).where(
                    GapOverlapLinkRecord.portfolio_id == portfolio_id
                )
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
                delete(CapabilityGapPortfolioRecord).where(
                    CapabilityGapPortfolioRecord.id == portfolio_id
                )
            )
        for draft_id in draft_ids:
            await session.execute(
                delete(RoleProfileDraftAuditRecord).where(
                    RoleProfileDraftAuditRecord.draft_id == draft_id
                )
            )
            await session.execute(
                delete(RoleProfileDraftVersionRecord).where(
                    RoleProfileDraftVersionRecord.draft_id == draft_id
                )
            )
            await session.execute(
                delete(RoleProfileDraftRecord).where(RoleProfileDraftRecord.id == draft_id)
            )
        for role_id in role_ids:
            await session.execute(
                delete(RoleCompetencyProfileRecord).where(RoleCompetencyProfileRecord.id == role_id)
            )
        for job_id in job_ids:
            await session.execute(
                delete(ExtractionAuditEventRecord).where(
                    ExtractionAuditEventRecord.job_id == job_id
                )
            )
        for profile_id in profile_ids:
            await session.execute(
                delete(ExtractionProfileRecord).where(ExtractionProfileRecord.id == profile_id)
            )
        for job_id in job_ids:
            await session.execute(
                delete(ExtractionJobRecord).where(ExtractionJobRecord.id == job_id)
            )
        for document_id in document_ids:
            await session.execute(
                delete(DocumentRecord).where(DocumentRecord.id == UUID(document_id))
            )
    return {**result, "cleanup_completed": True}


def _complete_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    completed = []
    for item in requirements:
        value = dict(item)
        value.update(
            {
                "priority": value.get("priority") or "medium",
                "target_level": value.get("target_level") or "working",
                "observable_behaviors": value.get("observable_behaviors")
                or ["demonstrates the capability in a role-relevant task"],
                "evidence_constraints": value.get("evidence_constraints")
                or ["source-backed work example"],
                "provenance": {
                    "capability": "jd_extraction",
                    "priority": "reviewer_authored",
                    "target_level": "reviewer_authored",
                    "observable_behaviors": "reviewer_authored",
                    "evidence_constraints": "reviewer_authored",
                },
            }
        )
        completed.append(value)
    return completed


def assert_scenario(portfolio: Mapping[str, Any], expected_mode: str) -> None:
    if portfolio.get("current_role", {}).get("usage_mode") != expected_mode:
        raise AssertionError(f"expected capability mode {expected_mode}")
    if "combined_score" in portfolio or "readiness_score" in portfolio:
        raise AssertionError("E2E portfolio must not contain a combined decision")
    forbidden = {"content", "source_excerpt", "prompt", "model_response", "candidate_profile"}

    def scan(value: object) -> None:
        if isinstance(value, Mapping):
            if forbidden.intersection(value):
                raise AssertionError("E2E result contains a forbidden raw field")
            for child in value.values():
                scan(child)
        elif isinstance(value, list):
            for child in value:
                scan(child)

    scan(portfolio)


async def run_e2e(config: E2EConfig) -> dict[str, object]:
    validate_e2e_inputs(config)
    async with httpx.AsyncClient(base_url=config.api_base_url.rstrip("/"), timeout=30) as client:
        cv_document_id, cv_job_id, cv_profile_id = await _upload_and_accept(
            client, config.cv_path, "cv"
        )
        jd_document_id, jd_job_id, jd_profile_id = await _upload_and_accept(
            client, config.jd_path, "jd"
        )
        scenarios: dict[str, object] = {}
        for name, requested_status, expected_mode, complete in (
            ("provisional_preview", "provisional", "preview", False),
            ("active_official", "active", "official", True),
        ):
            draft = await _request(
                client,
                "POST",
                "/role-profile-drafts",
                str(REVIEWER_ID),
                json={
                    "source_jd_profile_id": jd_profile_id,
                    "correlation_id": f"{name}-{uuid4().hex[:12]}",
                },
            )
            requirements = draft.get("requirements", [])
            authored = await _request(
                client,
                "PATCH",
                f"/role-profile-drafts/{draft['id']}",
                str(REVIEWER_ID),
                json={
                    "expected_version": draft["version"],
                    "title": "E2E authored role",
                    "requirements": _complete_requirements(requirements)
                    if complete
                    else requirements,
                },
            )
            validated = await _request(
                client,
                "POST",
                f"/role-profile-drafts/{draft['id']}/validate",
                str(REVIEWER_ID),
                json={"expected_version": authored["version"]},
            )
            approved = await _request(
                client,
                "POST",
                f"/role-profile-drafts/{draft['id']}/approve",
                str(REVIEWER_ID),
                json={
                    "expected_version": validated["version"],
                    "requested_status": requested_status,
                },
            )
            portfolio = await _request(
                client,
                "POST",
                "/capability-gap-portfolios",
                str(LEARNER_ID),
                json={
                    "cv_profile_id": cv_profile_id,
                    "current_target_profile_id": approved["approved_role_profile_id"],
                    "correlation_id": f"{name}-portfolio-{uuid4().hex[:12]}",
                },
            )
            assert_scenario(portfolio, expected_mode)
            scenarios[name] = {
                "draft_id": draft["id"],
                "role_profile_id": approved["approved_role_profile_id"],
                "portfolio_id": portfolio["id"],
                "mode": expected_mode,
            }
    return {
        "cv_document_id": cv_document_id,
        "cv_job_id": cv_job_id,
        "cv_profile_id": cv_profile_id,
        "jd_document_id": jd_document_id,
        "jd_job_id": jd_job_id,
        "jd_profile_id": jd_profile_id,
        "scenarios": scenarios,
        "cleanup_scope": "exact_ids_only",
    }


def _config() -> E2EConfig:
    values = {
        name: os.environ.get(name, "")
        for name in (
            "PAI_API_BASE_URL",
            "PAI_REAL_CV_PATH",
            "PAI_REAL_CV_SHA256",
            "PAI_REAL_JD_PATH",
            "PAI_REAL_JD_SHA256",
        )
    }
    if any(not value for value in values.values()):
        raise E2EPreflightError("PAI_API_BASE_URL and both real-file paths/hashes are required")
    return E2EConfig(
        api_base_url=values["PAI_API_BASE_URL"],
        cv_path=Path(values["PAI_REAL_CV_PATH"]),
        cv_sha256=values["PAI_REAL_CV_SHA256"],
        jd_path=Path(values["PAI_REAL_JD_PATH"]),
        jd_sha256=values["PAI_REAL_JD_SHA256"],
    )


async def _main() -> None:
    cleanup_flag = os.environ.get("PAI_REAL_CV_JD_CLEANUP", "false").lower()
    if cleanup_flag not in {"true", "false"}:
        raise E2EPreflightError("PAI_REAL_CV_JD_CLEANUP must be true or false")
    result = await run_e2e(_config())
    if cleanup_flag == "true":
        from app.main import create_app

        app = create_app()
        try:
            result = await cleanup_e2e_data(
                app.state.database.session_factory,
                app.state.document_blob_store,
                result,
                enabled=True,
            )
        finally:
            await app.state.database.dispose()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(_main())
