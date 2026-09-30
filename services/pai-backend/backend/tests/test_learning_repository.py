from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.learning.repository import InMemoryLearningPathRepository
from app.learning.schemas import (
    CourseBlueprint,
    LearningModule,
    LearningObjective,
    LearningObjectMetadata,
    LearningObjectType,
    LearningPath,
    LearningPathStatus,
    Lesson,
    PrerequisiteNode,
    ProvenanceStatus,
)


def path_fixture() -> LearningPath:
    return LearningPath(
        id="path-1",
        version=1,
        status=LearningPathStatus.ACTIVE,
        subject_id=uuid4(),
        organization_id=uuid4(),
        target_profile_id="role-1",
        target_profile_version="1.0",
        preliminary_match_id="match-1",
        verified_competency_record_ids=[uuid4()],
        approved_gap_ids=["python"],
        development_goal="Become job-ready",
        target_completion_date=date(2026, 12, 1),
        objectives=[
            LearningObjective(
                id="obj-1",
                competency_id="python",
                target_level=2,
                measurable_outcome="Write functions",
                gap_id="python",
                sequence=1,
            )
        ],
        prerequisite_nodes=[PrerequisiteNode(id="node-1", learning_object_id="lo-1")],
        learning_objects=[
            LearningObjectMetadata(
                id="lo-1",
                version="1.0",
                object_type=LearningObjectType.READING,
                title="Functions",
                estimated_minutes=20,
                competency_id="python",
                target_level=2,
                assessment_template_id="assessment-1",
                assessment_template_version="1.0",
                approved_source_reference="catalog:python",
                provenance_status=ProvenanceStatus.APPROVED,
            )
        ],
        lessons=[
            Lesson(
                id="lesson-1",
                version="1.0",
                title="Functions",
                objective_ids=["obj-1"],
                learning_object_ids=["lo-1"],
            )
        ],
        modules=[
            LearningModule(
                id="module-1",
                version="1.0",
                title="Python",
                objective_ids=["obj-1"],
                lesson_ids=["lesson-1"],
            )
        ],
        blueprints=[
            CourseBlueprint(
                id="blueprint-1",
                version="1.0",
                title="Python",
                objective_ids=["obj-1"],
                module_ids=["module-1"],
                provenance_status=ProvenanceStatus.APPROVED,
            )
        ],
        generator_version="fake-1",
        policy_version="learning-1",
        correlation_id=str(uuid4()),
        created_by=uuid4(),
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_repository_keeps_snapshot_immutable_and_audits_safe_metadata() -> None:
    repository = InMemoryLearningPathRepository()
    path = path_fixture()

    stored = await repository.create(path)
    assert await repository.get(path.id) == path
    assert "development_goal" not in repository.audit_events[0]["metadata"]
    assert "learning_objects" not in repository.audit_events[0]["metadata"]

    with pytest.raises(ValueError, match="immutable"):
        await repository.create(path)
    assert stored.version == 1


@pytest.mark.asyncio
async def test_repository_supersedes_without_mutating_original() -> None:
    repository = InMemoryLearningPathRepository()
    original = path_fixture()
    await repository.create(original)

    successor = original.model_copy(
        update={"version": 2, "status": LearningPathStatus.ACTIVE}, deep=True
    )
    superseded = await repository.supersede(original.id, successor)

    assert superseded.version == 2
    assert (await repository.get(original.id)).status is LearningPathStatus.ACTIVE
    assert (await repository.get(original.id, version=1)).status is LearningPathStatus.SUPERSEDED
    assert (await repository.get(original.id, version=2)).status is LearningPathStatus.ACTIVE


@pytest.mark.asyncio
async def test_repository_rolls_back_when_audit_write_fails() -> None:
    repository = InMemoryLearningPathRepository(audit_failure=True)

    with pytest.raises(RuntimeError, match="audit_insert_failed"):
        await repository.create(path_fixture())

    assert repository.paths == {}
