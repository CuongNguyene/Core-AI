from uuid import uuid4

from app.integration.repository import IntegrationRepository
from app.integration.schemas import (
    CompetencyResultReference,
    CourseBlueprintV1,
    IntegrationEnvelopeV1,
    LearningResultAccepted,
    LearningResultRequest,
)
from app.learning.repository import LearningPathRepository


class IntegrationService:
    def __init__(
        self,
        repository: IntegrationRepository,
        blueprint_source: LearningPathRepository | None = None,
    ) -> None:
        self._repository = repository
        self._blueprint_source = blueprint_source
        self._blueprints: dict[str, CourseBlueprintV1] = {}
        self._competency_results: dict[str, CompetencyResultReference] = {}

    def register_blueprint(self, blueprint: CourseBlueprintV1) -> None:
        self._blueprints[blueprint.blueprint_id] = blueprint

    def register_competency_result(self, result_id: str, result: CompetencyResultReference) -> None:
        self._competency_results[result_id] = result

    async def get_blueprint(self, blueprint_id: str) -> CourseBlueprintV1 | None:
        blueprint = self._blueprints.get(blueprint_id)
        if blueprint is not None or self._blueprint_source is None:
            return blueprint
        path = await self._blueprint_source.get(blueprint_id)
        if path is None:
            return None
        source = next((item for item in path.blueprints if item.id == blueprint_id), None)
        if source is None:
            return None
        objective_titles = {
            item.id: item.measurable_outcome for item in path.objectives
        }
        lessons = {item.id: item for item in path.lessons}
        modules = []
        for order, module in enumerate(path.modules, start=1):
            module_lessons = []
            for lesson_order, lesson_id in enumerate(module.lesson_ids, start=1):
                lesson = lessons.get(lesson_id)
                if lesson is None:
                    continue
                module_lessons.append(
                    {
                        "lesson_ref": lesson.id,
                        "title": lesson.title,
                        "order": lesson_order,
                        "delivery_type": "TEXT",
                        "objective_refs": list(lesson.objective_ids),
                    }
                )
            modules.append(
                {
                    "module_ref": module.id,
                    "title": module.title,
                    "order": order,
                    "lessons": module_lessons,
                }
            )
        return CourseBlueprintV1(
            blueprint_id=source.id,
            version=source.version,
            title=source.title,
            objectives=[
                {
                    "objective_ref": item,
                    "title": objective_titles.get(item, item),
                    "sequence": index,
                }
                for index, item in enumerate(source.objective_ids, start=1)
            ],
            modules=modules,
            assessment_references=[],
        )

    async def accept_learning_result(
        self, envelope: IntegrationEnvelopeV1[LearningResultRequest]
    ) -> LearningResultAccepted:
        existing = await self._repository.get_learning_result(envelope.data.submission_id)
        if existing is not None:
            return LearningResultAccepted(
                status="ACCEPTED", evaluation_reference=existing.evaluation_reference
            )
        stored = await self._repository.create_learning_result(
            envelope.data, f"eval-{uuid4()}"
        )
        return LearningResultAccepted(status="ACCEPTED", evaluation_reference=stored.evaluation_reference)

    async def get_competency_result(self, result_id: str) -> CompetencyResultReference | None:
        result = self._competency_results.get(result_id)
        if result is not None:
            return result
        stored = await self._repository.get_learning_result_by_evaluation(result_id)
        if stored is None:
            return None
        return CompetencyResultReference(
            status="PENDING", evaluation_reference=stored.evaluation_reference
        )
