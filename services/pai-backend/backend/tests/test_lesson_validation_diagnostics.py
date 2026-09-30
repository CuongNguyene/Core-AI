from datetime import UTC, datetime

import pytest
from test_course_generation import draft
from test_lesson_generation import lesson_draft

from app.content_generation.repository import InMemoryContentGenerationRepository
from app.content_generation.schemas import (
    AssessmentQuestion,
    AssessmentQuestionType,
    GeneratedAssessmentDraft,
    GeneratedCourseLesson,
    GeneratedLessonDraft,
    LessonValidationDiagnostic,
    LessonValidationIssue,
    LessonValidationSectionMetrics,
)
from app.course_generation.lesson_validation import (
    replay_lesson_validation_diagnostic,
    validate_generated_lesson_report,
)
from app.course_generation.quality import measure_section_depth


def test_validator_collects_all_rejection_issues_and_section_metrics() -> None:
    candidate = draft().model_copy(
        update={
            "lesson_ref": "wrong-lesson",
            "lesson": draft().modules[0].lessons[0].model_copy(
                update={
                    "title": "Rejected lesson",
                    "objective_refs": ["unknown-objective"],
                    "sections": [
                        section.model_copy(
                            update={
                                "content": "too short",
                                "steps": [],
                                "success_criteria": [],
                            }
                        )
                        for section in draft().modules[0].lessons[0].sections
                    ],
                }
            ),
            "assessment": GeneratedAssessmentDraft(
                questions=[
                    AssessmentQuestion(
                        prompt="Question",
                        question_type=AssessmentQuestionType.SHORT_ANSWER,
                        expected_answer="Answer",
                        objective_refs=["unknown-objective"],
                    )
                ]
            ),
        }
    )

    report = validate_generated_lesson_report(
        candidate,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Clean invalid values",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
    )

    assert report.valid is False
    assert set(report.issue_codes) >= {
        "lesson_ref_invalid",
        "objective_refs_invalid",
        "section_depth_invalid",
        "guided_steps_missing",
        "independent_success_criteria_missing",
        "assessment_objective_ref_invalid",
    }
    assert len(report.section_metrics) == 6
    concept = next(item for item in report.section_metrics if item.section_type == "concept")
    assert concept.content_words == 2
    assert concept.steps_words == 0
    assert concept.success_criteria_words == 0
    assert concept.effective_words == 2
    assert concept.validation_words == 2
    assert concept.threshold == 180
    assert report.assessment_summary.question_count == 1


def test_section_depth_measurement_uses_structured_practice_payload() -> None:
    source = lesson_draft()
    guided = next(
        section for section in source.lesson.sections if section.type.value == "guided_practice"
    )
    independent = next(
        section
        for section in source.lesson.sections
        if section.type.value == "independent_practice"
    )

    guided_metrics = measure_section_depth(
        guided.model_copy(
            update={
                "content": " ".join(["guided"] * 30),
                "steps": [" ".join(["step"] * 40), " ".join(["step"] * 35)],
            }
        )
    )
    independent_metrics = measure_section_depth(
        independent.model_copy(
            update={
                "content": " ".join(["task"] * 50),
                "success_criteria": [" ".join(["criterion"] * 40)],
            }
        )
    )

    assert guided_metrics.content_words == 30
    assert guided_metrics.steps_words == 75
    assert guided_metrics.effective_words == 105
    assert guided_metrics.validation_words == 105
    assert independent_metrics.content_words == 50
    assert independent_metrics.success_criteria_words == 40
    assert independent_metrics.effective_words == 90
    assert independent_metrics.validation_words == 90


def test_structured_practice_payload_removes_depth_false_negatives() -> None:
    source = lesson_draft()
    sections = [
        section.model_copy(
            update={
                "content": " ".join(["guided"] * 30),
                "steps": [" ".join(["step"] * 40), " ".join(["step"] * 35)],
            }
        )
        if section.type.value == "guided_practice"
        else section.model_copy(
            update={
                "content": " ".join(["task"] * 50),
                "success_criteria": [" ".join(["criterion"] * 40)],
            }
        )
        if section.type.value == "independent_practice"
        else section
        for section in source.lesson.sections
    ]
    candidate = source.model_copy(
        update={"lesson": source.lesson.model_copy(update={"sections": sections})}
    )

    report = validate_generated_lesson_report(
        candidate,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Clean invalid values",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
    )

    assert report.valid is True
    assert "section_depth_invalid" not in report.issue_codes


def test_practice_structure_is_still_required_when_depth_is_sufficient() -> None:
    source = lesson_draft()
    sections = [
        section.model_copy(
            update={"content": " ".join(["guided"] * 120), "steps": []}
        )
        if section.type.value == "guided_practice"
        else section.model_copy(
            update={"content": " ".join(["task"] * 100), "success_criteria": []}
        )
        if section.type.value == "independent_practice"
        else section
        for section in source.lesson.sections
    ]
    candidate = source.model_copy(
        update={"lesson": source.lesson.model_copy(update={"sections": sections})}
    )

    report = validate_generated_lesson_report(
        candidate,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Clean invalid values",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
    )

    assert "guided_steps_missing" in report.issue_codes
    assert "independent_success_criteria_missing" in report.issue_codes


