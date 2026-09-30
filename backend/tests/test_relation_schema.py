import pytest
from pydantic import ValidationError

from app.extraction.relation import EntityRelation, EntityRelationOutput, RelationType


def test_entity_relation_preserves_allowed_relation_and_excerpt() -> None:
    relation = EntityRelation(
        subject="Kafka",
        relation=RelationType.USED_IN,
        object="real-time sentiment analysis system",
        evidence_excerpt="Developed real-time sentiment analysis system using Kafka and Spark",
        confidence=0.95,
    )
    assert relation.relation is RelationType.USED_IN
    assert EntityRelationOutput(relations=[relation]).relations[0].subject == "Kafka"


def test_entity_relation_rejects_unknown_relation_and_empty_evidence() -> None:
    with pytest.raises(ValidationError):
        EntityRelation(
            subject="Kafka",
            relation="owned",
            object="system",
            evidence_excerpt="supported",
            confidence=0.9,
        )
    with pytest.raises(ValidationError):
        EntityRelation(
            subject="Kafka",
            relation=RelationType.USED_IN,
            object="system",
            evidence_excerpt="",
            confidence=0.9,
        )
