import json

from app.content_generation.schemas import (
    AssessmentQuestionType,
    ContentSectionType,
    GeneratedLessonDraft,
    LessonAssessmentValidationSummary,
    LessonValidationDiagnostic,
    LessonValidationIssue,
    LessonValidationReport,
    LessonValidationSectionMetrics,
)

from .errors import CourseGenerationOutputInvalidError
from .quality import (
    REQUIRED_SECTION_TYPES,
    CourseContentQualityPolicy,
    measure_section_depth,
)


def _issue(
    code: str,
    *,
    path: str,
    message: str,
    actual: str | int | list[str] | list[int] | None = None,
    expected: str | int | list[str] | list[int] | None = None,
) -> LessonValidationIssue:
    return LessonValidationIssue(
        code=code,
        path=path,
        message=message,
        actual=actual,
        expected=expected,
    )


def validate_generated_lesson_report(
    draft: GeneratedLessonDraft,
    *,
    expected_lesson_ref: str,
    expected_lesson_title: str,
    expected_objective_refs: list[str],
    allowed_objective_refs: set[str],
    policy: CourseContentQualityPolicy | None = None,
    duration_constraint: str | None = None,
    enforce_content_quality: bool = True,
) -> LessonValidationReport:
    """Collect every deterministic lesson validation issue without raising."""

    quality_policy = policy or CourseContentQualityPolicy()
    issues: list[LessonValidationIssue] = []
    if draft.lesson_ref != expected_lesson_ref:
        issues.append(
            _issue(
                "lesson_ref_invalid",
                path="lesson_ref",
                message="lesson reference does not match the planned lesson",
                actual=draft.lesson_ref,
                expected=expected_lesson_ref,
            )
        )
    if not draft.lesson.title.strip() or draft.lesson.title != expected_lesson_title:
        issues.append(
            _issue(
                "lesson_title_invalid",
                path="lesson.title",
                message="lesson title must match the planned lesson title",
                actual=draft.lesson.title,
                expected=expected_lesson_title,
            )
        )
    unknown_objective_refs = sorted(set(draft.lesson.objective_refs) - allowed_objective_refs)
    if draft.lesson.objective_refs != expected_objective_refs or unknown_objective_refs:
        issues.append(
            _issue(
                "objective_refs_invalid",
                path="lesson.objective_refs",
                message="lesson objective references changed or are not allowed",
                actual=list(draft.lesson.objective_refs),
                expected=list(expected_objective_refs),
            )
        )

    sections = list(draft.lesson.sections)
    section_types = {section.type for section in sections}
    for missing in sorted(REQUIRED_SECTION_TYPES, key=lambda item: item.value):
        if missing in section_types:
            continue
        issues.append(
            _issue(
                "section_missing",
                path="lesson.sections",
                message="required section is missing",
                actual=sorted(section_type.value for section_type in section_types),
                expected=missing.value,
            )
        )
    section_orders = [section.order for section in sections]
    if section_orders != list(range(1, len(section_orders) + 1)):
        issues.append(
            _issue(
                "section_order_invalid",
                path="lesson.sections.order",
                message="section order must be contiguous and start at one",
                actual=section_orders,
                expected=list(range(1, len(section_orders) + 1)),
            )
        )

    section_metrics: list[LessonValidationSectionMetrics] = []
    lesson_words = 0
    for index, section in enumerate(sections):
        depth = measure_section_depth(section)
        content_words = depth.content_words
        steps_words = depth.steps_words
        criteria_words = depth.success_criteria_words
        threshold = quality_policy.minimum_section_words.get(section.type)
        section_metrics.append(
            LessonValidationSectionMetrics(
                section_type=section.type.value,
                content_words=content_words,
                steps_words=steps_words,
                success_criteria_words=criteria_words,
                effective_words=depth.effective_words,
                validation_words=depth.validation_words,
                threshold=threshold,
            )
        )
        lesson_words += content_words
        if not section.content.strip():
            issues.append(
                _issue(
                    "section_content_missing",
                    path=f"lesson.sections[{index}].content",
                    message="section content is required",
                    actual=content_words,
                    expected=threshold or 1,
                )
            )
        elif (
            enforce_content_quality and threshold is not None and depth.validation_words < threshold
        ):
            issues.append(
                _issue(
                    "section_depth_invalid",
                    path=f"lesson.sections[{index}].content",
                    message="section depth is below the configured threshold",
                    actual=depth.validation_words,
                    expected=threshold,
                )
            )
        if (
            enforce_content_quality
            and section.type is ContentSectionType.GUIDED_PRACTICE
            and len(section.steps) < 2
        ):
            issues.append(
                _issue(
                    "guided_steps_missing",
                    path=f"lesson.sections[{index}].steps",
                    message="guided practice requires at least two steps",
                    actual=len(section.steps),
                    expected=2,
                )
            )
        if (
            enforce_content_quality
            and section.type is ContentSectionType.INDEPENDENT_PRACTICE
            and not section.success_criteria
        ):
            issues.append(
                _issue(
                    "independent_success_criteria_missing",
                    path=f"lesson.sections[{index}].success_criteria",
                    message="independent practice requires success criteria",
                    actual=0,
                    expected=1,
                )
            )

    maximum_words = quality_policy.maximum_lesson_words(duration_constraint)
    if enforce_content_quality and lesson_words > maximum_words:
        issues.append(
            _issue(
                "section_depth_invalid",
                path="lesson.sections",
                message="lesson content exceeds the configured maximum",
                actual=lesson_words,
                expected=maximum_words,
            )
        )

    assessment = draft.assessment
    questions = list(assessment.questions) if assessment is not None else []
    invalid_assessment_refs = sorted(
        {
            reference
            for question in questions
            for reference in question.objective_refs
            if reference not in allowed_objective_refs
        }
    )
    assessment_summary = LessonAssessmentValidationSummary(
        present=assessment is not None,
        question_count=len(questions),
        multiple_choice_count=sum(
            question.question_type is AssessmentQuestionType.MULTIPLE_CHOICE
            for question in questions
        ),
        short_answer_count=sum(
            question.question_type is AssessmentQuestionType.SHORT_ANSWER for question in questions
        ),
        objective_refs=sorted({ref for question in questions for ref in question.objective_refs}),
        invalid_objective_refs=invalid_assessment_refs,
        mcq_invalid_count=sum(
            question.question_type is AssessmentQuestionType.MULTIPLE_CHOICE
            and (
                len(question.options) < 3
                or len(question.options) != len(set(question.options))
                or question.expected_answer not in question.options
            )
            for question in questions
        ),
        missing_answer_count=sum(not question.expected_answer.strip() for question in questions),
    )
    if assessment is None:
        if expected_objective_refs:
            issues.append(
                _issue(
                    "assessment_missing",
                    path="assessment",
                    message="lesson assessment is required when objectives exist",
                    actual=0,
                    expected=1,
                )
            )
    else:
        for index, question in enumerate(questions):
            if not question.objective_refs or any(
                reference not in allowed_objective_refs for reference in question.objective_refs
            ):
                issues.append(
                    _issue(
                        "assessment_objective_ref_invalid",
                        path=f"assessment.questions[{index}].objective_refs",
                        message="assessment objective references are not allowed",
                        actual=list(question.objective_refs),
                    )
                )
            if (
                question.question_type is AssessmentQuestionType.MULTIPLE_CHOICE
                and (
                    len(question.options) < 3
                    or len(question.options) != len(set(question.options))
                    or question.expected_answer not in question.options
                )
            ) or (
                question.question_type is AssessmentQuestionType.SHORT_ANSWER
                and not question.expected_answer.strip()
            ):
                issues.append(
                    _issue(
                        "assessment_structure_invalid",
                        path=f"assessment.questions[{index}]",
                        message="assessment question shape is invalid",
                    )
                )

    return LessonValidationReport(
        valid=not issues,
        issues=issues,
        section_metrics=section_metrics,
        assessment_summary=assessment_summary,
    )


