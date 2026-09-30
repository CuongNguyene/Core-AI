from app.extraction.prompts import (
    CV_SECTION_SCHEMA_ID,
    JD_SECTION_SCHEMA_ID,
    SECTION_EXTRACTION_SCHEMA_VERSION,
    register_extraction_contracts,
)
from app.extraction.schemas import (
    CVSectionExtractionOutput,
    EvidenceType,
    JDSectionExtractionOutput,
)
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def test_section_contracts_register_versioned_cv_and_jd_schemas() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()

    register_extraction_contracts(prompts, schemas)

    assert schemas.resolve(CV_SECTION_SCHEMA_ID, SECTION_EXTRACTION_SCHEMA_VERSION) is (
        CVSectionExtractionOutput
    )
    assert schemas.resolve(JD_SECTION_SCHEMA_ID, SECTION_EXTRACTION_SCHEMA_VERSION) is (
        JDSectionExtractionOutput
    )


def test_cv_section_prompt_scopes_model_to_current_section() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)

    messages = prompts.resolve(CV_SECTION_SCHEMA_ID, SECTION_EXTRACTION_SCHEMA_VERSION).render(
        {"section_type": "skills", "section_text": "Python"}
    )

    rendered = "\n".join(message.content for message in messages)
    assert "section_type" in rendered
    assert "section_text" in rendered
    assert "current section" in rendered.lower()
    assert "explicit_skill" in rendered.lower()
    assert "evidence_type" in rendered
    assert EvidenceType.EXPLICIT_SKILL.value in rendered
