import pytest
from pydantic import ValidationError
from test_course_generation import ReferenceReader, actor, authoring_request, blueprint, draft

from app.content_generation.prompts import course_generation_prompt_template
from app.content_generation.repository import InMemoryContentGenerationRepository
from app.content_generation.schemas import (
    AssessmentQuestion,
    AssessmentQuestionType,
    ContentSectionType,
    GeneratedAssessmentDraft,
    GeneratedCourseDraft,
    GeneratedCourseLesson,
    GeneratedCourseModule,
    GeneratedCourseSection,
    GenerationRunStatus,
)
from app.course_authoring.schemas import CourseAuthoringMode, CourseAuthoringRequest
from app.course_generation.context import CourseGenerationContext, CourseGenerationContextBuilder
from app.course_generation.errors import CourseGenerationOutputInvalidError
from app.course_generation.service import CourseGenerationService
from app.course_generation.validation import validate_generated_course
from app.model_gateway.errors import StructuredOutputFailedError


class GoalAuthoringReader:
    async def get(self, _request_id: str, _actor: object) -> CourseAuthoringRequest:
        return authoring_request(CourseAuthoringMode.GOAL_DRIVEN)


def test_course_generation_prompt_declares_the_current_structured_contract() -> None:
    template = course_generation_prompt_template()

    assert "course.title" in template.system_instruction
    assert "modules[].lessons[].sections[]" in template.system_instruction
    assert "snake_case" in template.system_instruction
    assert "course_title" in template.system_instruction
    assert "objective_refs" in template.user_instruction


