from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictSourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SourceIdentity(StrictSourceModel):
    source_system: str = Field(min_length=1, max_length=64)
    employee_ref: str = Field(min_length=1, max_length=255)


class SourceSnapshotMetadata(StrictSourceModel):
    source_updated_at: datetime | None = None
    source_version: str | int | None = None
    source_snapshot_ref: str | None = Field(default=None, max_length=255)


class CareerRecord(StrictSourceModel):
    source_record_ref: str | None = Field(default=None, max_length=255)
    company: str | None = None
    role: str | None = None
    department: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    responsibilities: str | None = None
    technologies: list[str] = Field(default_factory=list)


class EducationRecord(StrictSourceModel):
    source_record_ref: str | None = Field(default=None, max_length=255)
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str | None = None


class CertificationRecord(StrictSourceModel):
    source_record_ref: str | None = Field(default=None, max_length=255)
    name: str | None = None
    issuer: str | None = None
    issued_at: str | None = None
    expires_at: str | None = None
    source_verification_status: str | None = None


class NamedSourceRecord(StrictSourceModel):
    source_record_ref: str | None = Field(default=None, max_length=255)
    name: str = Field(min_length=1)
    description: str | None = None
    source_value: str | None = None


class LanguageRecord(StrictSourceModel):
    source_record_ref: str | None = Field(default=None, max_length=255)
    name: str = Field(min_length=1)
    proficiency: str | None = None
    scale: str | None = None


class InterviewCriterion(StrictSourceModel):
    source_criterion_ref: str | None = None
    name: str | None = None
    score: str | int | float | None = None
    score_scale: str | None = None
    comment: str | None = None
    evaluator_ref: str | None = None


class InterviewRecord(StrictSourceModel):
    source_record_ref: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None
    round_name: str | None = None
    evaluator_ref: str | None = None
    recommendation: str | None = None
    score: str | int | float | None = None
    score_scale: str | None = None
    comment: str | None = None
    criteria: list[InterviewCriterion] = Field(default_factory=list)


class AssessmentDimension(StrictSourceModel):
    source_dimension_ref: str | None = None
    name: str | None = None
    score: str | int | float | None = None
    score_scale: str | None = None
    result: str | None = None


class AssessmentRecord(StrictSourceModel):
    source_record_ref: str | None = Field(default=None, max_length=255)
    assessment_type: str | None = None
    name: str | None = None
    occurred_at: datetime | None = None
    result: str | None = None
    score: str | int | float | None = None
    score_scale: str | None = None
    report_ref: str | None = None
    dimensions: list[AssessmentDimension] = Field(default_factory=list)


class ATSScanningSignal(StrictSourceModel):
    job_ref: str | None = None
    score: float | None = None
    reason: str | None = None
    keywords_found: list[str] = Field(default_factory=list)
    keywords_missing: list[str] = Field(default_factory=list)


class CandidateSourceFields(StrictSourceModel):
    schema_id: Literal["pai.candidate-source"]
    schema_version: Literal["v1"]
    company: str = Field(min_length=1)
    department: str | None = None
    identity: SourceIdentity
    career_history: list[CareerRecord] = Field(default_factory=list)
    education: list[EducationRecord] = Field(default_factory=list)
    certifications: list[CertificationRecord] = Field(default_factory=list)
    tools: list[NamedSourceRecord] = Field(default_factory=list)
    languages: list[LanguageRecord] = Field(default_factory=list)
    projects: list[NamedSourceRecord] = Field(default_factory=list)
    interviews: list[InterviewRecord] = Field(default_factory=list)
    assessments: list[AssessmentRecord] = Field(default_factory=list)
    ats_ai_scanning: ATSScanningSignal | None = None


class CandidateSourceEnvelope(CandidateSourceFields):
    """Internal projection; API adapters map the upstream snapshot revision here."""

    source_revision: int = Field(gt=0)
    source_snapshot: SourceSnapshotMetadata = Field(default_factory=SourceSnapshotMetadata)


