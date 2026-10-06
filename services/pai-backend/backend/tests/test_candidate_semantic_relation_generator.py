from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.candidate_semantics.contracts import (
    CandidateSemanticEvidenceInput,
    CandidateSemanticEvidenceKind,
    SemanticProposalValidationStatus,
    SemanticRelation,
    StructuredCandidateEvidenceBasis,
    TargetCapabilityContext,
)
from app.candidate_semantics.generator import propose_semantic_relation
from app.candidate_semantics.prompts import (
    RELATION_OUTPUT_SCHEMA_ID,
    RELATION_OUTPUT_SCHEMA_VERSION,
    RELATION_PROMPT_ID,
    RELATION_PROMPT_VERSION,
)
from app.capability_analysis import rules as legacy_capability_rules
from app.capability_governance.definitions import CapabilityDefinition
from app.capability_governance.identity import CanonicalCapabilityRef
from app.capability_governance.packs import CapabilityPackId, CapabilityPackReleaseRef
from app.capability_governance.resolution import CapabilityDefinitionPin
from app.model_gateway.contracts import (
    DataClassification,
    InferenceAuditMetadata,
    InferencePurpose,
    InferenceRequest,
    ModelUsage,
    StructuredInferenceResponse,
)


class RecordingGateway:
    def __init__(self, parsed: dict[str, object]) -> None:
        self.parsed = parsed
        self.request: InferenceRequest | None = None
        self.schema: type[BaseModel] | None = None

    async def infer_structured(
        self, request: InferenceRequest, output_schema: type[BaseModel]
    ) -> StructuredInferenceResponse[Any]:
        self.request = request
        self.schema = output_schema
        parsed = output_schema.model_validate_json(json.dumps(self.parsed), strict=True)
        return StructuredInferenceResponse(parsed=parsed, audit=audit())

    async def infer_text(self, request: InferenceRequest) -> Any:
        raise AssertionError("relation proposals must use structured inference")


def target() -> TargetCapabilityContext:
    ref = CanonicalCapabilityRef.parse("capability:test_core:project_management")
    return TargetCapabilityContext(
        definition_pin=CapabilityDefinitionPin(
            capability_ref=ref,
            pack_release_ref=CapabilityPackReleaseRef(
                pack_id=CapabilityPackId("test_core_pack"),
                version="1.0",
                checksum="sha256:" + "b" * 64,
            ),
        ),
        definition=CapabilityDefinition(
            canonical_ref=ref,
            label="Project Management",
            definition="Plan and coordinate project delivery.",
        ),
    )


def evidence(content: str = "Coordinated milestones.") -> CandidateSemanticEvidenceInput:
    return CandidateSemanticEvidenceInput(
        candidate_ref="candidate:42",
        source_system="HRM",
        source_revision=17,
        snapshot_ref="snapshot:abc",
        content_fingerprint="a" * 64,
        source_kind=CandidateSemanticEvidenceKind.EMPLOYMENT,
        source_record_ref="career-1",
        field_path="candidate_source.career_history[0].responsibilities",
        content=content,
    )


def basis() -> StructuredCandidateEvidenceBasis:
    return StructuredCandidateEvidenceBasis(
        candidate_ref="candidate:42",
        source_system="HRM",
        source_revision=17,
        snapshot_ref="snapshot:abc",
        content_fingerprint="a" * 64,
    )


def audit() -> InferenceAuditMetadata:
    return InferenceAuditMetadata(
        provider="local-mock",
        model="relation-test-model",
        model_revision="r1",
        prompt_template_id=RELATION_PROMPT_ID,
        prompt_template_version=RELATION_PROMPT_VERSION,
        output_schema_id=RELATION_OUTPUT_SCHEMA_ID,
        output_schema_version=RELATION_OUTPUT_SCHEMA_VERSION,
        policy_version="privacy-1",
        correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        routing_decision="local",
        attempt_count=1,
        latency_ms=7,
        usage=ModelUsage(input_tokens=32, output_tokens=9),
        outcome="succeeded",
        protocol="test",
        deployment_type="local",
        data_boundary="local",
    )


