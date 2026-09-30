"""Research-only experiment contracts for fair instructional-design comparisons."""

from datetime import datetime
from enum import StrEnum
from statistics import mean, median, stdev
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.instructional_design.schemas import (
    AssessmentDependencyCandidate,
    AssessmentSpec,
    CourseOutline,
    InstructionalDesignQualityReport,
    InstructionalDesignResearchSnapshot,
    LearningObjectiveSpec,
    LessonSpec,
    PrerequisiteSpec,
    ResearchLearningBrief,
)
from app.model_gateway.contracts import InferenceAuditMetadata

DEPENDENCY_NORMALIZER_VERSION = "id02d.2@0.1"


class ExperimentCondition(StrEnum):
    ONE_SHOT = "one_shot"
    STRUCTURED = "structured"
    STRUCTURED_V03 = "structured_v0.3"
    STRUCTURED_V031 = "structured_v0.3.1"


class ExperimentRunStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class EditEffort(StrEnum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    REWRITE_REQUIRED = "rewrite_required"


class GenerationConfig(BaseModel):
    """Shared provider settings; unsupported fields are recorded, never invented."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    temperature: float | None = Field(default=None, ge=0)
    top_p: float | None = Field(default=None, gt=0, le=1)
    max_output_tokens: int | None = Field(default=None, gt=0)
    seed: int | None = None
    unsupported_fields: list[str] = Field(default_factory=list)


class PromptSchemaVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    schema_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: str = Field(min_length=1)
    experiment_version: str = Field(min_length=1)
    fixture_ids: list[str] = Field(min_length=1)
    runs_per_fixture_per_condition: int = Field(default=3, gt=0)
    conditions: tuple[ExperimentCondition, ...] = (
        ExperimentCondition.ONE_SHOT,
        ExperimentCondition.STRUCTURED,
    )
    model_provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_revision: str | None = None
    generation_config: GenerationConfig
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    dependency_normalizer_version: str = Field(min_length=1)
    prompt_schema_versions: list[PromptSchemaVersion] = Field(min_length=1)


class ExperimentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: str
    experiment_version: str
    fixture_count: int = Field(ge=0)
    fixture_ids: list[str]
    conditions: tuple[ExperimentCondition, ...]
    runs_per_fixture_per_condition: int = Field(gt=0)
    model_provider: str
    model_name: str
    model_revision: str | None
    generation_config: GenerationConfig
    policy_id: str
    policy_version: str
    # Historical Smoke-2/Smoke-3 manifests predate ID-02D.2. They remain
    # readable, but execution preflight rejects them until metadata is present.
    dependency_normalizer_version: str | None = None
    prompt_schema_versions: list[PromptSchemaVersion]
    estimated_model_call_count: int = Field(ge=0)


def build_experiment_manifest(config: ExperimentConfig) -> ExperimentManifest:
    validate_experiment_manifest_preflight(config)
    calls_per_fixture_run = sum(
        1 if condition is ExperimentCondition.ONE_SHOT else 5
        for condition in config.conditions
    )
    return ExperimentManifest(
        experiment_id=config.experiment_id,
        experiment_version=config.experiment_version,
        fixture_count=len(config.fixture_ids),
        fixture_ids=list(config.fixture_ids),
        conditions=config.conditions,
        runs_per_fixture_per_condition=config.runs_per_fixture_per_condition,
        model_provider=config.model_provider,
        model_name=config.model_name,
        model_revision=config.model_revision,
        generation_config=config.generation_config,
        policy_id=config.policy_id,
        policy_version=config.policy_version,
        dependency_normalizer_version=config.dependency_normalizer_version,
        prompt_schema_versions=list(config.prompt_schema_versions),
        estimated_model_call_count=(
            len(config.fixture_ids) * calls_per_fixture_run * config.runs_per_fixture_per_condition
        ),
    )


def validate_experiment_manifest_preflight(config: ExperimentConfig) -> None:
    """Validate required provenance before any experiment model call."""

    required_values = {
        "experiment_id": config.experiment_id,
        "experiment_version": config.experiment_version,
        "model_provider": config.model_provider,
        "model_name": config.model_name,
        "policy_id": config.policy_id,
        "policy_version": config.policy_version,
        "dependency_normalizer_version": config.dependency_normalizer_version,
    }
    missing = [
        name
        for name, value in required_values.items()
        if not isinstance(value, str) or not value.strip()
    ]
    if missing:
        raise ValueError(
            "experiment manifest provenance is incomplete: " + ", ".join(missing)
        )
    if not config.fixture_ids or any(
        not isinstance(fixture_id, str) or not fixture_id.strip()
        for fixture_id in config.fixture_ids
    ):
        raise ValueError("experiment manifest provenance is incomplete: fixture_ids")
    if not config.prompt_schema_versions:
        raise ValueError(
            "experiment manifest provenance is incomplete: prompt_schema_versions"
        )
    for index, item in enumerate(config.prompt_schema_versions):
        values = {
            "prompt_id": item.prompt_id,
            "prompt_version": item.prompt_version,
            "schema_id": item.schema_id,
            "schema_version": item.schema_version,
        }
        missing_fields = [
            name
            for name, value in values.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if missing_fields:
            raise ValueError(
                "experiment manifest provenance is incomplete at prompt_schema_versions["
                f"{index}]: {', '.join(missing_fields)}"
            )


def validate_manifest_for_execution(manifest: ExperimentManifest) -> str:
    """Reject historical/incomplete manifests before any model call."""

    version = manifest.dependency_normalizer_version
    if not version or not version.strip():
        raise ValueError(
            "experiment manifest provenance is incomplete: dependency_normalizer_version"
        )
    return version


class ExperimentRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    experiment_version: str = Field(min_length=1)
    fixture_id: str = Field(min_length=1)
    condition: ExperimentCondition
    run_number: int = Field(ge=1)
    model_provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_revision: str | None = None
    generation_config: GenerationConfig
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    prompt_schema_versions: list[PromptSchemaVersion] = Field(min_length=1)
    started_at: datetime

    @classmethod
    def from_config(
        cls,
        *,
        run_id: str,
        config: ExperimentConfig,
        fixture_id: str,
        condition: ExperimentCondition,
        run_number: int,
        started_at: datetime,
    ) -> "ExperimentRun":
        if fixture_id not in config.fixture_ids:
            raise ValueError("fixture_id is not part of the experiment configuration")
        if condition not in config.conditions:
            raise ValueError("condition is not part of the experiment configuration")
        return cls(
            run_id=run_id,
            experiment_id=config.experiment_id,
            experiment_version=config.experiment_version,
            fixture_id=fixture_id,
            condition=condition,
            run_number=run_number,
            model_provider=config.model_provider,
            model_name=config.model_name,
            model_revision=config.model_revision,
            generation_config=config.generation_config,
            policy_id=config.policy_id,
            policy_version=config.policy_version,
            prompt_schema_versions=list(config.prompt_schema_versions),
            started_at=started_at,
        )


class StageFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    stage: str = Field(min_length=1)
    failure_class: str = Field(min_length=1)
    validation_error: str | None = None
    retry_count: int = Field(ge=0)


class ExperimentPartialArtifacts(BaseModel):
    """Safe typed output retained after a stage fails; it is never a passing snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    objectives: list[LearningObjectiveSpec] = Field(default_factory=list)
    assessments: list[AssessmentSpec] = Field(default_factory=list)
    dependency_candidates: list[AssessmentDependencyCandidate] = Field(default_factory=list)
    prerequisites: list[PrerequisiteSpec] = Field(default_factory=list)
    course_outline: CourseOutline | None = None
    lessons: list[LessonSpec] = Field(default_factory=list)


class ExperimentRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run: ExperimentRun
    status: ExperimentRunStatus
    snapshot: InstructionalDesignResearchSnapshot | None = None
    partial_artifacts: ExperimentPartialArtifacts | None = None
    stage_failure: StageFailure | None = None
    model_audits: list[InferenceAuditMetadata] = Field(default_factory=list)
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def completed_and_failed_runs_have_explicit_shapes(self) -> "ExperimentRunResult":
        if self.status is ExperimentRunStatus.COMPLETED and (
            self.snapshot is None or self.stage_failure is not None
        ):
            raise ValueError("completed run requires a snapshot and no stage failure")
        if self.status is ExperimentRunStatus.FAILED and (
            self.stage_failure is None or self.snapshot is not None
        ):
            raise ValueError("failed run requires stage failure and cannot have a passing snapshot")
        return self


class HumanEvaluationScores(BaseModel):
    """Ordinal human scores: 1 poor, 2 weak, 3 acceptable, 4 good, 5 strong."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    objective_measurability: int = Field(ge=1, le=5)
    objective_assessment_alignment: int = Field(ge=1, le=5)
    cognitive_alignment: int = Field(ge=1, le=5)
    evidence_validity: int = Field(ge=1, le=5)
    prerequisite_quality: int = Field(ge=1, le=5)
    sequence_coherence: int = Field(ge=1, le=5)
    instruction_assessment_alignment: int = Field(ge=1, le=5)
    under_teaching: int = Field(ge=1, le=5)
    over_teaching: int = Field(ge=1, le=5)
    overall_edit_effort: int = Field(ge=1, le=5)


class HumanEvaluation(BaseModel):
    """Human-owned evaluation keyed only by run ID, not generation condition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: str = Field(min_length=1)
    source: Literal["human"] = "human"
    reviewer_id: str = Field(min_length=1)
    reviewed_at: datetime
    scores: HumanEvaluationScores
    edit_effort: EditEffort
    objectives_changed: int | None = Field(default=None, ge=0)
    assessments_changed: int | None = Field(default=None, ge=0)
    prerequisites_changed: int | None = Field(default=None, ge=0)
    modules_changed: int | None = Field(default=None, ge=0)
    lessons_changed: int | None = Field(default=None, ge=0)
    notes: str | None = None


class BlindedInstructionalDesignArtifact(BaseModel):
    """Reviewable design only; excludes gate and generation metadata that reveal condition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    brief: ResearchLearningBrief
    objectives: list[LearningObjectiveSpec]
    assessments: list[AssessmentSpec]
    prerequisites: list[PrerequisiteSpec]
    course_outline: CourseOutline | None
    lessons: list[LessonSpec]


class BlindedReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    review_id: str = Field(min_length=1)
    artifact: BlindedInstructionalDesignArtifact
    rubric_version: str = "instructional_design_human_rubric@0.1"
    special_review_question: str = (
        "Ignoring machine traceability or schema issues, is this instructional design "
        "pedagogically reasonable?"
    )


def build_blinded_review_payload(
    result: ExperimentRunResult, *, review_id: str
) -> BlindedReviewPayload:
    if result.snapshot is None:
        raise ValueError("cannot blind-review a failed run without a snapshot")
    return BlindedReviewPayload(
        review_id=review_id,
        artifact=BlindedInstructionalDesignArtifact(
            brief=result.snapshot.brief,
            objectives=result.snapshot.objectives,
            assessments=result.snapshot.assessments,
            prerequisites=result.snapshot.prerequisites,
            course_outline=result.snapshot.course_outline,
            lessons=result.snapshot.lessons,
        ),
    )


class ExperimentComparison(BaseModel):
    """Per-fixture descriptive comparison; it deliberately contains no verdict."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fixture_id: str = Field(min_length=1)
    one_shot_runs: list[ExperimentRunResult] = Field(default_factory=list)
    structured_runs: list[ExperimentRunResult] = Field(default_factory=list)
    human_evaluations: list[HumanEvaluation] = Field(default_factory=list)

    @model_validator(mode="after")
    def runs_and_reviews_are_bound_to_this_fixture(self) -> "ExperimentComparison":
        runs = [*self.one_shot_runs, *self.structured_runs]
        if any(run.run.fixture_id != self.fixture_id for run in runs):
            raise ValueError("comparison runs must share the comparison fixture_id")
        if any(run.run.condition is not ExperimentCondition.ONE_SHOT for run in self.one_shot_runs):
            raise ValueError("one_shot_runs must contain only one_shot condition runs")
        if any(
            run.run.condition
            not in {
                ExperimentCondition.STRUCTURED,
                ExperimentCondition.STRUCTURED_V03,
                ExperimentCondition.STRUCTURED_V031,
            }
            for run in self.structured_runs
        ):
            raise ValueError("structured_runs must contain only structured condition runs")
        run_ids = {run.run.run_id for run in runs}
        if any(review.run_id not in run_ids for review in self.human_evaluations):
            raise ValueError("human evaluations must reference a comparison run")
        return self


def build_experiment_comparisons(
    results: list[ExperimentRunResult],
    human_evaluations: list[HumanEvaluation] | None = None,
) -> list[ExperimentComparison]:
    """Group immutable runs by fixture without deriving a score or winner."""

    evaluations_by_run = {
        evaluation.run_id: evaluation for evaluation in human_evaluations or []
    }
    comparisons: list[ExperimentComparison] = []
    for fixture_id in sorted({result.run.fixture_id for result in results}):
        fixture_runs = [result for result in results if result.run.fixture_id == fixture_id]
        fixture_run_ids = {result.run.run_id for result in fixture_runs}
        comparisons.append(
            ExperimentComparison(
                fixture_id=fixture_id,
                one_shot_runs=[
                    result
                    for result in fixture_runs
                    if result.run.condition is ExperimentCondition.ONE_SHOT
                ],
                structured_runs=[
                    result
                    for result in fixture_runs
                    if result.run.condition
                    in {
                        ExperimentCondition.STRUCTURED,
                        ExperimentCondition.STRUCTURED_V03,
                        ExperimentCondition.STRUCTURED_V031,
                    }
                ],
                human_evaluations=[
                    evaluation
                    for run_id, evaluation in evaluations_by_run.items()
                    if run_id in fixture_run_ids
                ],
            )
        )
    return comparisons


class NumericSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    count: int = Field(ge=0)
    mean: float | None = None
    median: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    standard_deviation: float | None = None


def _numeric_summary(values: list[float]) -> NumericSummary:
    return NumericSummary(
        count=len(values),
        mean=mean(values) if values else None,
        median=median(values) if values else None,
        minimum=min(values) if values else None,
        maximum=max(values) if values else None,
        standard_deviation=stdev(values) if len(values) > 1 else None,
    )


class ConditionExperimentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    quality_gate_pass_rate: float | None = Field(default=None, ge=0, le=1)
    objective_coverage: NumericSummary
    assessment_coverage: NumericSummary
    finding_counts_by_code: dict[str, int] = Field(default_factory=dict)
    finding_counts_by_severity: dict[str, int] = Field(default_factory=dict)
    unresolved_prerequisite_count: NumericSummary


class ExperimentAggregation(BaseModel):
    """Descriptive comparison only; no composite score or automatic winner exists."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    by_condition: dict[ExperimentCondition, ConditionExperimentSummary]


def _summarize_condition(results: list[ExperimentRunResult]) -> ConditionExperimentSummary:
    snapshots = [result.snapshot for result in results if result.snapshot is not None]
    reports: list[InstructionalDesignQualityReport] = [
        snapshot.quality_report for snapshot in snapshots
    ]
    finding_counts_by_code: dict[str, int] = {}
    finding_counts_by_severity: dict[str, int] = {}
    for report in reports:
        for finding in report.findings:
            finding_counts_by_code[finding.code] = finding_counts_by_code.get(finding.code, 0) + 1
            severity = finding.severity.value
            finding_counts_by_severity[severity] = finding_counts_by_severity.get(severity, 0) + 1
    return ConditionExperimentSummary(
        run_count=len(results),
        completed_count=len(snapshots),
        failed_count=sum(result.status is ExperimentRunStatus.FAILED for result in results),
        quality_gate_pass_rate=(
            sum(report.passed for report in reports) / len(reports) if reports else None
        ),
        objective_coverage=_numeric_summary([report.objective_coverage for report in reports]),
        assessment_coverage=_numeric_summary([report.assessment_coverage for report in reports]),
        finding_counts_by_code=finding_counts_by_code,
        finding_counts_by_severity=finding_counts_by_severity,
        unresolved_prerequisite_count=_numeric_summary(
            [float(len(report.unresolved_prerequisites)) for report in reports]
        ),
    )


def aggregate_experiment_results(results: list[ExperimentRunResult]) -> ExperimentAggregation:
    return ExperimentAggregation(
        by_condition={
            condition: _summarize_condition(
                [result for result in results if result.run.condition is condition]
            )
            for condition in ExperimentCondition
        }
    )
