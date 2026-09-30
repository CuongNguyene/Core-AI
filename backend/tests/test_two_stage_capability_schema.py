import pytest
from pydantic import ValidationError

from app.extraction.two_stage_capability_schema import (
    CAPABILITY_DERIVATION_EXPERIMENT_PROMPT_ID,
    CAPABILITY_DERIVATION_EXPERIMENT_VERSION,
    FACT_EXTRACTION_EXPERIMENT_PROMPT_ID,
    FACT_EXTRACTION_EXPERIMENT_VERSION,
    ExperimentalCapabilityDerivation,
    ExperimentalCvFacts,
    ExperimentalExperienceFact,
    ExperimentalStatement,
    ExperimentalToolFact,
    normalize_capabilities,
    register_two_stage_experiment,
    validate_capability_references,
    validate_facts_references,
)
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def statement(statement_id: str = "s1", *, document_id: str = "doc-1", page: int = 1) -> ExperimentalStatement:
    return ExperimentalStatement(
        statement_id=statement_id,
        text="Managed production systems and improved reliability.",
        document_id=document_id,
        page_number=page,
    )


def facts(*statements: ExperimentalStatement) -> ExperimentalCvFacts:
    return ExperimentalCvFacts(
        document_id="doc-1",
        experiences=[
            ExperimentalExperienceFact(
                experience_id="exp-1",
                role="Engineer",
                organization="Example",
                statements=list(statements),
            )
        ],
        education=[],
        tools_platforms=[],
    )


def test_duplicate_experience_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate_experience_id"):
        ExperimentalCvFacts(
            document_id="doc-1",
            experiences=[
                ExperimentalExperienceFact(experience_id="exp-1", role="A", statements=[statement()]),
                ExperimentalExperienceFact(experience_id="exp-1", role="B", statements=[statement("s2")]),
            ],
        )


def test_duplicate_statement_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate_statement_id"):
        facts(statement(), statement())


def test_document_and_page_references_are_validated() -> None:
    valid = facts(statement())
    validate_facts_references(valid, expected_document_id="doc-1", page_count=2)
    with pytest.raises(ValueError, match="document_id_mismatch"):
        validate_facts_references(facts(statement(document_id="other")), expected_document_id="doc-1", page_count=2)
    with pytest.raises(ValueError, match="page_out_of_range"):
        validate_facts_references(facts(statement(page=3)), expected_document_id="doc-1", page_count=2)


def test_tools_require_grounded_supporting_statements() -> None:
    with pytest.raises(ValidationError):
        ExperimentalToolFact(name="Unreferenced tool")


def test_stage_two_references_only_known_fact_statements() -> None:
    source = facts(statement())
    output = ExperimentalCapabilityDerivation(capabilities=[{"name": "Reliability Engineering", "supporting_statement_ids": ["s1"]}])
    validate_capability_references(output, source)
    invalid = ExperimentalCapabilityDerivation(capabilities=[{"name": "Reliability Engineering", "supporting_statement_ids": ["missing"]}])
    with pytest.raises(ValueError, match="unknown_statement_ref"):
        validate_capability_references(invalid, source)


def test_one_statement_and_multiple_statements_are_supported() -> None:
    source = facts(statement(), statement("s2"))
    output = ExperimentalCapabilityDerivation(
        capabilities=[
            {"name": "Reliability Engineering", "supporting_statement_ids": ["s1", "s2"]},
            {"name": "Production Operations", "supporting_statement_ids": ["s1"]},
        ]
    )
    validate_capability_references(output, source)


def test_experiment_prompt_and_schema_registration_is_versioned() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_two_stage_experiment(prompts, schemas)
    assert prompts.resolve(FACT_EXTRACTION_EXPERIMENT_PROMPT_ID, FACT_EXTRACTION_EXPERIMENT_VERSION)
    assert prompts.resolve(CAPABILITY_DERIVATION_EXPERIMENT_PROMPT_ID, CAPABILITY_DERIVATION_EXPERIMENT_VERSION)
    assert schemas.resolve(FACT_EXTRACTION_EXPERIMENT_PROMPT_ID, FACT_EXTRACTION_EXPERIMENT_VERSION) is ExperimentalCvFacts
    assert schemas.resolve(CAPABILITY_DERIVATION_EXPERIMENT_PROMPT_ID, CAPABILITY_DERIVATION_EXPERIMENT_VERSION) is ExperimentalCapabilityDerivation


def test_capabilities_are_deduplicated_and_references_merged_deterministically() -> None:
    output = ExperimentalCapabilityDerivation(
        capabilities=[
            {"name": "Omni-channel", "supporting_statement_ids": ["s1"]},
            {"name": "Omni-channel", "supporting_statement_ids": ["s2", "s1"]},
        ]
    )
    normalized = normalize_capabilities(output)
    assert [(item.name, item.supporting_statement_ids) for item in normalized] == [
        ("Omnichannel Commerce", ["s1", "s2"])
    ]
