from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.content_generation.schemas import (
    ContentGenerationRequest,
    ContentGenerationResult,
    ContentGenerationStatus,
    ContentGenerationType,
    ContentSection,
    ContentSectionType,
    GenerationMetadata,
    GenerationRun,
)
from app.content_generation.validation import (
    validate_content_generation_request,
    validate_content_generation_result,
)
from app.instructional_blueprint.schemas import (
    CourseBlueprint,
    InstructionalBlueprint,
    InstructionalPattern,
    LessonBlueprint,
    LessonType,
    ModuleBlueprint,
)
from app.learning.schemas import LearningObjective


def request(**overrides: object) -> ContentGenerationRequest:
    values: dict[str, object] = {
        "id": "request-001",
        "blueprint_ref": "blueprint-001",
        "lesson_ref": "lesson-001",
        "objective_refs": ["objective-001"],
        "generation_type": ContentGenerationType.LESSON_CONTENT,
        "constraints": {"language": "vi", "target_level": None},
        "generation_metadata": {},
    }
    values.update(overrides)
    return ContentGenerationRequest.model_validate(values)


def result(**overrides: object) -> ContentGenerationResult:
    values: dict[str, object] = {
        "id": "content-001",
        "request_ref": "request-001",
        "lesson_ref": "lesson-001",
        "status": ContentGenerationStatus.DRAFT,
        "sections": [],
        "source_blueprint_ref": "blueprint-001",
        "generation_metadata": {},
    }
    values.update(overrides)
    return ContentGenerationResult.model_validate(values)


def test_request_preserves_references_and_allows_empty_metadata() -> None:
    content_request = request()

    assert content_request.blueprint_ref == "blueprint-001"
    assert content_request.lesson_ref == "lesson-001"
    assert content_request.objective_refs == ["objective-001"]
    assert content_request.generation_metadata.prompt_version is None
    validate_content_generation_request(content_request)


def test_generation_metadata_supports_future_provenance_values() -> None:
    metadata = GenerationMetadata(
        prompt_version="prompt-v1",
        model="model-v1",
        provider="provider-v1",
        created_at=datetime(2026, 8, 21, tzinfo=UTC),
        generation_run_id="run-001",
    )

    assert metadata.model == "model-v1"
    assert metadata.created_at is not None
    assert metadata.generation_run_id == "run-001"


@pytest.mark.parametrize(
    "field",
    ["blueprint_ref", "lesson_ref", "generation_type"],
)
def test_request_rejects_missing_required_generation_inputs(field: str) -> None:
    value = "" if field != "generation_type" else "unsupported"

    with pytest.raises(ValidationError):
        request(**{field: value})


def test_result_supports_initial_statuses_and_preserves_source_blueprint() -> None:
    for status in ContentGenerationStatus:
        content_result = result(status=status)
        assert content_result.status is status
        assert content_result.source_blueprint_ref == "blueprint-001"


def test_result_validates_structured_sections_and_contiguous_order() -> None:
    sections = [
        ContentSection(
            type=ContentSectionType.INTRODUCTION,
            title="Introduction",
            content="",
            order=1,
        ),
        ContentSection(
            type=ContentSectionType.SUMMARY,
            title="Summary",
            content="",
            order=2,
        ),
    ]

    content_result = result(sections=sections)

    assert [section.type for section in content_result.sections] == [
        ContentSectionType.INTRODUCTION,
        ContentSectionType.SUMMARY,
    ]
    validate_content_generation_result(content_result)


def test_result_rejects_invalid_section_type_and_order() -> None:
    with pytest.raises(ValidationError):
        result(status="INVALID")

    with pytest.raises(ValidationError):
        result(
            sections=[
                {
                    "type": "assessment",
                    "title": "Unsupported",
                    "content": "",
                    "order": 1,
                }
            ]
        )


@pytest.mark.parametrize("field", ["request_ref", "lesson_ref", "source_blueprint_ref"])
def test_result_rejects_missing_source_references(field: str) -> None:
    with pytest.raises(ValidationError):
        result(**{field: ""})


def test_result_rejects_non_contiguous_section_order() -> None:
    with pytest.raises(ValidationError, match="invalid_section_order"):
        result(
            sections=[
                {
                    "type": ContentSectionType.INTRODUCTION,
                    "title": "Introduction",
                    "content": "",
                    "order": 2,
                }
            ]
        )


def test_empty_result_sections_and_optional_metadata_are_supported() -> None:
    content_result = result()

    assert content_result.sections == []
    assert content_result.generation_metadata.model_dump(exclude_none=True) == {}


def test_result_preserves_traceability_and_version_contract() -> None:
    content_result = ContentGenerationResult(
        id="content-002",
        request_ref="request-002",
        lesson_ref="lesson-002",
        objective_refs=["objective-002"],
        learning_need_refs=["learning-need-002"],
        version=1,
        supersedes_result_ref=None,
        status=ContentGenerationStatus.CREATED,
        source_blueprint_ref="blueprint-002",
        generation_run=None,
        sections=[],
    )

    assert content_result.version == 1
    assert content_result.learning_need_refs == ["learning-need-002"]
    assert content_result.generation_run is None


def test_generation_run_reserves_future_execution_metadata() -> None:
    run = GenerationRun(
        run_id="run-001",
        request_ref="request-001",
        model="future-model",
        prompt_version="text01-v1",
        provider="future-provider",
        started_at=None,
        finished_at=None,
    )

    assert run.run_id == "run-001"
    assert run.prompt_version == "text01-v1"


def test_reserved_content_lifecycle_states_are_represented() -> None:
    assert {status.value for status in ContentGenerationStatus} >= {
        "CREATED",
        "GENERATING",
        "REVISION_REQUESTED",
        "SUPERSEDED",
    }


def test_existing_learning_design_models_remain_constructible() -> None:
    objective = LearningObjective(
        id="objective-001",
        learning_need_ref="learning-need-001",
        statement="Handle missing values",
        competency_id="competency-001",
        target_level=3,
        measurable_outcome="Handle missing values safely.",
        gap_id="gap-001",
        sequence=1,
    )
    lesson = LessonBlueprint(
        id="lesson-001",
        title="Handle missing values",
        objective_refs=[objective.id],
        lesson_type=LessonType.SKILL_PRACTICE,
        estimated_minutes=30,
        instructional_pattern=[InstructionalPattern.CONCEPT_INTRODUCTION],
        sequence=1,
    )
    blueprint = InstructionalBlueprint(
        id="blueprint-001",
        learning_need_ref="learning-need-001",
        objective_refs=[objective.id],
        course=CourseBlueprint(
            id="course-001",
            title="Data quality",
            objective_refs=[objective.id],
            module_refs=["module-001"],
        ),
        modules=[
            ModuleBlueprint(
                id="module-001",
                title="Data quality",
                objective_refs=[objective.id],
                lesson_refs=[lesson.id],
                sequence=1,
            )
        ],
        lessons=[lesson],
    )

    assert objective.id in blueprint.objective_refs
