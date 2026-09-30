from app.extraction.prompts import (
    JD_REQUIREMENT_SCHEMA_ID,
    JD_REQUIREMENT_SCHEMA_VERSION,
    register_extraction_contracts,
)
from app.extraction.schemas import JDRequirementExtractionOutputV2
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def test_jd_requirement_contract_is_atomic_and_registered_as_v2() -> None:
    output = JDRequirementExtractionOutputV2(requirements=[])
    assert output.requirements == []

    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)

    assert schemas.resolve(JD_REQUIREMENT_SCHEMA_ID, JD_REQUIREMENT_SCHEMA_VERSION) is (
        JDRequirementExtractionOutputV2
    )
    rendered = "\n".join(
        message.content
        for message in prompts.resolve(
            JD_REQUIREMENT_SCHEMA_ID, JD_REQUIREMENT_SCHEMA_VERSION
        ).render({"document": "Mentoring junior engineers"})
    ).lower()
    assert "atomic" in rendered
    assert "do not infer" in rendered
    assert "stable unique requirement_id" in rendered
    assert "backend owns sourcelocator.document_id" in rendered
    assert "do not use a field named value" in rendered
    assert "do not emit unknown or insufficient placeholder rows" in rendered


def test_jd_requirement_prompt_requires_full_coverage_and_semantic_classification() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)

    rendered = "\n".join(
        message.content
        for message in prompts.resolve(
            JD_REQUIREMENT_SCHEMA_ID, JD_REQUIREMENT_SCHEMA_VERSION
        ).render({"document": "Prepare reports; PMP preferred; 3 years ERP experience"})
    ).lower()

    assert "every materially distinct explicit" in rendered
    assert "preferred" in rendered
    assert "responsibility" in rendered
    assert "credential" in rendered
    assert "experience" in rendered
    assert "or" in rendered


def test_jd_requirement_prompt_preserves_exclusions_optionality_and_full_lists() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_extraction_contracts(prompts, schemas)

    rendered = "\n".join(
        message.content
        for message in prompts.resolve(
            JD_REQUIREMENT_SCHEMA_ID, JD_REQUIREMENT_SCHEMA_VERSION
        ).render({"document": "May support onboarding; preferred: BigQuery, dbt, analytics"})
    ).lower()

    assert "scope exclusion" in rendered
    assert "not required" in rendered
    assert "preserve optionality" in rendered
    assert "never strengthen" in rendered
    assert "independently meaningful" in rendered
    assert "broad summary" in rendered
