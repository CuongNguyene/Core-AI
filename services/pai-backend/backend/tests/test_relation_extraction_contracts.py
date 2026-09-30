from app.extraction.prompts import (
    CV_ENTITY_RELATION_SCHEMA_ID,
    CV_RELATION_SCHEMA_ID,
    CV_SECTION_EVIDENCE_SCHEMA_ID,
    CV_SECTION_RELATION_SCHEMA_ID,
    JD_REQUIREMENT_SCHEMA_ID,
    RELATION_EXTRACTION_SCHEMA_VERSION,
    register_extraction_contracts,
)
from app.extraction.relation import EntityRelationOutput, SectionEvidenceOutput
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def test_cv_relation_contract_is_registered_and_contextual() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)

    assert (
        schemas.resolve(CV_RELATION_SCHEMA_ID, RELATION_EXTRACTION_SCHEMA_VERSION)
        is EntityRelationOutput
    )
    messages = prompts.resolve(CV_RELATION_SCHEMA_ID, RELATION_EXTRACTION_SCHEMA_VERSION).render(
        {"document": "Implemented model using PyTorch"}
    )
    rendered = "\n".join(message.content for message in messages).lower()
    assert "explicit relationships" in rendered
    assert "production deployment" in rendered
    assert "return json only" in rendered


def test_section_relation_contract_is_bounded_to_input_data() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)

    template = prompts.resolve(CV_SECTION_RELATION_SCHEMA_ID, RELATION_EXTRACTION_SCHEMA_VERSION)
    assert template.payload_boundary == "input_data"
    assert "supplied cv section" in template.system_instruction.lower()


def test_entity_relation_and_section_evidence_contracts_are_registered() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)

    assert (
        schemas.resolve(CV_ENTITY_RELATION_SCHEMA_ID, RELATION_EXTRACTION_SCHEMA_VERSION)
        is EntityRelationOutput
    )
    assert (
        schemas.resolve(CV_SECTION_EVIDENCE_SCHEMA_ID, RELATION_EXTRACTION_SCHEMA_VERSION)
        is SectionEvidenceOutput
    )
    full = prompts.resolve(CV_ENTITY_RELATION_SCHEMA_ID, RELATION_EXTRACTION_SCHEMA_VERSION)
    section = prompts.resolve(CV_SECTION_EVIDENCE_SCHEMA_ID, RELATION_EXTRACTION_SCHEMA_VERSION)
    assert "allowed relations" in full.system_instruction.lower()
    assert "technology mention means mentioned" in section.system_instruction.lower()
    assert section.payload_boundary == "input_data"


def test_jd_requirement_contract_is_registered() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)
    assert schemas.resolve(
        JD_REQUIREMENT_SCHEMA_ID, RELATION_EXTRACTION_SCHEMA_VERSION
    ).__name__ == ("JDExtractionOutput")
    rendered = "\n".join(
        message.content
        for message in prompts.resolve(
            JD_REQUIREMENT_SCHEMA_ID, RELATION_EXTRACTION_SCHEMA_VERSION
        ).render({"document": "production ML deployment"})
    ).lower()
    assert "untrusted data" in rendered
    assert "hiring decisions" in rendered
