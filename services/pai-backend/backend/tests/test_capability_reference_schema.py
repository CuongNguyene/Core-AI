import pytest
from pydantic import ValidationError

from app.extraction.capability_reference_schema import (
    CAPABILITY_REFERENCE_EXPERIMENT_PROMPT_ID,
    CAPABILITY_REFERENCE_EXPERIMENT_VERSION,
    ExperimentalCapability,
    ExperimentalCvExtraction,
    ExperimentalEvidenceItem,
    ExperimentalExperience,
    experimental_to_v2,
    register_capability_reference_experiment,
)
from app.extraction.schemas import NativePdfLocator
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def _evidence(evidence_id: str, local_id: str = "exp-1") -> ExperimentalEvidenceItem:
    return ExperimentalEvidenceItem(
        evidence_id=evidence_id,
        context=local_id,
        source_excerpt="Built and managed the platform.",
        source_locator=NativePdfLocator(
            document_id="doc-1", page_number=1, section="experience"
        ),
    )


def _experience() -> ExperimentalExperience:
    return ExperimentalExperience(local_id="exp-1", title="Project Lead", evidence_refs=["ev-1"])


def test_duplicate_evidence_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate_evidence_id"):
        ExperimentalCvExtraction(
            evidence_inventory=[_evidence("ev-1"), _evidence("ev-1")],
            experience=[_experience()],
        )


def test_dangling_capability_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown_capability_evidence_ref"):
        ExperimentalCvExtraction(
            evidence_inventory=[_evidence("ev-1")],
            experience=[_experience()],
            capabilities=[ExperimentalCapability(raw_name="Project Management", evidence_refs=["missing"])],
        )


def test_one_capability_can_reference_multiple_experiences() -> None:
    result = ExperimentalCvExtraction(
        evidence_inventory=[_evidence("ev-1", "exp-1"), _evidence("ev-2", "exp-2")],
        experience=[_experience(), ExperimentalExperience(local_id="exp-2", title="Manager", evidence_refs=["ev-2"])],
        capabilities=[ExperimentalCapability(raw_name="Project Management", evidence_refs=["ev-1", "ev-2"])],
    )

    assert result.capabilities[0].evidence_refs == ["ev-1", "ev-2"]


def test_reference_schema_projects_to_legacy_v2_without_losing_experience() -> None:
    result = ExperimentalCvExtraction(
        evidence_inventory=[_evidence("ev-1")],
        experience=[_experience()],
        capabilities=[ExperimentalCapability(raw_name="Project Management", evidence_refs=["ev-1"])],
    )

    projected = experimental_to_v2(result, document_id="doc-1")

    assert projected.experience[0].title == "Project Lead"
    assert projected.capabilities[0].canonical_name == "Project Management"


def test_reference_experiment_prompt_and_schema_are_registered_separately() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_capability_reference_experiment(prompts, schemas)

    template = prompts.resolve(
        CAPABILITY_REFERENCE_EXPERIMENT_PROMPT_ID,
        CAPABILITY_REFERENCE_EXPERIMENT_VERSION,
    )
    rendered = "\n".join(message.content for message in template.render({"document": "CV"})).lower()
    assert "evidence_inventory" in rendered
    assert "evidence_refs" in rendered
    assert "do not repeat source excerpts" in rendered
    assert schemas.resolve(
        CAPABILITY_REFERENCE_EXPERIMENT_PROMPT_ID,
        CAPABILITY_REFERENCE_EXPERIMENT_VERSION,
    ) is ExperimentalCvExtraction
