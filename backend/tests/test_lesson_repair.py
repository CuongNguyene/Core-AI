from datetime import UTC, datetime

import pytest
from test_lesson_generation import lesson_draft

from app.content_generation.prompts import (
    LESSON_REPAIR_PROMPT_ID,
    LESSON_REPAIR_PROMPT_VERSION,
    lesson_content_repair_prompt_template,
)
from app.content_generation.schemas import GeneratedLessonDraft, LessonValidationDiagnostic
from app.course_generation.lesson_validation import validate_generated_lesson_report
from app.course_generation.repair import (
    build_lesson_repair_context,
    is_repairable_lesson_report,
)


def rejected_candidate() -> GeneratedLessonDraft:
    source = lesson_draft()
    sections = [
        section.model_copy(
            update={"content": "concept " * 145}
        )
        if section.type.value == "concept"
        else section.model_copy(
            update={
                "content": "guided " * 40,
                "steps": ["step " * 26, "step " * 26],
            }
        )
        if section.type.value == "guided_practice"
        else section
        for section in source.lesson.sections
    ]
    return source.model_copy(
        update={"lesson": source.lesson.model_copy(update={"sections": sections})}
    )


def diagnostic_for(candidate: GeneratedLessonDraft) -> tuple[LessonValidationDiagnostic, object]:
    report = validate_generated_lesson_report(
        candidate,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Clean invalid values",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
    )
    diagnostic = LessonValidationDiagnostic(
        id="lesson-validation-diagnostic:repair-001",
        authoring_request_ref="request-001",
        plan_ref="plan-001",
        task_ref="task-001",
        lesson_ref="lesson-001",
        attempt=1,
        generation_run_ref="run-001",
        provider="fake-provider",
        model="fake-model",
        prompt_version="sep-02.2-v2",
        created_at=datetime(2026, 8, 26, tzinfo=UTC),
        sanitized_parsed_draft=candidate.model_dump(mode="json"),
        validation_issues=report.issues,
        section_metrics=report.section_metrics,
        assessment_summary=report.assessment_summary,
    )
    return diagnostic, report


def test_repair_context_contains_only_deficient_sections() -> None:
    diagnostic, report = diagnostic_for(rejected_candidate())

    assert is_repairable_lesson_report(report) is True
    context = build_lesson_repair_context(report, diagnostic)

    assert [(item.section_type, item.deficit_words) for item in context.deficient_sections] == [
        ("concept", 35),
        ("guided_practice", 8),
    ]
    assert set(context.preserved_sections) >= {
        "introduction",
        "example",
        "independent_practice",
        "summary",
    }
    assert context.assessment_status == "VALID"
    assert context.objective_refs == ["objective-001"]
    assert "concept" in " ".join(context.repair_instructions)
    assert "guided_practice" in " ".join(context.repair_instructions)


def test_repair_eligibility_fails_closed_for_provenance_mismatch() -> None:
    candidate = rejected_candidate().model_copy(
        update={
            "lesson": rejected_candidate().lesson.model_copy(
                update={"objective_refs": ["objective-changed"]}
            )
        }
    )
    _diagnostic, report = diagnostic_for(candidate)

    assert "objective_refs_invalid" in report.issue_codes
    assert is_repairable_lesson_report(report) is False


def test_repair_prompt_is_separate_and_preserves_contract() -> None:
    prompt = lesson_content_repair_prompt_template()

    assert prompt.template_id == LESSON_REPAIR_PROMPT_ID
    assert prompt.version == LESSON_REPAIR_PROMPT_VERSION == "sep-02.2c-v1"
    text = f"{prompt.system_instruction} {prompt.user_instruction}".lower()
    for phrase in (
        "repair only",
        "lesson_ref",
        "exact planned lesson title",
        "objective_refs",
        "minimum required instructional depth",
        "do not add filler",
        "assessment",
    ):
        assert phrase in text


@pytest.mark.asyncio
async def test_lesson_generator_maps_repair_context_to_repair_contract() -> None:
    from test_course_generation import ReferenceReader, actor, authoring_request

    from app.course_generation.context import CourseGenerationContextBuilder
    from app.course_generation.generator import ModelGatewayLessonContentGenerator
    from app.course_generation.plan_schemas import CourseLessonPlan
    from app.model_gateway.contracts import (
        InferenceAuditMetadata,
        ModelUsage,
        StructuredInferenceResponse,
    )
    diagnostic, report = diagnostic_for(rejected_candidate())
    repair_context = build_lesson_repair_context(report, diagnostic)
    calls: list[object] = []

    class Gateway:
        async def infer_structured(self, request: object, output_schema: object) -> object:
            calls.append(request)
            return StructuredInferenceResponse(
                parsed=lesson_draft(),
                audit=InferenceAuditMetadata(
                    provider="fake-provider",
                    model="fake-model",
                    prompt_template_id=LESSON_REPAIR_PROMPT_ID,
                    prompt_template_version=LESSON_REPAIR_PROMPT_VERSION,
                    output_schema_id=LESSON_REPAIR_PROMPT_ID,
                    output_schema_version=LESSON_REPAIR_PROMPT_VERSION,
                    policy_version="test",
                    correlation_id="corr-001",
                    routing_decision="test",
                    attempt_count=1,
                    latency_ms=1,
                    usage=ModelUsage(),
                    outcome="succeeded",
                ),
            )

    context = await CourseGenerationContextBuilder(ReferenceReader()).build(
        authoring_request(), actor()
    )
    await ModelGatewayLessonContentGenerator(
        gateway=Gateway(), requested_provider="fake-provider", correlation_id="corr-001"
    ).generate(
        CourseLessonPlan(
            lesson_ref="lesson-001",
            module_order=1,
            lesson_order=1,
            title="Lesson",
            objective_refs=["objective-001"],
        ),
        context,
        repair_context=repair_context,
    )

    request = calls[0]
    assert request.prompt_template_id == LESSON_REPAIR_PROMPT_ID
    assert request.prompt_template_version == LESSON_REPAIR_PROMPT_VERSION
    assert "repair_context" in request.payload
    assert "original_lesson_draft" in request.payload