@pytest.mark.asyncio
async def test_gateway_receives_one_restricted_evidence_and_result_uses_server_provenance() -> None:
    gateway = RecordingGateway(
        {"relation": "DIRECT_SUPPORT", "rationale": "Explicit coordination of delivery milestones."}
    )

    proposal = await propose_semantic_relation(
        gateway, target=target(), evidence=evidence(), source_basis=basis()
    )

    request = gateway.request
    assert request is not None
    assert request.purpose is InferencePurpose.COMPETENCY_MAPPING
    assert request.data_classification is DataClassification.RESTRICTED
    assert request.prompt_template_id == RELATION_PROMPT_ID
    assert request.prompt_template_version == RELATION_PROMPT_VERSION
    assert request.output_contract is not None
    assert (request.output_contract.schema_id, request.output_contract.schema_version) == (
        RELATION_OUTPUT_SCHEMA_ID,
        RELATION_OUTPUT_SCHEMA_VERSION,
    )
    assert set(request.payload) == {"target", "evidence"}
    assert isinstance(request.payload["evidence"], list)
    assert len(request.payload["evidence"]) == 1
    assert set(request.payload["evidence"][0]) == {"kind", "content"}
    assert proposal.source_locator.source_record_ref == "career-1"
    assert (
        proposal.source_locator.field_path == "candidate_source.career_history[0].responsibilities"
    )
    assert proposal.source_basis.snapshot_ref == "snapshot:abc"
    assert proposal.validation_status is SemanticProposalValidationStatus.UNVALIDATED
    assert proposal.audit.provider == "local-mock"
    assert proposal.audit.usage.output_tokens == 9
    assert proposal.relation is SemanticRelation.DIRECT_SUPPORT


@pytest.mark.parametrize(
    "model_output",
    [
        {"relation": "NOT_A_RELATION", "rationale": "Unsupported."},
        {"relation": "DIRECT_SUPPORT", "rationale": "Grounded.", "confidence": 0.99},
        {"relation": "DIRECT_SUPPORT", "rationale": "Grounded.", "validation_status": "VALIDATED"},
        {
            "relation": "DIRECT_SUPPORT",
            "rationale": "Grounded.",
            "source_locator": {"snapshot_ref": "forged"},
        },
    ],
)
@pytest.mark.asyncio
async def test_generator_rejects_malformed_or_lifecycle_bearing_model_output(
    model_output: dict[str, object],
) -> None:
    gateway = RecordingGateway(model_output)

    with pytest.raises(ValidationError):
        await propose_semantic_relation(
            gateway, target=target(), evidence=evidence(), source_basis=basis()
        )


@pytest.mark.asyncio
async def test_generator_rejects_source_basis_that_does_not_match_evidence() -> None:
    gateway = RecordingGateway({"relation": "NO_SUPPORT", "rationale": "No supporting fact."})
    mismatched = basis().model_copy(update={"source_revision": 16})

    with pytest.raises(ValueError, match="source basis does not match evidence"):
        await propose_semantic_relation(
            gateway, target=target(), evidence=evidence(), source_basis=mismatched
        )
    assert gateway.request is None


@pytest.mark.asyncio
async def test_direct_support_proposal_never_invokes_legacy_capability_evaluator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_evaluated(*args: object, **kwargs: object) -> None:
        raise AssertionError("unvalidated candidate relation reached the legacy evaluator")

    monkeypatch.setattr(legacy_capability_rules, "evaluate_target", fail_if_evaluated)
    gateway = RecordingGateway(
        {"relation": "DIRECT_SUPPORT", "rationale": "Explicit coordination of project delivery."}
    )

    proposal = await propose_semantic_relation(
        gateway, target=target(), evidence=evidence(), source_basis=basis()
    )

    serialized = proposal.model_dump(mode="json")
    assert proposal.validation_status is SemanticProposalValidationStatus.UNVALIDATED
    assert proposal.relation is SemanticRelation.DIRECT_SUPPORT
    assert not {
        "confidence",
        "capability_status",
        "capability_level",
        "gap",
        "readiness",
    }.intersection(serialized)
