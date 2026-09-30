"""Research-only typed instructional-design adapters over ModelGateway."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03,
    LESSON_PLANNING_SCHEMA_ID,
    OBJECTIVE_DESIGN_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_VERSION,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
    AssessmentDesignOutput,
    CoursePlanningOutput,
    LearningObjectiveDesignOutput,
    LessonPlanningOutput,
    OneShotInstructionalDesignOutput,
    PrerequisiteProposalOutput,
)
from app.instructional_design.practice_coverage import planner_coverage_requirements
from app.instructional_design.schemas import (
    AssessmentDependencyCandidate,
    AssessmentSpec,
    CourseOutline,
    LearningObjectiveSpec,
    PrerequisiteSpec,
    ResearchLearningBrief,
)
from app.instructional_design.workload import WorkloadBudgetContext
from app.model_gateway.contracts import (
    DataClassification,
    InferenceAuditMetadata,
    InferencePurpose,
    InferenceRequest,
    ModelGateway,
    OutputContract,
)

T = TypeVar("T", bound=BaseModel)


@dataclass
class _GatewayContext:
    gateway: ModelGateway
    requested_provider: str
    correlation_id: str
    output_token_budget: int | None
    temperature: float | None
    model_audits: list[InferenceAuditMetadata] = field(default_factory=list)

    async def infer(
        self,
        *,
        prompt_id: str,
        prompt_version: str,
        output_schema: type[T],
        payload: dict[str, object],
    ) -> T:
        response = await self.gateway.infer_structured(
            InferenceRequest(
                purpose=InferencePurpose.LEARNING_CONTENT_GENERATION,
                data_classification=DataClassification.PUBLIC,
                prompt_template_id=prompt_id,
                prompt_template_version=prompt_version,
                payload=payload,
                output_contract=OutputContract(
                    schema_id=prompt_id,
                    schema_version=prompt_version,
                ),
                requested_provider=self.requested_provider,
                temperature=self.temperature,
                output_token_budget=self.output_token_budget,
                correlation_id=f"{self.correlation_id}:{prompt_id}",
            ),
            output_schema,
        )
        self.model_audits.append(response.audit)
        return response.parsed


def _brief_payload(brief: ResearchLearningBrief) -> dict[str, object]:
    return {"brief": brief.model_dump(mode="json")}


@dataclass
class ModelGatewayOneShotInstructionalDesignGenerator:
    gateway: ModelGateway
    requested_provider: str
    correlation_id: str
    output_token_budget: int | None = None
    temperature: float | None = None
    _context: _GatewayContext = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._context = _GatewayContext(
            gateway=self.gateway,
            requested_provider=self.requested_provider,
            correlation_id=self.correlation_id,
            output_token_budget=self.output_token_budget,
            temperature=self.temperature,
        )

    @property
    def model_audits(self) -> Sequence[InferenceAuditMetadata]:
        return self._context.model_audits

    async def generate(self, brief: ResearchLearningBrief) -> OneShotInstructionalDesignOutput:
        return await self._context.infer(
            prompt_id=ONE_SHOT_BASELINE_SCHEMA_ID,
            prompt_version=ONE_SHOT_BASELINE_SCHEMA_VERSION,
            output_schema=OneShotInstructionalDesignOutput,
            payload=_brief_payload(brief),
        )


@dataclass
class ModelGatewayStructuredDesigners:
    gateway: ModelGateway
    requested_provider: str
    correlation_id: str
    output_token_budget: int | None = None
    temperature: float | None = None
    stage_version: str = INSTRUCTIONAL_DESIGN_STAGE_VERSION
    _context: _GatewayContext = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._context = _GatewayContext(
            gateway=self.gateway,
            requested_provider=self.requested_provider,
            correlation_id=self.correlation_id,
            output_token_budget=self.output_token_budget,
            temperature=self.temperature,
        )

    @property
    def model_audits(self) -> Sequence[InferenceAuditMetadata]:
        return self._context.model_audits

    @property
    def objective(self) -> "_ObjectiveDesigner":
        return _ObjectiveDesigner(self._context, self.stage_version)

    @property
    def assessment(self) -> "_AssessmentDesigner":
        return _AssessmentDesigner(self._context, self.stage_version)

    @property
    def prerequisite(self) -> "_PrerequisiteDesigner":
        return _PrerequisiteDesigner(self._context, self.stage_version)

    @property
    def course(self) -> "_CourseDesigner":
        return _CourseDesigner(self._context, self.stage_version)

    @property
    def lesson(self) -> "_LessonDesigner":
        return _LessonDesigner(self._context, self.stage_version)


@dataclass(frozen=True)
class _ObjectiveDesigner:
    context: _GatewayContext
    stage_version: str

    async def propose(self, brief: ResearchLearningBrief) -> LearningObjectiveDesignOutput:
        return await self.context.infer(
            prompt_id=OBJECTIVE_DESIGN_SCHEMA_ID,
            prompt_version=self.stage_version,
            output_schema=LearningObjectiveDesignOutput,
            payload=_brief_payload(brief),
        )


@dataclass(frozen=True)
class _AssessmentDesigner:
    context: _GatewayContext
    stage_version: str

    async def propose(
        self, brief: ResearchLearningBrief, objectives: Sequence[LearningObjectiveSpec]
    ) -> AssessmentDesignOutput:
        return await self.context.infer(
            prompt_id=ASSESSMENT_DESIGN_SCHEMA_ID,
            prompt_version=self.stage_version,
            output_schema=AssessmentDesignOutput,
            payload={
                **_brief_payload(brief),
                "objectives": [item.model_dump(mode="json") for item in objectives],
                "allowed_references": {
                    "objective_ids": [item.id for item in objectives],
                },
            },
        )


@dataclass(frozen=True)
class _PrerequisiteDesigner:
    context: _GatewayContext
    stage_version: str

    async def propose(
        self,
        brief: ResearchLearningBrief,
        objectives: Sequence[LearningObjectiveSpec],
        assessments: Sequence[AssessmentSpec],
        dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
    ) -> PrerequisiteProposalOutput:
        result = await self.context.infer(
            prompt_id=PREREQUISITE_PROPOSAL_SCHEMA_ID,
            prompt_version=self.stage_version,
            output_schema=PrerequisiteProposalOutput,
            payload={
                **_brief_payload(brief),
                "objectives": [item.model_dump(mode="json") for item in objectives],
                "assessments": [item.model_dump(mode="json") for item in assessments],
                "dependency_candidates": [
                    item.model_dump(mode="json") for item in dependency_candidates
                ],
            },
        )
        if self.stage_version.startswith(INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03):
            from app.instructional_design.contracts import validate_v03_prerequisite_proposals

            validate_v03_prerequisite_proposals(result)
        return result


@dataclass(frozen=True)
class _CourseDesigner:
    context: _GatewayContext
    stage_version: str

    async def propose(
        self,
        brief: ResearchLearningBrief,
        objectives: Sequence[LearningObjectiveSpec],
        assessments: Sequence[AssessmentSpec],
        prerequisites: Sequence[PrerequisiteSpec],
        dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
        workload_context: WorkloadBudgetContext | None = None,
    ) -> CoursePlanningOutput:
        return await self.context.infer(
            prompt_id=COURSE_PLANNING_SCHEMA_ID,
            prompt_version=self.stage_version,
            output_schema=CoursePlanningOutput,
            payload={
                **_brief_payload(brief),
                "objectives": [item.model_dump(mode="json") for item in objectives],
                "assessments": [item.model_dump(mode="json") for item in assessments],
                "prerequisites": [item.model_dump(mode="json") for item in prerequisites],
                "dependency_candidates": [
                    item.model_dump(mode="json") for item in dependency_candidates
                ],
                "workload_budget_context": workload_context.model_dump(mode="json") if workload_context else None,
                "practice_coverage_requirements": planner_coverage_requirements(assessments),
                "allowed_references": {
                    "objective_ids": [item.id for item in objectives],
                    "assessment_ids": [item.id for item in assessments],
                    "prerequisite_ids": [item.id for item in prerequisites],
                    "lesson_ids": [],
                },
            },
        )


@dataclass(frozen=True)
class _LessonDesigner:
    context: _GatewayContext
    stage_version: str

    async def propose(
        self,
        brief: ResearchLearningBrief,
        objectives: Sequence[LearningObjectiveSpec],
        assessments: Sequence[AssessmentSpec],
        prerequisites: Sequence[PrerequisiteSpec],
        course_outline: CourseOutline,
        dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
        module_objective_scope: Mapping[str, Sequence[str]] | None = None,
        workload_context: WorkloadBudgetContext | None = None,
    ) -> LessonPlanningOutput:
        return await self.context.infer(
            prompt_id=LESSON_PLANNING_SCHEMA_ID,
            prompt_version=self.stage_version,
            output_schema=LessonPlanningOutput,
            payload={
                **_brief_payload(brief),
                "objectives": [item.model_dump(mode="json") for item in objectives],
                "assessments": [item.model_dump(mode="json") for item in assessments],
                "prerequisites": [item.model_dump(mode="json") for item in prerequisites],
                "course_outline": course_outline.model_dump(mode="json"),
                "dependency_candidates": [
                    item.model_dump(mode="json") for item in dependency_candidates
                ],
                "workload_budget_context": workload_context.model_dump(mode="json") if workload_context else None,
                "practice_coverage_requirements": planner_coverage_requirements(assessments),
                "allowed_references": {
                    "module_ids": [item.id for item in course_outline.modules],
                    "objective_ids": [item.id for item in objectives],
                    "objective_ids_by_module": {
                        module_id: list(objective_ids)
                        for module_id, objective_ids in (module_objective_scope or {}).items()
                    },
                    "assessment_ids": [item.id for item in assessments],
                    "prerequisite_ids": [item.id for item in prerequisites],
                },
            },
        )