_LEGACY_ERROR_CODES = {
    "lesson_ref_invalid": "lesson_reference_mismatch",
    "lesson_title_invalid": "lesson_title_required",
    "objective_refs_invalid": "lesson_objective_references_changed",
    "section_missing": "required_section_missing",
    "section_order_invalid": "invalid_lesson_section_order",
    "section_content_missing": "generated_section_content_required",
    "section_depth_invalid": "section_word_count_below_minimum",
    "guided_steps_missing": "guided_practice_steps_required",
    "independent_success_criteria_missing": "independent_practice_success_criteria_required",
    "assessment_missing": "lesson_assessment_required",
    "assessment_structure_invalid": "multiple_choice_options_required",
    "assessment_objective_ref_invalid": "assessment_objective_reference_invalid",
}


def raise_for_lesson_validation_report(report: LessonValidationReport) -> None:
    if report.valid:
        return
    first_code = report.issues[0].code
    raise CourseGenerationOutputInvalidError(_LEGACY_ERROR_CODES.get(first_code, first_code))


def validate_generated_lesson(
    draft: GeneratedLessonDraft,
    *,
    expected_lesson_ref: str,
    expected_lesson_title: str,
    expected_objective_refs: list[str],
    allowed_objective_refs: set[str],
    policy: CourseContentQualityPolicy | None = None,
    duration_constraint: str | None = None,
    enforce_content_quality: bool = True,
) -> None:
    """Backward-compatible pass/fail wrapper around the diagnostic validator."""

    report = validate_generated_lesson_report(
        draft,
        expected_lesson_ref=expected_lesson_ref,
        expected_lesson_title=expected_lesson_title,
        expected_objective_refs=expected_objective_refs,
        allowed_objective_refs=allowed_objective_refs,
        policy=policy,
        duration_constraint=duration_constraint,
        enforce_content_quality=enforce_content_quality,
    )
    raise_for_lesson_validation_report(report)


def replay_lesson_validation_diagnostic(
    diagnostic: LessonValidationDiagnostic,
    *,
    expected_lesson_ref: str,
    expected_lesson_title: str,
    expected_objective_refs: list[str],
    allowed_objective_refs: set[str],
    policy: CourseContentQualityPolicy | None = None,
    duration_constraint: str | None = None,
    enforce_content_quality: bool = True,
) -> LessonValidationReport:
    """Revalidate a sanitized parsed candidate without invoking a model provider."""

    draft = GeneratedLessonDraft.model_validate_json(json.dumps(diagnostic.sanitized_parsed_draft))
    return validate_generated_lesson_report(
        draft,
        expected_lesson_ref=expected_lesson_ref,
        expected_lesson_title=expected_lesson_title,
        expected_objective_refs=expected_objective_refs,
        allowed_objective_refs=allowed_objective_refs,
        policy=policy,
        duration_constraint=duration_constraint,
        enforce_content_quality=enforce_content_quality,
    )
