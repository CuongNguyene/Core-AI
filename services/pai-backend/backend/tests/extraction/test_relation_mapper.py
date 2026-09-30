from app.extraction.evidence import EvidenceContext
from app.extraction.relation_mapper import map_relation_to_evidence_context


def test_used_in_academic_project_maps_to_project() -> None:
    assert (
        map_relation_to_evidence_context("used_in", "Kafka", "real-time academic project")
        is EvidenceContext.USED_IN_PROJECT
    )


def test_deployed_production_service_maps_to_production() -> None:
    assert (
        map_relation_to_evidence_context("deployed", "PyTorch", "production inference service")
        is EvidenceContext.USED_IN_PRODUCTION
    )


def test_used_in_production_wording_does_not_replace_deployed_relation() -> None:
    assert (
        map_relation_to_evidence_context("used_in", "PyTorch", "production inference service")
        is EvidenceContext.USED_IN_PROJECT
    )


def test_plain_mention_does_not_upgrade_context() -> None:
    assert (
        map_relation_to_evidence_context("used_in", "Python", "coursework mention")
        is EvidenceContext.USED_IN_PROJECT
    )


def test_owned_and_led_map_to_explicit_contexts() -> None:
    assert (
        map_relation_to_evidence_context("owned", "API", "platform") is EvidenceContext.OWNED_SYSTEM
    )
    assert map_relation_to_evidence_context("led", "team", "project") is EvidenceContext.LED_TEAM