@pytest.mark.parametrize(
    ("label", "update"),
    [
        ("course title", {"course": {"title": ""}}),
        ("module list", {"modules": []}),
        ("lesson list", {"modules": [{"title": "Foundations", "order": 1, "lessons": []}]}),
        (
            "section type",
            {
                "modules": [
                    {
                        "title": "Foundations",
                        "order": 1,
                        "lessons": [
                            {
                                "title": "Lesson",
                                "order": 1,
                                "sections": [
                                    {
                                        "type": "unsupported",
                                        "title": "Bad section",
                                        "content": "Content",
                                        "order": 1,
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
        ),
    ],
)
def test_structured_course_contract_rejects_invalid_hierarchy(
    label: str, update: dict[str, object]
) -> None:
    del label
    values = draft().model_dump()
    if "course" in update:
        course = dict(values["course"])
        course.update(update["course"])
        values["course"] = course
    else:
        values.update(update)

    with pytest.raises(ValidationError):
        GeneratedCourseDraft.model_validate(values)


def test_structured_course_contract_accepts_all_section_and_assessment_types() -> None:
    sections = [
        GeneratedCourseSection(
            type=section_type,
            title=section_type.value.replace("_", " ").title(),
            content=" ".join(f"word{index}" for index in range(
                {
                    ContentSectionType.INTRODUCTION: 60,
                    ContentSectionType.CONCEPT: 180,
                    ContentSectionType.EXAMPLE: 100,
                    ContentSectionType.GUIDED_PRACTICE: 100,
                    ContentSectionType.INDEPENDENT_PRACTICE: 80,
                    ContentSectionType.SUMMARY: 60,
                }[section_type]
            )),
            order=index,
            steps=["Inspect the task", "Complete the guided action"]
            if section_type is ContentSectionType.GUIDED_PRACTICE
            else [],
            success_criteria=["The learner produces the expected result"]
            if section_type is ContentSectionType.INDEPENDENT_PRACTICE
            else [],
        )
        for index, section_type in enumerate(ContentSectionType, start=1)
    ]
    generated = GeneratedCourseDraft(
        course={"title": "Course", "description": "Description"},
        modules=[
            GeneratedCourseModule(
                title="Module",
                order=1,
                lessons=[
                    GeneratedCourseLesson(
                        title="Lesson",
                        order=1,
                        objective_refs=["objective-001"],
                        sections=sections,
                    )
                ],
            )
        ],
        assessment=GeneratedAssessmentDraft(
            questions=[
                AssessmentQuestion(
                    prompt="Choose the first action.",
                    question_type=AssessmentQuestionType.MULTIPLE_CHOICE,
                    options=["Inspect", "Ignore", "Escalate"],
                    expected_answer="Inspect",
                    objective_refs=["objective-001"],
                ),
                AssessmentQuestion(
                    prompt="Explain the rationale.",
                    question_type=AssessmentQuestionType.SHORT_ANSWER,
                    expected_answer="Inspect before acting.",
                    objective_refs=["objective-001"],
                ),
            ]
        ),
    )

    context = CourseGenerationContext(
        authoring_request_ref="request-001",
        course_title="Practical capability",
        training_brief={"goal": "Goal"},
        audience_summary={"learner_count": 1, "source": "MANUAL_SELECTION"},
        learning_need_refs=["learning-need-001"],
        learning_objectives=[
            {
                "id": "objective-001",
                "learning_need_ref": "learning-need-001",
                "statement": "Do the task",
                "bloom_level": "apply",
                "evidence_required": ["evidence"],
                "competency_id": "competency-001",
                "current_level": 1,
                "target_level": 3,
                "measurable_outcome": "Do the task safely.",
                "gap_id": "gap-001",
                "sequence": 1,
            }
        ],
        instructional_blueprint=blueprint(),
    )

    validate_generated_course(generated, context)


@pytest.mark.asyncio
async def test_generation_maps_structured_gateway_failure_and_fails_run() -> None:
    class MalformedGenerator:
        model_audits: list[object] = []

        async def generate(
            self, _request: CourseAuthoringRequest, _context: CourseGenerationContext
        ) -> GeneratedCourseDraft:
            raise StructuredOutputFailedError("invalid_model_json")

    repository = InMemoryContentGenerationRepository()
    service = CourseGenerationService(
        authoring=GoalAuthoringReader(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=MalformedGenerator(),
        repository=repository,
        provider="fake-provider",
        model="fake-model",
    )

    with pytest.raises(CourseGenerationOutputInvalidError, match="invalid_model_json"):
        await service.generate("request-001", actor())

    run = next(iter(repository.runs.values()))
    assert run.status is GenerationRunStatus.FAILED
    assert run.error_code == "malformed_structured_output"


@pytest.mark.asyncio
async def test_generation_context_contains_only_minimal_audience_and_design_context() -> None:
    context = await CourseGenerationContextBuilder(ReferenceReader()).build(
        authoring_request(), actor()
    )

    assert set(context.model_dump()) == {
        "authoring_request_ref",
        "course_title",
        "training_brief",
        "audience_summary",
        "learning_need_refs",
        "learning_objectives",
        "instructional_blueprint",
        "language",
        "duration_constraint",
        "target_completion_context",
        "generated_objectives",
        "normalized_duration",
    }
    for forbidden in ("raw_cv", "raw_jd", "credentials", "learner_profiles"):
        assert forbidden not in context.model_dump()


@pytest.mark.asyncio
async def test_generation_run_has_execution_timestamps_and_v1_result_metadata() -> None:
    class GoalGenerator:
        model_audits: list[object] = []

        async def generate(
            self, _request: CourseAuthoringRequest, _context: CourseGenerationContext
        ) -> GeneratedCourseDraft:
            return draft(objective_ref="goal-driven-objective:course-authoring-request-001:1")

    repository = InMemoryContentGenerationRepository()
    service = CourseGenerationService(
        authoring=GoalAuthoringReader(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=GoalGenerator(),
        repository=repository,
        provider="fake-provider",
        model="fake-model",
    )

    accepted = await service.generate("request-001", actor())
    result = await repository.get_result(accepted.result_ref)
    run = repository.runs[accepted.generation_run_ref]

    assert accepted.version == 1
    assert result is not None
    assert result.supersedes_result_ref is None
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.started_at <= run.finished_at
    assert run.prompt_version == "sep-02-v3"
    assert result.generated_objectives[0].origin == "GOAL_DRIVEN_TRAINING_BRIEF"
    assert result.generation_metadata.generation_run_id == run.run_id
