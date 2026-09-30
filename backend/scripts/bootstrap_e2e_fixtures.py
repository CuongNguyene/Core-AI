"""Create deterministic, provider-free fixtures for the read-only Playwright smoke.

This is intentionally a test-tooling script. It uses the existing SQLAlchemy models and
Pydantic contracts, never the production HTTP API, and emits only non-secret IDs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TypedDict
from uuid import UUID

from sqlalchemy import select

from app.candidate.models import CandidateProfileRecord, CandidateRecord
from app.candidate.schemas import CandidateReviewState, CandidateStatus
from app.capability_analysis.models import (
    CapabilityGapAuditEventRecord,
    CapabilityGapPortfolioRecord,
    RequirementAssessmentRecord,
    TargetGapRecord,
)
from app.capability_analysis.schemas import (
    AssessmentDecisionDetails,
    AssessmentEvidenceStatus,
    CombinedGapPortfolio,
    PreliminaryPriority,
    RequirementAssessment,
    TargetGap,
    TargetGapAnalysis,
    TargetType,
    TargetUsageMode,
)
from app.documents.models import DocumentRecord
from app.documents.schemas import DocumentKind, DocumentStatus
from app.extraction.capability_projection import project_v2_to_candidate_profile
from app.extraction.models import ExtractionJobRecord, ExtractionProfileRecord
from app.extraction.schemas import (
    CapabilityEvidence,
    CapabilityItem,
    CVFullExtractionOutputV2,
    EvidenceStrength,
    ExperienceItem,
    ReviewState,
    SourceLocator,
)
from app.learning.models import LearningPathRecord
from app.matching.models import RoleCompetencyProfileRecord
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleProfileStatus,
    RoleRequirement,
)
from app.role_profile_authoring.models import RoleProfileDraftRecord
from app.role_registry.models import RoleJDRecord, RoleJDVersionRecord, RoleRecord
from app.shared.database import Database

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
ACTOR_ID = UUID("00000000-0000-0000-0000-000000000004")
CANDIDATE_ID = UUID("08b10000-0000-4000-8000-000000000001")
ROLE_ID = UUID("08b10000-0000-4000-8000-000000000002")
ROLE_JD_ID = UUID("08b10000-0000-4000-8000-000000000003")
ROLE_JD_VERSION_ID = UUID("08b10000-0000-4000-8000-000000000004")
CV_DOCUMENT_ID = UUID("08b10000-0000-4000-8000-000000000005")
JD_DOCUMENT_ID = UUID("08b10000-0000-4000-8000-000000000006")
JD_SOURCE_DOCUMENT_ID = "fixture-jd-basic"
CV_PROFILE_ID = "e2e-cv-profile-08b1"
JD_PROFILE_ID = "e2e-jd-profile-08b1"
ROLE_PROFILE_A = "role-profile-e2e-08b1-a"
ROLE_PROFILE_B = "role-profile-e2e-08b1-b"
ROLE_PROFILE_DRAFT_ID = "e2e-role-profile-draft-08b1"
ROLE_PROFILE_VERSION = "1"
ROLE_CODE = "E2E-08B1"
HISTORICAL_LEARNING_PATH_ID = "e2e-historical-learning-path-08b1"


class _CommonRequirement(TypedDict):
    classification: RequirementClassification
    confidence_threshold: float
    assessment_recommendation: str
    rubric_version: str
    priority: str
    target_level: str
    observable_behaviors: list[str]


def fixture_manifest() -> dict[str, str]:
    return {
        "candidateId": str(CANDIDATE_ID),
        "positiveAnalysisId": "cap-demo-08b1-positive",
        "negativeAnalysisId": "cap-demo-08b1-negative",
        "historicalAnalysisId": "cap-demo-08b1-historical",
        "comparisonAnalysisB": "cap-demo-08b1-comparison",
        "crossProfileAnalysisA": "cap-demo-08b1-cross-a",
        "crossProfileAnalysisB": "cap-demo-08b1-cross-b",
        "roleCode": ROLE_CODE,
        "acceptedJdProfileId": JD_PROFILE_ID,
        "roleProfileDraftId": ROLE_PROFILE_DRAFT_ID,
        "roleProfileDraftRoleId": str(ROLE_ID),
        "roleProfileDraftJdVersionId": str(ROLE_JD_VERSION_ID),
        "historicalLearningPathId": HISTORICAL_LEARNING_PATH_ID,
    }


def _historical_learning_path_record() -> LearningPathRecord:
    objective_id = "e2e-historical-objective-08b1"
    learning_object_id = "e2e-historical-object-08b1"
    lesson_id = "e2e-historical-lesson-08b1"
    module_id = "e2e-historical-module-08b1"
    prerequisite_id = "e2e-historical-prerequisite-08b1"
    gap_id = "e2e-historical-gap-08b1"
    competency_id = "e2e-historical-competency-08b1"
    return LearningPathRecord(
        id=HISTORICAL_LEARNING_PATH_ID,
        version=1,
        status="draft",
        subject_id=ACTOR_ID,
        organization_id=ORG_ID,
        target_profile_id=ROLE_PROFILE_A,
        target_profile_version=ROLE_PROFILE_VERSION,
        preliminary_match_id="e2e-historical-match-08b1",
        verified_competency_record_ids=["08b10000-0000-4000-8000-000000000010"],
        approved_gap_ids=[gap_id],
        development_goal="Review the historical capability learning path.",
        target_completion_date=date(2026, 12, 31),
        objectives=[
            {
                "id": objective_id,
                "learning_need_ref": None,
                "statement": "Review a capability development objective.",
                "bloom_level": "apply",
                "evidence_required": [],
                "competency_id": competency_id,
                "current_level": 1,
                "target_level": 2,
                "measurable_outcome": "Explain the intended development outcome.",
                "gap_id": gap_id,
                "sequence": 1,
            }
        ],
        prerequisite_nodes=[{"id": prerequisite_id, "learning_object_id": learning_object_id}],
        prerequisite_edges=[],
        learning_objects=[
            {
                "id": learning_object_id,
                "version": "1",
                "object_type": "reading",
                "title": "Historical learning object",
                "estimated_minutes": 15,
                "competency_id": competency_id,
                "target_level": 2,
                "assessment_template_id": "e2e-historical-assessment-08b1",
                "assessment_template_version": "1",
                "approved_source_reference": "e2e-historical-source-08b1",
                "provenance_status": "approved",
            }
        ],
        lessons=[
            {
                "id": lesson_id,
                "version": "1",
                "title": "Historical learning path lesson",
                "objective_ids": [objective_id],
                "learning_object_ids": [learning_object_id],
            }
        ],
        modules=[
            {
                "id": module_id,
                "version": "1",
                "title": "Historical learning path module",
                "objective_ids": [objective_id],
                "lesson_ids": [lesson_id],
                "prerequisite_node_ids": [prerequisite_id],
            }
        ],
        blueprints=[
            {
                "id": "e2e-historical-blueprint-08b1",
                "version": "1",
                "title": "Historical learning path blueprint",
                "objective_ids": [objective_id],
                "module_ids": [module_id],
                "provenance_status": "approved",
            }
        ],
        generator_version="e2e-fixture",
        policy_version="e2e-fixture",
        correlation_id="e2e-historical-learning-path-08b1",
        created_by=ACTOR_ID,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        source_type="capability_analysis",
        capability_analysis_id="cap-demo-08b1-historical",
        capability_analysis_version=1,
        source_candidate_id=CANDIDATE_ID,
        source_profile_id=CV_PROFILE_ID,
        source_profile_version=1,
        source_target_id=ROLE_PROFILE_A,
        source_target_version=ROLE_PROFILE_VERSION,
        source_gap_ids=[gap_id],
        source_evidence_refs=["cv-e2e-sql"],
        source_recommendation_refs=[f"recommendation:{gap_id}"],
        validation={"valid": True, "ready_for_review": True, "findings": []},
        reviewed=False,
        idempotency_key="e2e-historical-learning-path-08b1",
        request_fingerprint="e2e-historical-learning-path-08b1",
    )


def _locator(document_id: UUID, section: str = "experience") -> dict[str, object]:
    return SourceLocator(
        document_id=str(document_id), section=section, start_offset=0, end_offset=64
    ).model_dump(mode="json")


def _cv_output() -> CVFullExtractionOutputV2:
    evidence = CapabilityEvidence(
        source_excerpt="Delivered SQL reporting and REST API integrations.",
        source_locator=SourceLocator(
            document_id=str(CV_DOCUMENT_ID), section="experience", start_offset=0, end_offset=64
        ),
        evidence_strength=EvidenceStrength.DEMONSTRATED_IN_ROLE,
        confidence=0.96,
    )
    return CVFullExtractionOutputV2(
        candidate_summary="Deterministic E2E candidate",
        experience=[
            ExperienceItem(title="Integration Engineer", company="E2E Labs", evidence=[evidence])
        ],
        capabilities=[
            CapabilityItem(
                raw_name="SQL",
                canonical_name="SQL",
                evidence=[evidence],
                evidence_strength=EvidenceStrength.DEMONSTRATED_IN_ROLE,
            )
        ],
    )


def _requirements() -> list[RoleRequirement]:
    common: _CommonRequirement = {
        "classification": RequirementClassification.TRAINABLE_MANDATORY,
        "confidence_threshold": 0.8,
        "assessment_recommendation": "Review evidence against the requirement.",
        "rubric_version": "e2e-08b1",
        "priority": "high",
        "target_level": "working",
        "observable_behaviors": ["Can apply the requirement in a project."],
    }
    return [
        RoleRequirement(
            id="sql",
            criterion_dimension=CriterionDimension.SKILL,
            evidence_terms=["SQL"],
            **common,
        ),
        RoleRequirement(
            id="rest-api",
            criterion_dimension=CriterionDimension.SKILL,
            evidence_terms=["REST API design"],
            **common,
        ),
        RoleRequirement(
            id="pmp",
            criterion_dimension=CriterionDimension.CREDENTIAL,
            evidence_terms=["PMP"],
            **common,
        ),
    ]


def _jd_output() -> dict[str, object]:
    return {
        "requirements": [
            {
                "requirement_id": item.id,
                "statement": "; ".join(item.evidence_terms),
                "criterion_dimension": item.criterion_dimension.value
                if item.criterion_dimension
                else None,
                "modality": "must",
                "evidence_terms": item.evidence_terms,
                "confidence": 0.99,
                "evidence_status": "supported",
                "source_locator": {
                    "document_id": JD_SOURCE_DOCUMENT_ID,
                    "section": "requirements",
                    "start_offset": 0,
                    "end_offset": 64,
                },
                "source_excerpt": "; ".join(item.evidence_terms),
            }
            for item in _requirements()
        ]
    }


def _assessment(
    requirement_id: str,
    status: AssessmentEvidenceStatus,
    target_id: str,
    *,
    gap_identity: str,
    evidence: list[str] | None = None,
) -> tuple[RequirementAssessment, TargetGap]:
    details = AssessmentDecisionDetails(
        reason_codes=[status.value],
        observed_confidence=0.96 if status is AssessmentEvidenceStatus.SUPPORTED else 0.2,
        required_confidence=0.8,
        verification_required=status is AssessmentEvidenceStatus.REQUIRES_VERIFICATION,
        threshold_source="e2e-fixture",
    )
    refs = evidence or []
    assessment = RequirementAssessment(
        target_id=target_id,
        target_type=TargetType.CURRENT_ROLE,
        requirement_id=requirement_id,
        matched_evidence_refs=refs,
        missing_signals=[]
        if status is AssessmentEvidenceStatus.SUPPORTED
        else ["Evidence is missing."],
        rationale=f"E2E fixture assessment: {status.value}",
        preliminary_priority=PreliminaryPriority.HIGH,
        missing_priority_inputs=[],
        evidence_status=status,
        decision_details=details,
        recommendation="Review or learn this requirement.",
    )
    gap = TargetGap(
        id=f"e2e-gap-{gap_identity}-{target_id}-{requirement_id}",
        target_id=target_id,
        target_type=TargetType.CURRENT_ROLE,
        requirement_id=requirement_id,
        matched_evidence_refs=refs,
        missing_signals=assessment.missing_signals,
        rationale=assessment.rationale,
        preliminary_priority=assessment.preliminary_priority,
        missing_priority_inputs=[],
        evidence_status=status,
        decision_details=details,
        recommendation=assessment.recommendation,
    )
    return assessment, gap


def _portfolio(
    portfolio_id: str,
    target_id: str,
    target_version: str,
    statuses: dict[str, AssessmentEvidenceStatus],
) -> CombinedGapPortfolio:
    assessments: list[RequirementAssessment] = []
    gaps: list[TargetGap] = []
    for requirement_id, status in statuses.items():
        assessment, gap = _assessment(
            requirement_id,
            status,
            target_id,
            gap_identity=portfolio_id,
            evidence=["cv-e2e-sql"]
            if requirement_id == "sql" and status is AssessmentEvidenceStatus.SUPPORTED
            else None,
        )
        assessments.append(assessment)
        gaps.append(gap)
    return CombinedGapPortfolio(
        id=portfolio_id,
        cv_profile_id=CV_PROFILE_ID,
        cv_profile_version=1,
        current_target_version=target_version,
        owner_actor_id=ACTOR_ID,
        organization_id=ORG_ID,
        correlation_id=f"e2e-{portfolio_id}",
        candidate_id=CANDIDATE_ID,
        current_role=TargetGapAnalysis(
            target_id=target_id,
            target_type=TargetType.CURRENT_ROLE,
            usage_mode=TargetUsageMode.PREVIEW,
            assessments=assessments,
            gaps=gaps,
        ),
        snapshot_schema_version="capability-gap-v1",
    )


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    output_path = Path(os.environ.get("E2E_FIXTURE_MANIFEST_OUTPUT", "/tmp/e2e-fixtures.json"))
    now = datetime.now(UTC)
    db = Database(database_url)
    async with db.session() as session, session.begin():
        if await session.get(DocumentRecord, CV_DOCUMENT_ID) is None:
            for document_id, document_kind, _name in (
                (CV_DOCUMENT_ID, DocumentKind.CV, "e2e-cv.pdf"),
                (JD_DOCUMENT_ID, DocumentKind.JD, "e2e-jd.pdf"),
            ):
                session.add(
                    DocumentRecord(
                        id=document_id,
                        owner_actor_id=ACTOR_ID,
                        organization_id=ORG_ID,
                        document_kind=document_kind.value,
                        content_type="application/pdf",
                        byte_size=1,
                        sha256=hashlib.sha256(str(document_id).encode()).hexdigest(),
                        object_key=f"e2e/{document_id}",
                        status=DocumentStatus.CLEAN.value,
                        retention_until=now + timedelta(days=1),
                        created_at=now,
                    )
                )
        await session.flush()
        if await session.get(CandidateRecord, CANDIDATE_ID) is None:
            session.add(
                CandidateRecord(
                    id=CANDIDATE_ID,
                    candidate_code="CAN-E2E-08B1",
                    display_name="E2E Candidate",
                    primary_email=None,
                    primary_phone=None,
                    organization_id=ORG_ID,
                    created_by_actor_id=ACTOR_ID,
                    status=CandidateStatus.ACTIVE.value,
                    review_state=CandidateReviewState.ACCEPTED.value,
                    current_profile_id=CV_PROFILE_ID,
                    current_profile_version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
        if await session.get(CandidateProfileRecord, CANDIDATE_ID) is None:
            session.add(
                CandidateProfileRecord(
                    id=CANDIDATE_ID,
                    candidate_id=CANDIDATE_ID,
                    profile_id=CV_PROFILE_ID,
                    profile_version=1,
                    governance_version=1,
                    document_id=CV_DOCUMENT_ID,
                    review_state=CandidateReviewState.ACCEPTED.value,
                    linked_at=now,
                )
            )
        if await session.get(RoleRecord, ROLE_ID) is None:
            session.add(
                RoleRecord(
                    id=ROLE_ID,
                    organization_id=ORG_ID,
                    role_code=ROLE_CODE,
                    title="E2E Product Manager",
                    description="Deterministic role for read-only E2E smoke.",
                    status="active",
                    created_by=ACTOR_ID,
                    created_at=now,
                    updated_at=now,
                    active_role_profile_id=ROLE_PROFILE_A,
                )
            )
            await session.flush()
            session.add(
                RoleJDRecord(id=ROLE_JD_ID, role_id=ROLE_ID, created_at=now, updated_at=now)
            )
            session.add(
                RoleJDVersionRecord(
                    id=ROLE_JD_VERSION_ID,
                    role_jd_id=ROLE_JD_ID,
                    version=1,
                    document_id=JD_DOCUMENT_ID,
                    created_by=ACTOR_ID,
                    created_at=now,
                )
            )
        for job_id, profile_id, source_document_id, document_type, output, candidate_profile in (
            (
                "e2e-jd-job-08b1",
                JD_PROFILE_ID,
                JD_SOURCE_DOCUMENT_ID,
                "jd",
                _jd_output(),
                None,
            ),
            (
                "e2e-cv-job-08b1",
                CV_PROFILE_ID,
                CV_DOCUMENT_ID,
                "cv",
                _cv_output().model_dump(mode="json"),
                project_v2_to_candidate_profile(_cv_output()).model_dump(mode="json"),
            ),
        ):
            normalized = dict(output)
            if candidate_profile is not None:
                normalized["_candidate_profile"] = candidate_profile
            job = await session.get(ExtractionJobRecord, job_id)
            profile = await session.get(ExtractionProfileRecord, profile_id)
            if job is None:
                job = ExtractionJobRecord(
                    id=job_id,
                    document_id=source_document_id,
                    document_kind=document_type,
                    owner_actor_id=ACTOR_ID,
                    correlation_id=job_id,
                    status="succeeded",
                    profile_id=profile_id,
                )
                session.add(job)
            else:
                job.document_id = str(source_document_id)
                job.document_kind = document_type
                job.status = "succeeded"
                job.profile_id = profile_id
            if profile is None:
                session.add(
                    ExtractionProfileRecord(
                        id=profile_id,
                        job_id=job_id,
                        document_id=source_document_id,
                        document_kind=document_type,
                        owner_actor_id=ACTOR_ID,
                        version=1,
                        review_state=ReviewState.ACCEPTED.value,
                        accepted_by=ACTOR_ID,
                        accepted_at=now,
                        normalized_output=normalized,
                        audit_metadata={"pipeline": "e2e_fixture", "fixture": "cap-demo-08b1"},
                    )
                )
            else:
                profile.job_id = job_id
                profile.document_id = str(source_document_id)
                profile.document_kind = document_type
                profile.review_state = ReviewState.ACCEPTED.value
                profile.normalized_output = normalized
                profile.audit_metadata = {"pipeline": "e2e_fixture", "fixture": "cap-demo-08b1"}
        await session.flush()
        if await session.get(RoleProfileDraftRecord, ROLE_PROFILE_DRAFT_ID) is None:
            session.add(
                RoleProfileDraftRecord(
                    id=ROLE_PROFILE_DRAFT_ID,
                    source_jd_profile_id=JD_PROFILE_ID,
                    source_jd_profile_version=1,
                    owner_actor_id=ACTOR_ID,
                    organization_id=ORG_ID,
                    version=1,
                    status="draft",
                    title="E2E Product Manager Draft",
                    requirements=[item.model_dump(mode="json") for item in _requirements()],
                    quality_gate={"passed": True, "summary_findings": []},
                    approval_eligibility={
                        "can_create_draft": True,
                        "can_approve_provisional": False,
                        "can_approve_active": False,
                    },
                    source_schema="jd_requirement_extraction_v2",
                    source_version="1",
                    authoring_findings=[],
                    duplicate_candidate_groups=[],
                    role_id=ROLE_ID,
                    role_jd_version_id=ROLE_JD_VERSION_ID,
                    correlation_id="e2e-role-profile-draft-08b1",
                )
            )
        requirements = [item.model_dump(mode="json") for item in _requirements()]
        for profile_id, governance in ((ROLE_PROFILE_A, 1), (ROLE_PROFILE_B, 2)):
            if not await session.scalar(
                select(RoleCompetencyProfileRecord).where(
                    RoleCompetencyProfileRecord.id == profile_id
                )
            ):
                session.add(
                    RoleCompetencyProfileRecord(
                        record_id=f"{profile_id}@{ROLE_PROFILE_VERSION}",
                        id=profile_id,
                        version=ROLE_PROFILE_VERSION,
                        status=RoleProfileStatus.ACTIVE.value,
                        source_jd_profile_id=JD_PROFILE_ID,
                        source_jd_profile_version=1,
                        rule_set_version="e2e-08b1",
                        policy_version="e2e-08b1",
                        requirements=requirements,
                        role_id=ROLE_ID,
                        role_jd_version_id=ROLE_JD_VERSION_ID,
                        governance_version=governance,
                    )
                )
        portfolios = [
            _portfolio(
                "cap-demo-08b1-positive",
                ROLE_PROFILE_A,
                ROLE_PROFILE_VERSION,
                {
                    "sql": AssessmentEvidenceStatus.SUPPORTED,
                    "rest-api": AssessmentEvidenceStatus.INSUFFICIENT,
                    "pmp": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                },
            ),
            _portfolio(
                "cap-demo-08b1-negative",
                ROLE_PROFILE_A,
                ROLE_PROFILE_VERSION,
                {
                    "sql": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                    "rest-api": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                    "pmp": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                },
            ),
            _portfolio(
                "cap-demo-08b1-historical",
                ROLE_PROFILE_A,
                ROLE_PROFILE_VERSION,
                {
                    "sql": AssessmentEvidenceStatus.SUPPORTED,
                    "rest-api": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                    "pmp": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                },
            ),
            _portfolio(
                "cap-demo-08b1-comparison",
                ROLE_PROFILE_A,
                ROLE_PROFILE_VERSION,
                {
                    "sql": AssessmentEvidenceStatus.SUPPORTED,
                    "rest-api": AssessmentEvidenceStatus.SUPPORTED,
                    "pmp": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                },
            ),
            _portfolio(
                "cap-demo-08b1-cross-a",
                ROLE_PROFILE_A,
                ROLE_PROFILE_VERSION,
                {
                    "sql": AssessmentEvidenceStatus.SUPPORTED,
                    "rest-api": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                    "pmp": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                },
            ),
            _portfolio(
                "cap-demo-08b1-cross-b",
                ROLE_PROFILE_B,
                ROLE_PROFILE_VERSION,
                {
                    "sql": AssessmentEvidenceStatus.SUPPORTED,
                    "rest-api": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                    "pmp": AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
                },
            ),
        ]
        for portfolio in portfolios:
            if await session.get(CapabilityGapPortfolioRecord, portfolio.id) is not None:
                continue
            session.add(
                CapabilityGapPortfolioRecord(
                    id=portfolio.id,
                    cv_profile_id=portfolio.cv_profile_id,
                    cv_profile_version=portfolio.cv_profile_version,
                    current_target_id=portfolio.current_role.target_id,
                    current_target_version=portfolio.current_target_version,
                    current_usage_mode=portfolio.current_role.usage_mode.value,
                    future_target_id=None,
                    future_target_version=None,
                    future_usage_mode=None,
                    owner_actor_id=str(portfolio.owner_actor_id),
                    organization_id=str(portfolio.organization_id),
                    correlation_id=portfolio.correlation_id,
                    candidate_id=str(portfolio.candidate_id),
                    analysis_status=portfolio.analysis_status.value,
                    analysis_version=portfolio.analysis_version,
                    idempotency_key=portfolio.idempotency_key,
                    snapshot_schema_version=portfolio.snapshot_schema_version,
                    preview_readiness=None,
                    verification_queue=[],
                    semantic_policy=None,
                )
            )
            await session.flush()
            for assessment in portfolio.current_role.assessments:
                session.add(
                    RequirementAssessmentRecord(
                        record_id=f"{portfolio.id}:{assessment.target_type.value}:{assessment.requirement_id}",
                        portfolio_id=portfolio.id,
                        target_id=assessment.target_id,
                        target_type=assessment.target_type.value,
                        requirement_id=assessment.requirement_id,
                        payload=assessment.model_dump(mode="json"),
                    )
                )
            for gap in portfolio.current_role.gaps:
                session.add(
                    TargetGapRecord(
                        id=gap.id,
                        portfolio_id=portfolio.id,
                        target_id=gap.target_id,
                        target_type=gap.target_type.value,
                        requirement_id=gap.requirement_id,
                        payload=gap.model_dump(mode="json"),
                    )
                )
            session.add(
                CapabilityGapAuditEventRecord(
                    id=f"{portfolio.id}:created",
                    portfolio_id=portfolio.id,
                    action="E2E_FIXTURE_CREATED",
                    audit_metadata={"fixture": "cap-demo-08b1", "provider_calls": 0},
                )
            )
        expected_historical_learning_path = _historical_learning_path_record()
        historical_learning_path = await session.get(
            LearningPathRecord, (HISTORICAL_LEARNING_PATH_ID, 1)
        )
        if historical_learning_path is None:
            session.add(expected_historical_learning_path)
        else:
            # Repair only this deterministic fixture's subject binding; do not
            # create a second row when a previous bootstrap already inserted it.
            historical_learning_path.subject_id = expected_historical_learning_path.subject_id
    await db.dispose()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            fixture_manifest(),
            indent=2,
        )
        + "\n"
    )
    print(output_path)


if __name__ == "__main__":
    asyncio.run(main())
