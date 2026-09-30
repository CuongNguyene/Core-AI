from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.extraction.models import ExtractionJobRecord, ExtractionProfileRecord
from app.extraction.schemas import DocumentKind, JobStatus, ReviewState
from app.matching.models import RoleCompetencyProfileRecord, RoleProfileSemanticPolicyMappingRecord
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)

SOURCE_JD_PROFILE_ID = "seed-real-cv-capability-jd"
SOURCE_JD_JOB_ID = "seed-real-cv-capability-jd-job"
TARGET_PROFILE_ID = "seed-real-cv-capability-target"
TARGET_PROFILE_VERSION = "1.0"
SENTINEL_REQUIREMENT_ID = "seed-integration-unavailable-signal"
SENTINEL_EVIDENCE_TERM = SENTINEL_REQUIREMENT_ID
SEED_RULE_SET_VERSION = "capability-real-cv-v1"
SEED_POLICY_VERSION = "capability-policy-v1"
SEED_DOCUMENT_ID = "seed-real-cv-capability-jd-document"
_SEED_CREATED_AT = datetime(2026, 8, 6, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SeededCapabilityTarget:
    target_profile_id: str
    target_profile_version: str
    source_jd_profile_id: str


def _requirements() -> list[RoleRequirement]:
    return [
        RoleRequirement(
            id="seed-python",
            criterion_dimension=CriterionDimension.SKILL,
            classification=RequirementClassification.ROLE_CRITICAL,
            evidence_terms=["python"],
            confidence_threshold=0.7,
            assessment_recommendation="practical_task",
            rubric_version="rubric-v1",
        ),
        RoleRequirement(
            id="seed-fastapi",
            criterion_dimension=CriterionDimension.SKILL,
            classification=RequirementClassification.PREFERRED,
            evidence_terms=["fastapi"],
            confidence_threshold=0.7,
            assessment_recommendation="practical_task",
            rubric_version="rubric-v1",
        ),
        RoleRequirement(
            id=SENTINEL_REQUIREMENT_ID,
            criterion_dimension=CriterionDimension.SKILL,
            classification=RequirementClassification.OPTIONAL,
            evidence_terms=[SENTINEL_EVIDENCE_TERM],
            confidence_threshold=0.7,
            assessment_recommendation="practical_task",
            rubric_version="rubric-v1",
        ),
    ]


def _target() -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id=TARGET_PROFILE_ID,
        version=TARGET_PROFILE_VERSION,
        status=RoleProfileStatus.ACTIVE,
        source_jd_profile_id=SOURCE_JD_PROFILE_ID,
        source_jd_profile_version=1,
        rule_set_version=SEED_RULE_SET_VERSION,
        policy_version=SEED_POLICY_VERSION,
        requirements=_requirements(),
    )


def _source_values() -> dict[str, object]:
    return {
        "id": SOURCE_JD_PROFILE_ID,
        "job_id": SOURCE_JD_JOB_ID,
        "document_id": SEED_DOCUMENT_ID,
        "document_kind": DocumentKind.JD.value,
        "owner_actor_id": REVIEWER_ID,
        "version": 1,
        "review_state": ReviewState.ACCEPTED.value,
        "accepted_by": REVIEWER_ID,
        "accepted_at": _SEED_CREATED_AT,
        "supersedes_profile_id": None,
        "normalized_output": {
            "required_skills": [],
            "responsibilities": [],
            "qualifications": [],
        },
        "audit_metadata": {
            "action": "REAL_CV_CAPABILITY_INTEGRATION_SEED",
            "seed_version": "1",
            "owner_actor_id": str(REVIEWER_ID),
        },
    }


