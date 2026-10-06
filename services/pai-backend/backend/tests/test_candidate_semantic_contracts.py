from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.candidate_semantics.contracts import (
    CandidateSemanticEvidenceInput,
    CandidateSemanticEvidenceKind,
    SemanticEvidenceProposalV1,
    SemanticProposalValidationStatus,
    SemanticRelation,
    StructuredCandidateEvidenceBasis,
    StructuredCandidateSourceLocator,
    TargetCapabilityContext,
)
from app.capability_governance.definitions import CapabilityDefinition
from app.capability_governance.identity import CanonicalCapabilityRef
from app.capability_governance.packs import CapabilityPackId, CapabilityPackReleaseRef
from app.capability_governance.resolution import CapabilityDefinitionPin
from app.model_gateway.contracts import InferenceAuditMetadata, ModelUsage


def target_context() -> TargetCapabilityContext:
    ref = CanonicalCapabilityRef.parse("capability:test_core:project_management")
    definition = CapabilityDefinition(
        canonical_ref=ref,
        label="Project Management",
        definition="Plan and coordinate project delivery.",
    )
    pin = CapabilityDefinitionPin(
        capability_ref=ref,
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=CapabilityPackId("test_core_pack"),
            version="1.0",
            checksum="sha256:" + "b" * 64,
        ),
    )
    return TargetCapabilityContext(definition_pin=pin, definition=definition)


def evidence() -> CandidateSemanticEvidenceInput:
    return CandidateSemanticEvidenceInput(
        candidate_ref="candidate:42",
        source_system="hrm",
        source_revision=3,
        snapshot_ref="snapshot:abc",
        content_fingerprint="sha256:" + "a" * 64,
        source_kind=CandidateSemanticEvidenceKind.EMPLOYMENT,
        source_record_ref="employment:7",
        field_path="candidate_source.career_history[0].responsibilities",
        content="Coordinated project milestones with three teams.",
    )


def basis() -> StructuredCandidateEvidenceBasis:
    return StructuredCandidateEvidenceBasis(
        candidate_ref="candidate:42",
        source_system="hrm",
        source_revision=3,
        snapshot_ref="snapshot:abc",
        content_fingerprint="sha256:" + "a" * 64,
    )


def locator() -> StructuredCandidateSourceLocator:
    return StructuredCandidateSourceLocator(
        source_system="hrm",
        snapshot_ref="snapshot:abc",
        source_revision=3,
        field_path="candidate_source.career_history[0].responsibilities",
        source_record_ref="employment:7",
    )


def audit() -> InferenceAuditMetadata:
    return InferenceAuditMetadata(
        provider="mock",
        model="test-model",
        prompt_template_id="candidate_semantic_relation",
        prompt_template_version="1.0",
        output_schema_id="candidate_semantic_relation",
        output_schema_version="1.0",
        policy_version="1.0",
        correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        routing_decision="local",
        attempt_count=1,
        latency_ms=0,
        usage=ModelUsage(input_tokens=12, output_tokens=8),
        outcome="success",
    )


def proposal(**overrides: object) -> SemanticEvidenceProposalV1:
    values: dict[str, object] = {
        "target_ref": "capability:test_core:project_management",
        "relation": SemanticRelation.DIRECT_SUPPORT,
        "validation_status": SemanticProposalValidationStatus.UNVALIDATED,
        "rationale": "The source explicitly describes coordinating project work.",
        "source_locator": locator(),
        "source_basis": basis(),
        "generator_id": "candidate_semantic_relation",
        "generator_version": "1.0",
        "prompt_template_id": "candidate_semantic_relation",
        "prompt_template_version": "1.0",
        "output_schema_id": "candidate_semantic_relation",
        "output_schema_version": "1.0",
        "input_fingerprint": "sha256:" + "c" * 64,
        "audit": audit(),
    }
    values.update(overrides)
    return SemanticEvidenceProposalV1.model_validate(values)


def test_semantic_relation_contract_has_exact_five_values() -> None:
    assert {item.value for item in SemanticRelation} == {
        "DIRECT_SUPPORT",
        "PARTIAL_SUPPORT",
        "NO_SUPPORT",
        "CONTRADICTORY",
        "CONTEXT_MISMATCH",
    }


def test_evidence_and_proposal_preserve_source_provenance_without_confidence() -> None:
    item = evidence()
    result = proposal()

    assert item.field_path == "candidate_source.career_history[0].responsibilities"
    assert result.source_locator.snapshot_ref == "snapshot:abc"
    assert result.source_basis.content_fingerprint == "sha256:" + "a" * 64
    assert result.validation_status is SemanticProposalValidationStatus.UNVALIDATED
    assert "confidence" not in result.model_dump()
    assert "confidence" not in item.model_dump()


def test_target_context_rejects_definition_that_does_not_match_exact_pin() -> None:
    target = target_context()
    other_definition = target.definition.model_copy(
        update={"canonical_ref": CanonicalCapabilityRef.parse("capability:test_core:delivery")}
    )

    with pytest.raises(ValidationError):
        TargetCapabilityContext(definition_pin=target.definition_pin, definition=other_definition)


@pytest.mark.parametrize("relation", list(SemanticRelation))
def test_proposal_accepts_each_relation_but_always_unvalidated(
    relation: SemanticRelation,
) -> None:
    result = proposal(relation=relation)

    assert result.relation is relation
    assert result.validation_status is SemanticProposalValidationStatus.UNVALIDATED


@pytest.mark.parametrize("rationale", ["", "  ", "x" * 1001])
def test_proposal_rejects_blank_or_unbounded_rationale(rationale: str) -> None:
    with pytest.raises(ValidationError):
        proposal(rationale=rationale)


def test_evidence_rejects_injected_confidence_or_capability_status_fields() -> None:
    values = evidence().model_dump()

    with pytest.raises(ValidationError):
        CandidateSemanticEvidenceInput.model_validate({**values, "confidence": 0.99})
    with pytest.raises(ValidationError):
        CandidateSemanticEvidenceInput.model_validate({**values, "capability_status": "verified"})


def test_proposal_rejects_confidence_and_validated_lifecycle_status() -> None:
    with pytest.raises(ValidationError):
        proposal(confidence=0.99)
    with pytest.raises(ValidationError):
        proposal(validation_status="VALIDATED")
