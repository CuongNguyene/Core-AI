import logging

from app.content_generation.schemas import (
    AssessmentQuestionType,
    ContentSectionType,
    GeneratedCourseDraft,
)

from .context import CourseGenerationContext
from .errors import CourseGenerationOutputInvalidError
from .quality import (
    REQUIRED_SECTION_TYPES,
    CourseContentQualityPolicy,
    measure_section_depth,
)

logger = logging.getLogger(__name__)


class GeneratedCourseValidationError(CourseGenerationOutputInvalidError):
    """Raised when a structurally parsed draft violates generation invariants."""


def validate_generated_course(
    draft: GeneratedCourseDraft,
    context: CourseGenerationContext,
    policy: CourseContentQualityPolicy | None = None,
) -> None:
    quality_policy = policy or CourseContentQualityPolicy()
    if not context.authoring_request_ref:
        raise GeneratedCourseValidationError("authoring_request_ref_required")
    if not context.training_brief.goal.strip():
        raise GeneratedCourseValidationError("training_goal_required")
    allowed_objectives = {objective.id for objective in context.learning_objectives} | {
        objective.id for objective in context.generated_objectives
    }
    lesson_objectives: set[str] = set()
    for module in draft.modules:
        for lesson in module.lessons:
            lesson_objectives.update(lesson.objective_refs)
            if not set(lesson.objective_refs).issubset(allowed_objectives):
                raise GeneratedCourseValidationError("lesson_objective_reference_invalid")
            section_types = {section.type for section in lesson.sections}
            if REQUIRED_SECTION_TYPES - section_types:
                raise GeneratedCourseValidationError("required_section_missing")
            lesson_words = 0
            for section in lesson.sections:
                if not section.content.strip():
                    raise GeneratedCourseValidationError("generated_section_content_required")
                depth = measure_section_depth(section)
                lesson_words += depth.content_words
                minimum = quality_policy.minimum_section_words[section.type]
                if depth.validation_words < minimum:
                    logger.warning(
                        "course_generation_section_quality_failed section_type=%s "
                        "section_order=%s words=%s minimum=%s",
                        section.type.value,
                        section.order,
                        depth.validation_words,
                        minimum,
                    )
                    raise GeneratedCourseValidationError("section_word_count_below_minimum")
                if section.type is ContentSectionType.GUIDED_PRACTICE and len(section.steps) < 2:
                    raise GeneratedCourseValidationError("guided_practice_steps_required")
                if (
                    section.type is ContentSectionType.INDEPENDENT_PRACTICE
                    and not section.success_criteria
                ):
                    raise GeneratedCourseValidationError(
                        "independent_practice_success_criteria_required"
                    )
            if lesson_words > quality_policy.maximum_lesson_words(context.duration_constraint):
                raise GeneratedCourseValidationError("lesson_word_count_exceeds_limit")

    canonical_objectives = {objective.id for objective in context.learning_objectives}
    derived_objectives = {objective.id for objective in context.generated_objectives}
    if canonical_objectives and not canonical_objectives.issubset(lesson_objectives):
        raise GeneratedCourseValidationError("orphan_learning_objective_reference")
    if derived_objectives and not derived_objectives.issubset(lesson_objectives):
        raise GeneratedCourseValidationError("orphan_goal_derived_objective_reference")
    if not canonical_objectives and not derived_objectives and lesson_objectives:
        raise GeneratedCourseValidationError("goal_driven_objective_reference_invalid")
    if context.instructional_blueprint is not None:
        blueprint_objectives = set(context.instructional_blueprint.objective_refs)
        if blueprint_objectives != canonical_objectives:
            raise GeneratedCourseValidationError("blueprint_objective_context_mismatch")

    assessments = []
    if draft.assessment is not None:
        assessments.append(draft.assessment)
    assessments.extend(item.assessment for item in draft.lesson_assessments)
    for assessment in assessments:
        for question in assessment.questions:
            if not set(question.objective_refs).issubset(allowed_objectives):
                raise GeneratedCourseValidationError("assessment_objective_reference_invalid")
            if allowed_objectives and not question.objective_refs:
                raise GeneratedCourseValidationError("assessment_objective_reference_required")
            if not allowed_objectives and question.objective_refs:
                raise GeneratedCourseValidationError("goal_driven_assessment_reference_invalid")
            if question.question_type is AssessmentQuestionType.MULTIPLE_CHOICE:
                if len(question.options) < 3:
                    raise GeneratedCourseValidationError("multiple_choice_options_required")
                if question.expected_answer not in question.options:
                    raise GeneratedCourseValidationError("multiple_choice_answer_invalid")
            elif not question.expected_answer.strip():
                raise GeneratedCourseValidationError("short_answer_expected_answer_required")
