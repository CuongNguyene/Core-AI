import pytest
from test_course_generation import actor, authoring_request, draft

from app.content_generation.prompts import (
    LESSON_GENERATION_HISTORICAL_VERSIONS,
    lesson_content_generation_prompt_template,
)
from app.content_generation.schemas import (
    AssessmentQuestion,
    AssessmentQuestionType,
    ContentSectionType,
    GeneratedAssessmentDraft,
    GeneratedLessonDraft,
)
from app.course_generation.context import CourseGenerationContextBuilder
from app.course_generation.errors import CourseGenerationOutputInvalidError
from app.course_generation.generator import ModelGatewayLessonContentGenerator
from app.course_generation.lesson_validation import validate_generated_lesson
from app.course_generation.plan_schemas import CourseLessonPlan
from app.model_gateway.contracts import (
    InferenceAuditMetadata,
    ModelUsage,
    StructuredInferenceResponse,
)


def lesson_draft() -> GeneratedLessonDraft:
    source = draft().modules[0].lessons[0]
    return GeneratedLessonDraft(
        lesson_ref="lesson-001",
        lesson=source,
        assessment=GeneratedAssessmentDraft(
            questions=[
                AssessmentQuestion(
                    prompt="What should happen first?",
                    question_type=AssessmentQuestionType.SHORT_ANSWER,
                    expected_answer="Inspect the input.",
                    objective_refs=["objective-001"],
                )
            ]
        ),
    )


def test_lesson_prompt_is_versioned_and_lesson_scoped() -> None:
    prompt = lesson_content_generation_prompt_template()

    assert prompt.template_id == "lesson_content_generation"
    assert prompt.version == "sep-02.2-v2"
    assert "one lesson" in f"{prompt.system_instruction} {prompt.user_instruction}"
    assert "guided_practice" in prompt.user_instruction
    assert "independent_practice" in prompt.user_instruction
    assert "lesson_ref" in prompt.user_instruction
    for phrase in (
        "concept must include clear definitions",
        "worked example",
        "content gives setup/context/instructions",
        "success_criteria",
        "learner self-check",
    ):
        assert phrase in f"{prompt.system_instruction} {prompt.user_instruction}"


def test_lesson_prompt_v1_remains_historical() -> None:
    historical = lesson_content_generation_prompt_template("sep-02.2-v1")

    assert LESSON_GENERATION_HISTORICAL_VERSIONS == ("sep-02.2-v1",)
    assert historical.version == "sep-02.2-v1"
    assert "concept must include clear definitions" not in historical.user_instruction


@pytest.mark.asyncio
async def test_lesson_generator_uses_registered_lesson_contract() -> None:
    calls: list[tuple[object, object]] = []

    class Gateway:
        async def infer_structured(self, request: object, output_schema: object) -> object:
            calls.append((request, output_schema))
            return StructuredInferenceResponse(
                parsed=lesson_draft(),
                    audit=InferenceAuditMetadata(
                    provider="fake-provider",
                    model="fake-model",
                    model_revision=None,
                    prompt_template_id="lesson_content_generation",
                    prompt_template_version="sep-02.2-v2",
                    output_schema_id="lesson_content_generation",
                    output_schema_version="sep-02.2-v2",
                    policy_version="test",
                    correlation_id="corr-001",
                    routing_decision="test",
                    attempt_count=1,
                    latency_ms=1,
                        usage=ModelUsage(input_tokens=None, output_tokens=None),
                    outcome="succeeded",
                ),
            )

    from test_course_generation import ReferenceReader

    context = await CourseGenerationContextBuilder(ReferenceReader()).build(
        authoring_request(), actor()
    )
    result = await ModelGatewayLessonContentGenerator(
        gateway=Gateway(), requested_provider="fake-provider", correlation_id="corr-001"
    ).generate(
        CourseLessonPlan(
            lesson_ref="lesson-001",
            module_order=1,
            lesson_order=1,
            title="Clean invalid values",
            objective_refs=["objective-001"],
        ),
        context,
    )

    assert result.lesson_ref == "lesson-001"
    assert calls[0][1] is GeneratedLessonDraft


def test_lesson_validator_reuses_depth_and_practice_policy() -> None:
    generated = lesson_draft()
    validate_generated_lesson(
        generated,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Clean invalid values",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
    )

    shallow = generated.model_copy(
        update={
            "lesson": generated.lesson.model_copy(
                update={
                    "sections": [
                        section.model_copy(update={"content": "too short"})
                        if section.type is ContentSectionType.CONCEPT
                        else section
                        for section in generated.lesson.sections
                    ]
                }
            )
        }
    )
    with pytest.raises(CourseGenerationOutputInvalidError, match="section_word_count"):
        validate_generated_lesson(
            shallow,
            expected_lesson_ref="lesson-001",
            expected_lesson_title="Clean invalid values",
            expected_objective_refs=["objective-001"],
            allowed_objective_refs={"objective-001"},
        )


def test_lesson_validator_legacy_wrapper_preserves_empty_content_error() -> None:
    generated = lesson_draft()
    empty_content = generated.model_copy(
        update={
            "lesson": generated.lesson.model_copy(
                update={
                    "sections": [
                        section.model_copy(update={"content": ""})
                        if section.type is ContentSectionType.INTRODUCTION
                        else section
                        for section in generated.lesson.sections
                    ]
                }
            )
        }
    )

    with pytest.raises(
        CourseGenerationOutputInvalidError,
        match="generated_section_content_required",
    ):
        validate_generated_lesson(
            empty_content,
            expected_lesson_ref="lesson-001",
            expected_lesson_title="Clean invalid values",
            expected_objective_refs=["objective-001"],
            allowed_objective_refs={"objective-001"},
        )


def test_lesson_validator_can_disable_depth_gates_for_ui_smoke() -> None:
    generated = lesson_draft().model_copy(
        update={
            "lesson": lesson_draft().lesson.model_copy(
                update={
                    "sections": [
                        section.model_copy(
                            update={
                                "content": "short",
                                "steps": [],
                                "success_criteria": [],
                            }
                        )
                        for section in lesson_draft().lesson.sections
                    ]
                }
            )
        }
    )

    validate_generated_lesson(
        generated,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Clean invalid values",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
        enforce_content_quality=False,
    )


def test_lesson_validator_rejects_unknown_assessment_objective() -> None:
    generated = lesson_draft().model_copy(
        update={
            "assessment": GeneratedAssessmentDraft(
                questions=[
                    AssessmentQuestion(
                        prompt="Question",
                        question_type=AssessmentQuestionType.SHORT_ANSWER,
                        expected_answer="Answer",
                        objective_refs=["objective-unknown"],
                    )
                ]
            )
        }
    )

    with pytest.raises(CourseGenerationOutputInvalidError, match="assessment_objective"):
        validate_generated_lesson(
            generated,
            expected_lesson_ref="lesson-001",
            expected_lesson_title="Clean invalid values",
            expected_objective_refs=["objective-001"],
            allowed_objective_refs={"objective-001"},
        )
