import json
import re

from pydantic import BaseModel, ConfigDict, Field

from app.content_generation.schemas import (
    GeneratedLessonDraft,
    LessonValidationDiagnostic,
    LessonValidationReport,
    LessonValidationSectionMetrics,
)

REPAIRABLE_ISSUE_CODES = frozenset(
    {
        "section_depth_invalid",
        "guided_steps_missing",
        "independent_success_criteria_missing",
    }
)


class LessonSectionRepairRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    section_type: str = Field(min_length=1)
    validation_words: int = Field(ge=0)
    required_words: int = Field(ge=0)
    deficit_words: int = Field(ge=0)
    issue_codes: list[str] = Field(min_length=1)


class LessonRepairContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    previous_attempt_ref: str = Field(min_length=1)
    previous_run_ref: str = Field(min_length=1)
    issue_codes: list[str] = Field(min_length=1)
    deficient_sections: list[LessonSectionRepairRequirement] = Field(min_length=1)
    preserved_sections: list[str]
    previous_section_metrics: list[LessonValidationSectionMetrics]
    assessment_status: str = Field(min_length=1)
    objective_refs: list[str]
    repair_instructions: list[str] = Field(min_length=1)
    previous_lesson_draft: GeneratedLessonDraft


def _section_index(path: str) -> int | None:
    match = re.match(r"lesson\.sections\[(\d+)\]", path)
    return int(match.group(1)) if match else None


def is_repairable_lesson_report(report: LessonValidationReport) -> bool:
    """Allow automatic repair only for bounded instructional quality failures."""

    if not report.issues or any(
        issue.code not in REPAIRABLE_ISSUE_CODES for issue in report.issues
    ):
        return False
    for issue in report.issues:
        if issue.code != "section_depth_invalid":
            continue
        if (
            _section_index(issue.path) is None
            or not isinstance(issue.actual, int)
            or not isinstance(issue.expected, int)
            or issue.actual >= issue.expected
        ):
            return False
    return True


def build_lesson_repair_context(
    report: LessonValidationReport,
    diagnostic: LessonValidationDiagnostic,
) -> LessonRepairContext:
    """Build a sanitized, deterministic repair request from one rejection."""

    candidate = GeneratedLessonDraft.model_validate_json(
        json.dumps(diagnostic.sanitized_parsed_draft)
    )
    issue_codes = list(dict.fromkeys(issue.code for issue in report.issues))
    by_index: dict[int, list[str]] = {}
    for issue in report.issues:
        index = _section_index(issue.path)
        if index is not None:
            by_index.setdefault(index, []).append(issue.code)

    deficient: list[LessonSectionRepairRequirement] = []
    for index, metrics in enumerate(report.section_metrics):
        codes = list(dict.fromkeys(by_index.get(index, [])))
        if not codes:
            continue
        required = metrics.threshold or 0
        validation_words = metrics.validation_words
        if validation_words is None:
            validation_words = metrics.content_words
        deficient.append(
            LessonSectionRepairRequirement(
                section_type=metrics.section_type,
                validation_words=validation_words,
                required_words=required,
                deficit_words=max(required - validation_words, 0),
                issue_codes=codes,
            )
        )

    deficient_indexes = set(by_index)
    preserved_sections = [
        metrics.section_type
        for index, metrics in enumerate(report.section_metrics)
        if index not in deficient_indexes
    ]
    assessment_status = (
        "VALID"
        if report.assessment_summary.present
        and not report.assessment_summary.invalid_objective_refs
        and report.assessment_summary.mcq_invalid_count == 0
        and report.assessment_summary.missing_answer_count == 0
        else "INVALID"
    )
    instructions = [
        (
            f"Repair {item.section_type}: current validation depth is "
            f"{item.validation_words} words; minimum required instructional depth is "
            f"{item.required_words} validation words. Add substantive coverage beyond "
            "the minimum without filler or repetition."
        )
        for item in deficient
    ]
    return LessonRepairContext(
        previous_attempt_ref=diagnostic.id,
        previous_run_ref=diagnostic.generation_run_ref,
        issue_codes=issue_codes,
        deficient_sections=deficient,
        preserved_sections=preserved_sections,
        previous_section_metrics=report.section_metrics,
        assessment_status=assessment_status,
        objective_refs=list(candidate.lesson.objective_refs),
        repair_instructions=instructions,
        previous_lesson_draft=candidate,
    )