async def seed_real_cv_capability_target(
    session_factory: async_sessionmaker[AsyncSession],
) -> SeededCapabilityTarget:
    """Create the fixed source JD and active target used by the real-CV harness."""

    target = _target()
    target_values = {
        "id": target.id,
        "version": target.version,
        "status": target.status.value,
        "source_jd_profile_id": target.source_jd_profile_id,
        "source_jd_profile_version": target.source_jd_profile_version,
        "rule_set_version": target.rule_set_version,
        "policy_version": target.policy_version,
        "requirements": [item.model_dump(mode="json") for item in target.requirements],
    }

    async with session_factory() as session, session.begin():
        job = await session.get(ExtractionJobRecord, SOURCE_JD_JOB_ID)
        source = await session.get(ExtractionProfileRecord, SOURCE_JD_PROFILE_ID)
        role = await session.scalar(
            select(RoleCompetencyProfileRecord).where(
                RoleCompetencyProfileRecord.id == TARGET_PROFILE_ID,
                RoleCompetencyProfileRecord.version == TARGET_PROFILE_VERSION,
            )
        )

        if job is not None and _job_values(job) != _expected_job_values():
            raise ValueError("seed source job conflict")
        if source is not None and _source_record_values(source) != _source_values():
            raise ValueError("seed source profile conflict")
        if role is not None and _role_values(role) != target_values:
            raise ValueError("seed target conflict")

        if job is None:
            session.add(
                ExtractionJobRecord(
                    **_expected_job_values(),
                )
            )
        if source is None:
            session.add(ExtractionProfileRecord(**_source_values()))
        if role is None:
            session.add(
                RoleCompetencyProfileRecord(
                    record_id=f"{TARGET_PROFILE_ID}:{TARGET_PROFILE_VERSION}",
                    **target_values,
                )
            )

        mapping = await session.get(
            RoleProfileSemanticPolicyMappingRecord,
            (TARGET_PROFILE_ID, TARGET_PROFILE_VERSION),
        )
        if mapping is None:
            session.add(
                RoleProfileSemanticPolicyMappingRecord(
                    role_profile_id=TARGET_PROFILE_ID,
                    role_profile_version=TARGET_PROFILE_VERSION,
                    core_version="semantic-core-v1",
                    pack_refs=[{"pack_id": "it_ai", "version": "1"}],
                    selection_source="legacy_profile_version_mapping",
                )
            )

    return SeededCapabilityTarget(
        target_profile_id=TARGET_PROFILE_ID,
        target_profile_version=TARGET_PROFILE_VERSION,
        source_jd_profile_id=SOURCE_JD_PROFILE_ID,
    )


def _expected_job_values() -> dict[str, object]:
    return {
        "id": SOURCE_JD_JOB_ID,
        "document_id": SEED_DOCUMENT_ID,
        "document_kind": DocumentKind.JD.value,
        "owner_actor_id": LEARNER_ID,
        "correlation_id": SOURCE_JD_JOB_ID,
        "status": JobStatus.SUCCEEDED.value,
        "error_category": None,
        "profile_id": SOURCE_JD_PROFILE_ID,
    }


def _job_values(job: ExtractionJobRecord) -> dict[str, object]:
    return {
        "id": job.id,
        "document_id": job.document_id,
        "document_kind": job.document_kind,
        "owner_actor_id": job.owner_actor_id,
        "correlation_id": job.correlation_id,
        "status": job.status,
        "error_category": job.error_category,
        "profile_id": job.profile_id,
    }


def _source_record_values(source: ExtractionProfileRecord) -> dict[str, object]:
    accepted_at = source.accepted_at
    if accepted_at is not None and accepted_at.tzinfo is None:
        accepted_at = accepted_at.replace(tzinfo=UTC)
    return {
        "id": source.id,
        "job_id": source.job_id,
        "document_id": source.document_id,
        "document_kind": source.document_kind,
        "owner_actor_id": source.owner_actor_id,
        "version": source.version,
        "review_state": source.review_state,
        "accepted_by": source.accepted_by,
        "accepted_at": accepted_at,
        "supersedes_profile_id": source.supersedes_profile_id,
        "normalized_output": source.normalized_output,
        "audit_metadata": source.audit_metadata,
    }


def _role_values(role: RoleCompetencyProfileRecord) -> dict[str, object]:
    return {
        "id": role.id,
        "version": role.version,
        "status": role.status,
        "source_jd_profile_id": role.source_jd_profile_id,
        "source_jd_profile_version": role.source_jd_profile_version,
        "rule_set_version": role.rule_set_version,
        "policy_version": role.policy_version,
        "requirements": role.requirements,
    }
