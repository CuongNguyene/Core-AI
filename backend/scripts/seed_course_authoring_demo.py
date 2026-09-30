"""Seed idempotent goal-driven course authoring requests for local UI testing."""

from __future__ import annotations

import asyncio
import os
from uuid import UUID

from app.authorization.schemas import ActorContext, Role
from app.course_authoring.brief_revision_repository import (
    SqlAlchemyAuthoringBriefRevisionRepository,
)
from app.course_authoring.brief_revision_service import AuthoringBriefRevisionService
from app.course_authoring.repository import SqlAlchemyCourseAuthoringRepository
from app.course_authoring.schemas import CourseAuthoringRequestCreate, TrainingBrief
from app.course_authoring.service import CourseAuthoringService
from app.shared.database import Database

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000001")
REVIEWER_ID = UUID("00000000-0000-0000-0000-000000000004")

REQUESTS = (
    {
        "title": "Ultrasonic Testing Level II Refresher",
        "goal": "Refresh UT Level II technicians on calibration, interpretation, and reporting.",
        "outcomes": ("Calibrate UT equipment", "Interpret indications", "Write inspection reports"),
        "duration": "8 hours",
    },
    {
        "title": "Visual Testing Field Inspection",
        "goal": "Prepare field inspectors to perform consistent visual testing before NDT activities.",
        "outcomes": ("Plan a visual inspection", "Record defects", "Apply acceptance criteria"),
        "duration": "6 hours",
    },
    {
        "title": "Industrial Safety Leadership",
        "goal": "Develop supervisor capability to lead safe work planning and escalation.",
        "outcomes": ("Lead a safety briefing", "Identify escalation triggers", "Coach safe behaviors"),
        "duration": "4 hours",
    },
)


class NoReferenceReader:
    async def get_learning_need(self, artifact_id: str, actor: ActorContext) -> object:
        raise KeyError(artifact_id)

    async def get_learning_objective(self, artifact_id: str, actor: ActorContext) -> object:
        raise KeyError(artifact_id)

    async def get_instructional_blueprint(self, artifact_id: str, actor: ActorContext) -> object:
        raise KeyError(artifact_id)


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    database = Database(database_url)
    repository = SqlAlchemyCourseAuthoringRepository(database.session_factory)
    revisions = AuthoringBriefRevisionService(
        SqlAlchemyAuthoringBriefRevisionRepository(database.session_factory)
    )
    service = CourseAuthoringService(
        repository=repository,
        references=NoReferenceReader(),
        brief_revisions=revisions,
    )
    actor = ActorContext(
        actor_id=REVIEWER_ID,
        organization_id=ORGANIZATION_ID,
        roles=frozenset({Role.REVIEWER}),
    )
    existing_titles = {request.title for request in await repository.list()}
    created = []
    for item in REQUESTS:
        if item["title"] in existing_titles:
            continue
        accepted = await service.create(
            CourseAuthoringRequestCreate(
                title=item["title"],
                training_brief=TrainingBrief(
                    goal=item["goal"],
                    language="en",
                    duration_constraint=item["duration"],
                    desired_outcomes=item["outcomes"],
                    prerequisites=("Basic NDT awareness",),
                    expected_learning_effort=item["duration"],
                ),
                learner_refs=(),
                constraints={"seed": "local-demo"},
            ),
            actor,
        )
        created.append(accepted.request_id)
    print(f"course_authoring_seeded={len(created)}")
    for request_id in created:
        print(request_id)
    await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
