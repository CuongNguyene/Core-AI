import pytest

from app.capability_analysis.domain_packs.contracts import DomainPackReference
from app.capability_analysis.domain_packs.it_ai import IT_AI_PACK
from app.capability_analysis.domain_packs.registry import (
    DomainPackRegistry,
    DomainPackUnavailableError,
)
from app.capability_analysis.retrieval import canonical_concepts


def test_registry_resolves_only_exact_pack_id_and_version() -> None:
    registry = DomainPackRegistry((IT_AI_PACK,))

    resolved = registry.resolve(DomainPackReference(pack_id="it_ai", version="1"))

    assert resolved is IT_AI_PACK
    assert resolved.pack_id == "it_ai"
    assert resolved.version == "1"


@pytest.mark.parametrize(
    ("pack_id", "version"),
    [("it_ai", "2"), ("sales", "1"), ("IT_AI", "1")],
)
def test_registry_rejects_unavailable_or_inexact_references_safely(
    pack_id: str,
    version: str,
) -> None:
    registry = DomainPackRegistry((IT_AI_PACK,))

    with pytest.raises(DomainPackUnavailableError) as raised:
        registry.resolve(DomainPackReference(pack_id=pack_id, version=version))

    assert raised.value.code == "domain_pack_unavailable"
    assert raised.value.pack_reference == DomainPackReference(pack_id, version)


def test_registry_preserves_explicit_pack_reference_order() -> None:
    registry = DomainPackRegistry((IT_AI_PACK,))
    references = (
        DomainPackReference(pack_id="it_ai", version="1"),
        DomainPackReference(pack_id="it_ai", version="1"),
    )

    assert registry.resolve_ordered(references) == (IT_AI_PACK, IT_AI_PACK)


def test_it_aliases_resolve_only_when_it_ai_pack_is_explicitly_supplied() -> None:
    assert canonical_concepts("Used Apache Kafka") == {"used_apache_kafka"}
    assert canonical_concepts("Used Apache Kafka", domain_pack=IT_AI_PACK) == {"kafka"}


def test_it_ai_pack_exposes_hints_but_never_an_assessment_status() -> None:
    hints = IT_AI_PACK.map_requirement_phrase("Docker")

    assert hints.concepts == ("docker",)
    assert hints.evidence_expectations == (("docker", "demonstrated_usage"),)
    assert not hasattr(hints, "status")


def test_it_ai_pack_abstains_for_unknown_requirement_and_evidence_phrases() -> None:
    assert IT_AI_PACK.map_requirement_phrase("generic capability").concepts == ()
    assert IT_AI_PACK.map_requirement_phrase("generic capability").evidence_expectations == ()
    assert IT_AI_PACK.map_evidence_phrase("generic capability").concepts == ()
