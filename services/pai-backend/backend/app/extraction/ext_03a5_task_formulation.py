"""Evaluation-only capability task formulations for EXT-03A.5."""

import json

from pydantic import BaseModel, ConfigDict, Field

from app.extraction.two_stage_capability_schema import (
    ExperimentalCapabilityDerivation,
    ExperimentalCvFacts,
)
from app.model_gateway.prompts import PromptTemplate, PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry

OPEN_PROMPT_ID = "cv_capability_open_vocabulary_experiment"
BOUNDED_PROMPT_ID = "cv_capability_bounded_vocabulary_experiment"
HYBRID_PROMPT_ID = "cv_capability_hybrid_mapping_experiment"
EXPERIMENT_VERSION = "1"

CAPABILITY_FAMILIES = (
    "Project Management", "Product Management", "eCommerce",
    "Omnichannel Commerce", "Order Management", "Warehouse Management",
    "Delivery / Logistics Management", "Operations Planning",
    "Digital Platform Development", "Team Leadership", "Process Optimization",
)


class BoundedCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    family: str = Field(min_length=1)
    supporting_statement_ids: list[str] = Field(min_length=1)


class BoundedCapabilityDerivation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    capabilities: list[BoundedCapability] = Field(default_factory=list)


class HybridCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    proposed_name: str = Field(min_length=1)
    mapped_family: str = Field(min_length=1)
    supporting_statement_ids: list[str] = Field(min_length=1)


class HybridCapabilityDerivation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    capabilities: list[HybridCapability] = Field(default_factory=list)


def _statement_ids(facts: ExperimentalCvFacts) -> set[str]:
    return {
        statement.statement_id
        for experience in facts.experiences
        for statement in experience.statements
    }


def _validate_refs(refs: list[str], known: set[str]) -> None:
    missing = sorted(set(refs) - known)
    if missing:
        raise ValueError(f"unknown_statement_ref:{missing[0]}")


def validate_bounded_capabilities(
    output: BoundedCapabilityDerivation, facts: ExperimentalCvFacts
) -> None:
    known = _statement_ids(facts)
    for capability in output.capabilities:
        if capability.family not in CAPABILITY_FAMILIES:
            raise ValueError(f"unknown_capability_family:{capability.family}")
        _validate_refs(capability.supporting_statement_ids, known)


def validate_hybrid_capabilities(
    output: HybridCapabilityDerivation, facts: ExperimentalCvFacts
) -> None:
    known = _statement_ids(facts)
    for capability in output.capabilities:
        if capability.mapped_family not in CAPABILITY_FAMILIES:
            raise ValueError(f"unknown_capability_family:{capability.mapped_family}")
        _validate_refs(capability.supporting_statement_ids, known)


def register_task_formulations(
    prompts: PromptTemplateRegistry, schemas: OutputSchemaRegistry
) -> None:
    base = "Use only supporting_statement_ids present in the supplied facts. Return JSON only."
    prompts.register(PromptTemplate(
        template_id=OPEN_PROMPT_ID, version=EXPERIMENT_VERSION,
        system_instruction="Derive grounded capabilities from factual CV JSON.",
        user_instruction=base + " Return free-form capability names with references. Schema:\n" + json.dumps(ExperimentalCapabilityDerivation.model_json_schema()),
        payload_boundary="input_data",
    ))
    schemas.register(OPEN_PROMPT_ID, EXPERIMENT_VERSION, ExperimentalCapabilityDerivation)
    prompts.register(PromptTemplate(
        template_id=BOUNDED_PROMPT_ID, version=EXPERIMENT_VERSION,
        system_instruction="Map factual CV statements to the supplied bounded capability vocabulary.",
        user_instruction=base + " Select only supported families from this vocabulary: " + json.dumps(CAPABILITY_FAMILIES) + ". Schema:\n" + json.dumps(BoundedCapabilityDerivation.model_json_schema()),
        payload_boundary="input_data",
    ))
    schemas.register(BOUNDED_PROMPT_ID, EXPERIMENT_VERSION, BoundedCapabilityDerivation)
    prompts.register(PromptTemplate(
        template_id=HYBRID_PROMPT_ID, version=EXPERIMENT_VERSION,
        system_instruction="Propose grounded capabilities and map each to one supplied canonical family.",
        user_instruction=base + " Propose a useful capability name, then map it to exactly one family from: " + json.dumps(CAPABILITY_FAMILIES) + ". Schema:\n" + json.dumps(HybridCapabilityDerivation.model_json_schema()),
        payload_boundary="input_data",
    ))
    schemas.register(HYBRID_PROMPT_ID, EXPERIMENT_VERSION, HybridCapabilityDerivation)