class CandidateSourceProjectionSnapshot(StrictSourceModel):
    source_revision: int = Field(gt=0)
    source_updated_at: datetime | None = None
    source_version: str | int | None = None
    source_snapshot_ref: str | None = Field(default=None, max_length=255)

    @field_validator("source_updated_at", mode="before")
    @classmethod
    def parse_source_updated_at(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        return value


class CandidateSourceProjectionV1(CandidateSourceFields):
    """Legacy candidate-source transport; retained for existing snapshot callers."""

    snapshot: CandidateSourceProjectionSnapshot

    def to_candidate_source_envelope(self) -> CandidateSourceEnvelope:
        payload = self.model_dump(mode="python", exclude={"snapshot"})
        snapshot = self.snapshot
        return CandidateSourceEnvelope(
            **payload,
            source_revision=snapshot.source_revision,
            source_snapshot=SourceSnapshotMetadata(
                source_updated_at=snapshot.source_updated_at,
                source_version=snapshot.source_version,
                source_snapshot_ref=snapshot.source_snapshot_ref,
            ),
        )


class LearningProjectionIdentity(StrictSourceModel):
    employee_ref: str = Field(min_length=1, max_length=255)
    source_system: Literal["HRM"]

    @field_validator("employee_ref")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("employee_ref must not be blank")
        return value


def _parse_projection_timestamp(value: object) -> object:
    return CandidateSourceProjectionSnapshot.parse_source_updated_at(value)


class LearningProjectionSnapshot(StrictSourceModel):
    source_revision: int = Field(gt=0)
    source_updated_at: datetime | None = None

    _parse_timestamp = field_validator("source_updated_at", mode="before")(
        _parse_projection_timestamp
    )


class LearningEmploymentContext(StrictSourceModel):
    company: str = Field(min_length=1)
    department: str | None = None
    job_title: str | None = None
    designation_label: str | None = None
    grade_label: str | None = None
    date_of_joining: str | None = None

    @field_validator("company")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("company must not be blank")
        return value


class LearningTargetJobSource(StrictSourceModel):
    source_application_ref: str | None = None
    job_description_html: str | None = None
    job_requirements_html: str | None = None
    job_posting_url: str | None = None


class LearningCareerRecord(StrictSourceModel):
    source_record_ref: str | None = Field(default=None, max_length=255)
    company: str | None = None
    role: str | None = None
    department: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    responsibilities: str | None = None


class LearningCandidateSource(StrictSourceModel):
    career_history: list[LearningCareerRecord]
    education: list[EducationRecord]
    languages: list[LanguageRecord]
    tools: list[NamedSourceRecord]
    certifications: list[CertificationRecord]
    projects: list[NamedSourceRecord]


class LearningInterviewRecord(InterviewRecord):
    _parse_timestamp = field_validator("occurred_at", mode="before")(_parse_projection_timestamp)


class LearningAssessmentRecord(AssessmentRecord):
    _parse_timestamp = field_validator("occurred_at", mode="before")(_parse_projection_timestamp)


class LearningRecruitmentEvidence(StrictSourceModel):
    interviewer_feedback: list[LearningInterviewRecord]
    assessments: list[LearningAssessmentRecord]


class AtsAiProfileV1(StrictSourceModel):
    """Upstream assertions only, including recruiter verification, not Core decisions."""

    cv_match_score: float | None = None
    verified_by_recruiter: bool | None = None
    verified_by: str | None = None
    verified_at: datetime | None = None
    summary: str | None = None

    _parse_timestamp = field_validator("verified_at", mode="before")(_parse_projection_timestamp)


class LearningAuxiliarySignals(StrictSourceModel):
    current_application_ai_score: str | int | float | None = None
    ats_ai_profile: AtsAiProfileV1 | None = None
    ats_ai_scanning: ATSScanningSignal | None = None


class EmployeeLearningProjectionV1(StrictSourceModel):
    """PAI-specific full source snapshot, never an HR payload or semantic profile."""

    schema_id: Literal["pai.employee-learning-projection"]
    schema_version: Literal["1.0"]
    identity: LearningProjectionIdentity
    snapshot: LearningProjectionSnapshot
    employment_context: LearningEmploymentContext
    target_job_source: LearningTargetJobSource | None = None
    candidate_source: LearningCandidateSource
    recruitment_evidence: LearningRecruitmentEvidence
    auxiliary_signals: LearningAuxiliarySignals | None = None

    def source_payload(self) -> dict[str, object]:
        # Preserve omitted versus explicitly null fields and original list order.
        return self.model_dump(mode="json", exclude_unset=True)

    def content_fingerprint_payload(self) -> dict[str, object]:
        # Revision is ordering authority; timestamp is audit-only. Neither is content.
        return {key: value for key, value in self.source_payload().items() if key != "snapshot"}

    def to_candidate_source_envelope(self) -> CandidateSourceEnvelope:
        source = self.candidate_source
        return CandidateSourceEnvelope(
            schema_id="pai.candidate-source",
            schema_version="v1",
            identity=SourceIdentity(**self.identity.model_dump()),
            source_revision=self.snapshot.source_revision,
            source_snapshot=SourceSnapshotMetadata(
                source_updated_at=self.snapshot.source_updated_at
            ),
            company=self.employment_context.company,
            department=self.employment_context.department,
            career_history=[
                CareerRecord(**record.model_dump()) for record in source.career_history
            ],
            education=source.education,
            languages=source.languages,
            tools=source.tools,
            certifications=source.certifications,
            projects=source.projects,
            interviews=[
                InterviewRecord(**record.model_dump())
                for record in self.recruitment_evidence.interviewer_feedback
            ],
            assessments=[
                AssessmentRecord(**record.model_dump())
                for record in self.recruitment_evidence.assessments
            ],
            ats_ai_scanning=self.auxiliary_signals.ats_ai_scanning
            if self.auxiliary_signals
            else None,
        )
