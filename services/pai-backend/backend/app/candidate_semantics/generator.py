"""ModelGateway-backed ephemeral semantic relation proposals."""

import json
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from app.candidate_semantics.contracts import (
    CandidateSemanticEvidenceInput,
    SemanticEvidenceProposalV1,
    SemanticProposalValidationStatus,
    StructuredCandidateEvidenceBasis,
    StructuredCandidateSourceLocator,
    TargetCapabilityContext,
)
from app.candidate_semantics.prompts import (
    RELATION_OUTPUT_SCHEMA_ID,
    RELATION_OUTPUT_SCHEMA_VERSION,
    RELATION_PROMPT_ID,
    RELATION_PROMPT_VERSION,
    SemanticRelationModelOutput,
)
from app.model_gateway.contracts import (
    DataClassification,
    InferencePurpose,
    InferenceRequest,
    ModelGateway,
    OutputContract,
)

GENERATOR_ID = "candidate_semantic_relation"
GENERATOR_VERSION = "1.0"


async def propose_semantic_relation(
    gateway: ModelGateway,
    *,
    target: TargetCapabilityContext,
    evidence: CandidateSemanticEvidenceInput,
    source_basis: StructuredCandidateEvidenceBasis,
) -> SemanticEvidenceProposalV1:
    """Ask the configured gateway to propose a relation; attach all trusted data server-side."""
    if (
        source_basis.candidate_ref != evidence.candidate_ref
        or source_basis.source_system != evidence.source_system
        or source_basis.source_revision != evidence.source_revision
        or source_basis.snapshot_ref != evidence.snapshot_ref
        or source_basis.content_fingerprint != evidence.content_fingerprint
        or source_basis.transport_schema_version != evidence.transport_schema_version
    ):
        raise ValueError("source basis does not match evidence")

    fingerprint_payload = {
        "target_pin": target.definition_pin.model_dump(mode="json"),
        "target_definition": target.definition.model_dump(mode="json"),
        "evidence": evidence.model_dump(mode="json"),
        "source_basis": source_basis.model_dump(mode="json"),
        "generator_id": GENERATOR_ID,
        "generator_version": GENERATOR_VERSION,
        "prompt_template_id": RELATION_PROMPT_ID,
        "prompt_template_version": RELATION_PROMPT_VERSION,
        "output_schema_id": RELATION_OUTPUT_SCHEMA_ID,
        "output_schema_version": RELATION_OUTPUT_SCHEMA_VERSION,
    }
    canonical = json.dumps(
        fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    fingerprint = "sha256:" + sha256(canonical.encode("utf-8")).hexdigest()
    correlation_id = str(uuid5(NAMESPACE_URL, fingerprint))
    request = InferenceRequest(
        purpose=InferencePurpose.COMPETENCY_MAPPING,
        data_classification=DataClassification.RESTRICTED,
        prompt_template_id=RELATION_PROMPT_ID,
        prompt_template_version=RELATION_PROMPT_VERSION,
        payload={
            "target": {
                "ref": str(target.definition_pin.capability_ref),
                "label": target.definition.label,
                "definition": target.definition.definition,
            },
            "evidence": [{"kind": evidence.source_kind.value, "content": evidence.content}],
        },
        output_contract=OutputContract(
            schema_id=RELATION_OUTPUT_SCHEMA_ID,
            schema_version=RELATION_OUTPUT_SCHEMA_VERSION,
            strict=True,
        ),
        temperature=0,
        output_token_budget=400,
        correlation_id=correlation_id,
    )
    response = await gateway.infer_structured(request, SemanticRelationModelOutput)
    parsed = response.parsed
    return SemanticEvidenceProposalV1(
        target_ref=target.definition_pin.capability_ref,
        relation=parsed.relation,
        validation_status=SemanticProposalValidationStatus.UNVALIDATED,
        rationale=parsed.rationale,
        source_locator=StructuredCandidateSourceLocator(
            source_system=evidence.source_system,
            snapshot_ref=evidence.snapshot_ref,
            source_revision=evidence.source_revision,
            field_path=evidence.field_path,
            source_record_ref=evidence.source_record_ref,
        ),
        source_basis=source_basis,
        generator_id=GENERATOR_ID,
        generator_version=GENERATOR_VERSION,
        prompt_template_id=RELATION_PROMPT_ID,
        prompt_template_version=RELATION_PROMPT_VERSION,
        output_schema_id=RELATION_OUTPUT_SCHEMA_ID,
        output_schema_version=RELATION_OUTPUT_SCHEMA_VERSION,
        input_fingerprint=fingerprint,
        audit=response.audit,
    )
