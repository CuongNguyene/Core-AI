from __future__ import annotations

import pytest

from app.job_semantics_eval.contracts import JobRequirementExtractionOutputV1
from app.job_semantics_eval.provider import (
    PROMPT_ID,
    SCHEMA_ID,
    extract_requirements,
    provider_input,
    register_extractor_contracts,
)
from app.job_semantics_eval.source_adapter import build_source_blocks
from app.model_gateway.contracts import InferenceAuditMetadata, StructuredInferenceResponse
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


class FakeGateway:
    def __init__(self) -> None:
        self.request = None
        self.output = JobRequirementExtractionOutputV1(
            statements=[
                {
                    "source_block_ids": ["jdblock:JOB_DESCRIPTION:0001"],
                    "source_text": "Design REST APIs.",
                    "normalized_statement": "Design REST APIs.",
                    "statement_type": "RESPONSIBILITY",
                    "capability_relevance": "CAPABILITY_BEARING",
                }
            ]
        )

    async def infer_structured(self, request, output_schema):
        self.request = request
        assert output_schema is JobRequirementExtractionOutputV1
        return StructuredInferenceResponse(
            parsed=self.output,
            audit=InferenceAuditMetadata(
                provider="fake",
                model="fake-model",
                prompt_template_id=PROMPT_ID,
                prompt_template_version="1.0",
                output_schema_id=SCHEMA_ID,
                output_schema_version="1.0",
                policy_version="test",
                correlation_id=request.correlation_id,
                routing_decision="test",
                attempt_count=1,
                latency_ms=1,
                usage={},
                outcome="succeeded",
            ),
        )

    async def infer_text(self, request):
        raise AssertionError("text inference is not used")


def test_provider_projection_has_only_allowlisted_source_blocks() -> None:
    source = {
        "source_application_ref": "private-ref",
        "job_posting_url": "/private-url",
        "job_description_html": "<p>Design REST APIs.</p>",
        "job_requirements_html": "<p>Build secure services.</p>",
    }
    blocks = build_source_blocks(source)
    projected = provider_input(blocks).model_dump(mode="json")
    assert set(projected) == {"source_blocks"}
    assert set(projected["source_blocks"][0]) == {"block_id", "source_field", "text"}
    assert "private-ref" not in str(projected)
    assert "/private-url" not in str(projected)


@pytest.mark.asyncio
async def test_extractor_uses_restricted_gateway_and_server_validates_provenance() -> None:
    blocks = build_source_blocks({"job_description_html": "<p>Design REST APIs.</p>"})
    gateway = FakeGateway()
    statements, audit, count, output_hash = await extract_requirements(
        gateway, blocks, input_fingerprint="sha256:abc"
    )
    assert gateway.request.data_classification.value == "restricted"
    assert gateway.request.purpose.value == "jd_extraction"
    assert statements[0].source_field == "JOB_DESCRIPTION"
    assert statements[0].start_offset == 0
    assert audit.provider == "fake"
    assert count == 1
    assert output_hash.startswith("sha256:")


def test_contract_registration_uses_exact_strict_output_schema() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extractor_contracts(prompts, schemas)
    prompt = prompts.resolve(PROMPT_ID, "1.0")
    assert "untrusted" in prompt.system_instruction
    assert schemas.resolve(SCHEMA_ID, "1.0") is JobRequirementExtractionOutputV1
