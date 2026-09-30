import pytest
from pydantic import ValidationError

from app.learning.graph import validate_prerequisite_graph
from app.learning.schemas import (
    LearningObjectMetadata,
    LearningObjectType,
    PrerequisiteEdge,
    PrerequisiteNode,
    ProvenanceStatus,
)


def object_metadata() -> LearningObjectMetadata:
    return LearningObjectMetadata(
        id="lo-python-functions",
        version="1.0",
        object_type=LearningObjectType.READING,
        title="Python functions",
        estimated_minutes=30,
        competency_id="python",
        target_level=2,
        assessment_template_id="assessment-python-1",
        assessment_template_version="1.0",
        approved_source_reference="catalog:python-basics",
        provenance_status=ProvenanceStatus.APPROVED,
    )


def test_learning_object_requires_approved_provenance_and_assessment_link() -> None:
    metadata = object_metadata()

    assert metadata.provenance_status is ProvenanceStatus.APPROVED
    assert metadata.assessment_template_version == "1.0"

    with pytest.raises(ValidationError):
        LearningObjectMetadata(
            **metadata.model_dump(exclude={"approved_source_reference"}),
            approved_source_reference="",
        )


def test_prerequisite_graph_rejects_cycle() -> None:
    nodes = [
        PrerequisiteNode(id="a", learning_object_id="lo-a"),
        PrerequisiteNode(id="b", learning_object_id="lo-b"),
    ]
    edges = [
        PrerequisiteEdge(from_node_id="a", to_node_id="b"),
        PrerequisiteEdge(from_node_id="b", to_node_id="a"),
    ]

    with pytest.raises(ValueError, match="cycle"):
        validate_prerequisite_graph(nodes, edges)


def test_prerequisite_graph_accepts_ordered_dag() -> None:
    nodes = [
        PrerequisiteNode(id="a", learning_object_id="lo-a"),
        PrerequisiteNode(id="b", learning_object_id="lo-b"),
    ]
    edges = [PrerequisiteEdge(from_node_id="a", to_node_id="b")]

    validate_prerequisite_graph(nodes, edges)