def test_validator_reports_missing_sections_order_title_and_assessment() -> None:
    source = lesson_draft()
    malformed_lesson = GeneratedCourseLesson.model_construct(
        title="",
        order=1,
        objective_refs=[],
        sections=[source.lesson.sections[1].model_copy(update={"order": 2})],
    )
    candidate = GeneratedLessonDraft.model_construct(
        lesson_ref="",
        lesson=malformed_lesson,
        assessment=None,
    )

    report = validate_generated_lesson_report(
        candidate,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Clean invalid values",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
    )

    assert set(report.issue_codes) >= {
        "lesson_ref_invalid",
        "lesson_title_invalid",
        "objective_refs_invalid",
        "section_missing",
        "section_order_invalid",
        "assessment_missing",
    }


def test_validator_rejects_model_lesson_title_drift() -> None:
    source = lesson_draft()
    candidate = source.model_copy(
        update={
            "lesson": source.lesson.model_copy(
                update={"title": "Module 1 Assessment and Review"}
            )
        }
    )

    report = validate_generated_lesson_report(
        candidate,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Module 1 Assessment",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
    )

    title_issue = next(issue for issue in report.issues if issue.code == "lesson_title_invalid")
    assert title_issue.actual == "Module 1 Assessment and Review"
    assert title_issue.expected == "Module 1 Assessment"


def test_validator_reports_assessment_structure_invalid() -> None:
    source = lesson_draft()
    invalid_question = AssessmentQuestion.model_construct(
        prompt="Question",
        question_type=AssessmentQuestionType.MULTIPLE_CHOICE,
        options=["Only one"],
        expected_answer="Missing",
        objective_refs=["objective-001"],
    )
    candidate = source.model_copy(
        update={
            "assessment": GeneratedAssessmentDraft.model_construct(
                questions=[invalid_question]
            )
        }
    )

    report = validate_generated_lesson_report(
        candidate,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Clean invalid values",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
    )

    assert "assessment_structure_invalid" in report.issue_codes


def test_replay_is_deterministic_without_provider() -> None:
    candidate = lesson_draft()
    diagnostic = LessonValidationDiagnostic(
        id="lesson-validation-diagnostic:001",
        authoring_request_ref="request-001",
        plan_ref="plan-001",
        task_ref="task-001",
        lesson_ref="lesson-001",
        attempt=1,
        generation_run_ref="run-001",
        provider="fake",
        model="fake-model",
        prompt_version="sep-02.2-v1",
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
        sanitized_parsed_draft=candidate.model_dump(mode="json"),
        validation_issues=[],
        section_metrics=[],
        assessment_summary={
            "present": True,
            "question_count": 1,
            "multiple_choice_count": 0,
            "short_answer_count": 1,
            "objective_refs": ["objective-001"],
            "invalid_objective_refs": [],
            "mcq_invalid_count": 0,
            "missing_answer_count": 0,
        },
    )

    first = replay_lesson_validation_diagnostic(
        diagnostic,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Clean invalid values",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
    )
    second = replay_lesson_validation_diagnostic(
        diagnostic,
        expected_lesson_ref="lesson-001",
        expected_lesson_title="Clean invalid values",
        expected_objective_refs=["objective-001"],
        allowed_objective_refs={"objective-001"},
    )

    assert first.issue_codes == second.issue_codes
    assert first.section_metrics == second.section_metrics
    assert first.assessment_summary == second.assessment_summary
    assert first.valid is True


@pytest.mark.asyncio
async def test_diagnostic_repository_round_trip_excludes_provider_transport_data() -> None:
    repository = InMemoryContentGenerationRepository()
    diagnostic = LessonValidationDiagnostic(
        id="lesson-validation-diagnostic:002",
        authoring_request_ref="request-001",
        plan_ref="plan-001",
        task_ref="task-001",
        lesson_ref="lesson-001",
        attempt=1,
        generation_run_ref="run-001",
        provider="gemini",
        model="gemini-3.5-flash-lite",
        prompt_version="sep-02.2-v1",
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
        sanitized_parsed_draft=lesson_draft().model_dump(mode="json"),
        validation_issues=[
            LessonValidationIssue(
                code="section_depth_invalid",
                path="lesson.sections[1].content",
                message="section below threshold",
                actual=2,
                expected=180,
            )
        ],
        section_metrics=[
            LessonValidationSectionMetrics(
                section_type="concept",
                content_words=2,
                steps_words=0,
                success_criteria_words=0,
                effective_words=2,
                threshold=180,
            )
        ],
        assessment_summary={
            "present": True,
            "question_count": 1,
            "multiple_choice_count": 0,
            "short_answer_count": 1,
            "objective_refs": ["objective-001"],
            "invalid_objective_refs": [],
            "mcq_invalid_count": 0,
            "missing_answer_count": 0,
        },
    )

    await repository.create_lesson_validation_diagnostic(diagnostic)
    restored = await repository.get_lesson_validation_diagnostic(diagnostic.id)

    assert restored is not None
    assert restored.sanitized_parsed_draft == diagnostic.sanitized_parsed_draft
    assert restored.issue_codes == ["section_depth_invalid"]
    assert "api_key" not in restored.sanitized_parsed_draft
    assert "headers" not in restored.sanitized_parsed_draft
