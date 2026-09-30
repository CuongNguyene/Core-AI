from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.content_generation.prompts import (
    COURSE_GENERATION_PROMPT_ID,
    COURSE_GENERATION_PROMPT_VERSION,
    LESSON_GENERATION_PROMPT_ID,
    LESSON_GENERATION_PROMPT_VERSION,
    LESSON_REPAIR_PROMPT_ID,
    LESSON_REPAIR_PROMPT_VERSION,
)
from app.content_generation.schemas import GeneratedCourseDraft, GeneratedLessonDraft
from app.course_authoring.schemas import CourseAuthoringRequest
from app.model_gateway.contracts import (
    DataClassification,
    InferenceAuditMetadata,
    InferencePurpose,
    InferenceRequest,
    ModelGateway,
    OutputContract,
)

from .context import CourseGenerationContext
from .plan_schemas import CourseLessonPlan
from .repair import LessonRepairContext


class CourseContentGenerator(Protocol):
    async def generate(
        self,
        request: CourseAuthoringRequest,
        context: CourseGenerationContext,
    ) -> GeneratedCourseDraft: ...


@dataclass
class ModelGatewayCourseContentGenerator:
    gateway: ModelGateway
    requested_provider: str
    correlation_id: str
    output_token_budget: int | None = None
    temperature: float | None = None
    _audits: list[InferenceAuditMetadata] = field(default_factory=list, init=False)

    @property
    def model_audits(self) -> Sequence[InferenceAuditMetadata]:
        return self._audits

    async def generate(
        self,
        request: CourseAuthoringRequest,
        context: CourseGenerationContext,
    ) -> GeneratedCourseDraft:
        del request
        response = await self.gateway.infer_structured(
            InferenceRequest(
                purpose=InferencePurpose.LEARNING_CONTENT_GENERATION,
                data_classification=DataClassification.PUBLIC,
                prompt_template_id=COURSE_GENERATION_PROMPT_ID,
                prompt_template_version=COURSE_GENERATION_PROMPT_VERSION,
                payload=context.model_dump(mode="json"),
                output_contract=OutputContract(
                    schema_id=COURSE_GENERATION_PROMPT_ID,
                    schema_version=COURSE_GENERATION_PROMPT_VERSION,
                ),
                requested_provider=self.requested_provider,
                temperature=self.temperature,
                output_token_budget=self.output_token_budget,
                correlation_id=self.correlation_id,
            ),
            GeneratedCourseDraft,
        )
        self._audits.append(response.audit)
        return response.parsed


@dataclass
class ModelGatewayLessonContentGenerator:
    gateway: ModelGateway
    requested_provider: str
    correlation_id: str
    output_token_budget: int | None = None
    temperature: float | None = None
    _audits: list[InferenceAuditMetadata] = field(default_factory=list, init=False)

    @property
    def model_audits(self) -> Sequence[InferenceAuditMetadata]:
        return self._audits

    async def generate(
        self,
        lesson_plan: CourseLessonPlan | dict[str, object],
        context: CourseGenerationContext,
        prior_learning_summary: Sequence[dict[str, object]] = (),
        *,
        repair_context: LessonRepairContext | None = None,
    ) -> GeneratedLessonDraft:
        plan = (
            lesson_plan
            if isinstance(lesson_plan, CourseLessonPlan)
            else CourseLessonPlan.model_validate(lesson_plan)
        )
        payload = {
            "course_context": {
                "course_title": context.course_title,
                "training_goal": context.training_brief.goal,
                "audience_summary": context.audience_summary.model_dump(mode="json"),
                "language": context.language,
                "duration_constraint": context.duration_constraint,
                "normalized_duration": (
                    context.normalized_duration.model_dump(mode="json")
                    if context.normalized_duration is not None
                    else None
                ),
                "target_completion_context": context.target_completion_context,
            },
            "lesson_plan": plan.model_dump(mode="json"),
            "objective_refs": list(plan.objective_refs),
            "prior_learning_summary": list(prior_learning_summary),
        }
        prompt_id = (
            LESSON_REPAIR_PROMPT_ID if repair_context is not None else LESSON_GENERATION_PROMPT_ID
        )
        prompt_version = (
            LESSON_REPAIR_PROMPT_VERSION
            if repair_context is not None
            else LESSON_GENERATION_PROMPT_VERSION
        )
        if repair_context is not None:
            payload["original_lesson_draft"] = repair_context.previous_lesson_draft.model_dump(
                mode="json"
            )
            payload["repair_context"] = repair_context.model_dump(
                mode="json", exclude={"previous_lesson_draft"}
            )
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
                correlation_id=self.correlation_id,
            ),
            GeneratedLessonDraft,
        )
        self._audits.append(response.audit)
        return response.parsed
