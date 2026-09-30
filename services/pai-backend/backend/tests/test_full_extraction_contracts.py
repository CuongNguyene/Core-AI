import pytest
from pydantic import ValidationError

from app.extraction.prompts import (
    CV_FULL_SCHEMA_ID,
    FULL_EXTRACTION_SCHEMA_V2_1_VERSION,
    FULL_EXTRACTION_SCHEMA_V2_2_VERSION,
    FULL_EXTRACTION_SCHEMA_V2_VERSION,
    FULL_EXTRACTION_SCHEMA_VERSION,
    JD_FULL_SCHEMA_ID,
    register_extraction_contracts,
)
from app.extraction.schemas import (
    CVFullExtractionOutput,
    CVFullExtractionOutputV2,
    EvidenceClaim,
    EvidenceType,
    JDFullExtractionOutput,
)
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def test_evidence_claim_requires_type_and_source_for_supported_claim() -> None:
    claim = EvidenceClaim(
        value="Python",
        evidence_type=EvidenceType.EXPLICIT_SKILL,
        confidence=0.95,
        evidence_status="supported",
        source_excerpt="Python and FastAPI",
    )

    assert claim.evidence_type is EvidenceType.EXPLICIT_SKILL


def test_evidence_claim_rejects_insufficient_claim_with_invented_evidence() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            value="Python",
            evidence_type=EvidenceType.UNKNOWN,
            confidence=0.4,
            evidence_status="insufficient",
            source_excerpt="Python",
        )


def test_full_output_schemas_preserve_cv_and_jd_field_groups() -> None:
    cv = CVFullExtractionOutput(skills=[], experience=[], education=[])
    jd = JDFullExtractionOutput(required_skills=[], responsibilities=[], qualifications=[])

    assert cv.skills == []
    assert jd.required_skills == []


def test_full_extraction_contracts_are_registered_with_versioned_schemas() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()

    register_extraction_contracts(prompts, schemas)

    assert (
        schemas.resolve(CV_FULL_SCHEMA_ID, FULL_EXTRACTION_SCHEMA_VERSION) is CVFullExtractionOutput
    )
    assert (
        schemas.resolve(JD_FULL_SCHEMA_ID, FULL_EXTRACTION_SCHEMA_VERSION) is JDFullExtractionOutput
    )
    messages = prompts.resolve(CV_FULL_SCHEMA_ID, FULL_EXTRACTION_SCHEMA_VERSION).render(
        {"document": "EXPERIENCE\nPython"}
    )
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert "evidence_type" in messages[1].content


def test_v2_full_cv_schema_is_registered_without_replacing_v1() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()

    register_extraction_contracts(prompts, schemas)

    assert schemas.resolve(CV_FULL_SCHEMA_ID, "2.0") is CVFullExtractionOutputV2
    assert schemas.resolve(CV_FULL_SCHEMA_ID, FULL_EXTRACTION_SCHEMA_VERSION) is CVFullExtractionOutput


def test_v2_prompt_requires_locator_shape_to_match_input_mode() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)

    template = prompts.resolve(CV_FULL_SCHEMA_ID, FULL_EXTRACTION_SCHEMA_V2_VERSION)
    assert template.payload_boundary == "input_data"

    rendered = "\n".join(
        message.content
        for message in template.render(
            {
                "input_mode": "whole_parsed_text",
                "locator_mode": "parsed_text_offsets",
                "document_id": "cv-1",
                "document": "Experience: Python",
            }
        )
    ).lower()

    assert "whole_parsed_text" in rendered
    assert "must return sourcelocator" in rendered
    assert "nativepdflocator is invalid" in rendered


def test_v2_1_prompt_requires_exhaustive_grounded_coverage() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)

    template = prompts.resolve(CV_FULL_SCHEMA_ID, FULL_EXTRACTION_SCHEMA_V2_1_VERSION)
    rendered = "\n".join(message.content for message in template.render({"document": "CV"})).lower()

    for phrase in (
        "every distinct experience record",
        "first page to the last page",
        "every explicit education record",
        "high recall for supported capabilities",
        "every capability must still have grounded evidence",
        "role title alone",
        "do not infer proficiency",
        "tools separate from capabilities",
        "concise evidence excerpts",
    ):
        assert phrase in rendered


def test_v2_2_prompt_derives_capabilities_from_each_experience_record() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)

    template = prompts.resolve(CV_FULL_SCHEMA_ID, FULL_EXTRACTION_SCHEMA_V2_2_VERSION)
    rendered = "\n".join(message.content for message in template.render({"document": "CV"})).lower()

    for phrase in (
        "for every extracted experience record",
        "responsibilities, actions, systems/platforms built",
        "one excerpt to support more than one",
        "do not derive capabilities only from the summary",
        "title alone is not sufficient evidence",
        "do not infer proficiency",
        "keep tools separate from capabilities",
        "every capability must still have grounded evidence",
    ):
        assert phrase in rendered
    assert schemas.resolve(CV_FULL_SCHEMA_ID, FULL_EXTRACTION_SCHEMA_V2_2_VERSION) is CVFullExtractionOutputV2
