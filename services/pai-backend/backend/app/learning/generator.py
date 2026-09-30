from datetime import date
from typing import Protocol

from app.learning.schemas import (
    CourseBlueprint,
    LearningModule,
    LearningObjective,
    LearningObjectMetadata,
    LearningObjectType,
    Lesson,
    PrerequisiteEdge,
    PrerequisiteNode,
    ProvenanceStatus,
)


class ContentGenerationRequest:
    def __init__(
        self,
        *,
        target_profile_id: str,
        target_profile_version: str,
        preliminary_match_id: str | None,
        objectives: list[LearningObjective],
        target_completion_date: date,
        policy_version: str,
    ) -> None:
        self.target_profile_id = target_profile_id
        self.target_profile_version = target_profile_version
        self.preliminary_match_id = preliminary_match_id
        self.objectives = tuple(objectives)
        self.target_completion_date = target_completion_date
        self.policy_version = policy_version


class GeneratedBlueprint:
    def __init__(
        self,
        *,
        prerequisite_nodes: list[PrerequisiteNode],
        prerequisite_edges: list[PrerequisiteEdge],
        learning_objects: list[LearningObjectMetadata],
        lessons: list[Lesson],
        modules: list[LearningModule],
        blueprints: list[CourseBlueprint],
        generator_version: str,
    ) -> None:
        self.prerequisite_nodes = prerequisite_nodes
        self.prerequisite_edges = prerequisite_edges
        self.learning_objects = learning_objects
        self.lessons = lessons
        self.modules = modules
        self.blueprints = blueprints
        self.generator_version = generator_version

    def model_dump(self) -> dict[str, object]:
        return {
            "prerequisite_nodes": [
                item.model_dump(mode="json") for item in self.prerequisite_nodes
            ],
            "prerequisite_edges": [
                item.model_dump(mode="json") for item in self.prerequisite_edges
            ],
            "learning_objects": [item.model_dump(mode="json") for item in self.learning_objects],
            "lessons": [item.model_dump(mode="json") for item in self.lessons],
            "modules": [item.model_dump(mode="json") for item in self.modules],
            "blueprints": [item.model_dump(mode="json") for item in self.blueprints],
            "generator_version": self.generator_version,
        }

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GeneratedBlueprint) and self.model_dump() == other.model_dump()


class ContentBlueprintGenerator(Protocol):
    async def generate(self, request: ContentGenerationRequest) -> GeneratedBlueprint: ...


class FakeContentBlueprintGenerator:
    version = "fake-learning-generator-v1"

    async def generate(self, request: ContentGenerationRequest) -> GeneratedBlueprint:
        objects: list[LearningObjectMetadata] = []
        lessons: list[Lesson] = []
        modules: list[LearningModule] = []
        nodes: list[PrerequisiteNode] = []
        edges: list[PrerequisiteEdge] = []
        objective_ids: list[str] = []

        for objective in request.objectives:
            object_id = f"lo-{objective.id}"
            lesson_id = f"lesson-{objective.id}"
            module_id = f"module-{objective.id}"
            node_id = f"node-{objective.id}"
            objective_ids.append(objective.id)
            objects.append(
                LearningObjectMetadata(
                    id=object_id,
                    version="1.0",
                    object_type=LearningObjectType.EXERCISE,
                    title=objective.measurable_outcome,
                    estimated_minutes=30,
                    competency_id=objective.competency_id,
                    target_level=objective.target_level,
                    assessment_template_id=f"assessment-{objective.competency_id}",
                    assessment_template_version="1.0",
                    approved_source_reference=f"catalog:{objective.competency_id}",
                    provenance_status=ProvenanceStatus.APPROVED,
                )
            )
            lessons.append(
                Lesson(
                    id=lesson_id,
                    version="1.0",
                    title=objective.measurable_outcome,
                    objective_ids=[objective.id],
                    learning_object_ids=[object_id],
                )
            )
            modules.append(
                LearningModule(
                    id=module_id,
                    version="1.0",
                    title=f"{objective.competency_id} development",
                    objective_ids=[objective.id],
                    lesson_ids=[lesson_id],
                    prerequisite_node_ids=[node_id],
                )
            )
            nodes.append(PrerequisiteNode(id=node_id, learning_object_id=object_id))
            if len(nodes) > 1:
                edges.append(
                    PrerequisiteEdge(
                        from_node_id=nodes[-2].id,
                        to_node_id=nodes[-1].id,
                        reason_reference="catalog:sequence",
                    )
                )

        return GeneratedBlueprint(
            prerequisite_nodes=nodes,
            prerequisite_edges=edges,
            learning_objects=objects,
            lessons=lessons,
            modules=modules,
            blueprints=[
                CourseBlueprint(
                    id=f"blueprint-{request.target_profile_id}",
                    version="1.0",
                    title=f"Development path for {request.target_profile_id}",
                    objective_ids=objective_ids,
                    module_ids=[module.id for module in modules],
                    provenance_status=ProvenanceStatus.APPROVED,
                )
            ],
            generator_version=self.version,
        )
