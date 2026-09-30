"""Immutable, evaluation-only capability taxonomy for CV extraction."""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.extraction.two_stage_capability_schema import ExperimentalCvFacts
from app.model_gateway.prompts import PromptTemplate, PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry

TAXONOMY_ID = "professional_capability_core"
TAXONOMY_VERSION = "0.1"
Classification = Literal[
    "CORE", "DOMAIN_SPECIFIC", "MERGE_CANDIDATE", "SPLIT_CANDIDATE", "EVALUATOR_ONLY"
]


class CapabilityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    category: str | None = Field(default=None, min_length=1)
    classification: Classification


class CapabilityTaxonomy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    taxonomy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    capabilities: tuple[CapabilityDefinition, ...] = Field(min_length=1)


class TaxonomySelectedCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    capability_id: str = Field(min_length=1)
    supporting_statement_ids: list[str] = Field(min_length=1)


class TaxonomySelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    taxonomy_id: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    capabilities: list[TaxonomySelectedCapability] = Field(default_factory=list)


def _definition(capability_id: str, name: str, description: str, aliases: tuple[str, ...], category: str, classification: Classification) -> CapabilityDefinition:
    return CapabilityDefinition(id=capability_id, name=name, description=description, aliases=aliases, category=category, classification=classification)


PROFESSIONAL_CAPABILITY_CORE = CapabilityTaxonomy(
    taxonomy_id=TAXONOMY_ID,
    version=TAXONOMY_VERSION,
    capabilities=(
        _definition("project_management", "Project Management", "Planning, coordinating, executing and delivering projects across scope, resources, timelines or stakeholders.", ("project delivery",), "PROJECT", "CORE"),
        _definition("product_management", "Product Management", "Defining, prioritizing and guiding products, platforms or product outcomes for users and stakeholders.", ("product ownership",), "PRODUCT", "CORE"),
        _definition("ecommerce", "eCommerce", "Operating or delivering commerce activities through electronic sales channels and digital commerce processes.", ("e-commerce", "electronic commerce"), "COMMERCE", "DOMAIN_SPECIFIC"),
        _definition("omnichannel_commerce", "Omnichannel Commerce", "Coordinating commerce experiences, inventory or customer journeys across multiple connected channels.", ("omni channel", "omnichannel", "o2o commerce"), "COMMERCE", "DOMAIN_SPECIFIC"),
        _definition("order_management", "Order Management", "Managing order lifecycle, fulfillment coordination, order processing or related operational controls.", ("order fulfillment",), "OPERATIONS", "DOMAIN_SPECIFIC"),
        _definition("warehouse_management", "Warehouse Management", "Planning or operating warehouse activities, inventory handling, storage or warehouse processes.", ("warehouse operations",), "OPERATIONS", "DOMAIN_SPECIFIC"),
        _definition("delivery_logistics_management", "Delivery / Logistics Management", "Planning or coordinating delivery, transportation, logistics networks or last-mile operations.", ("delivery management", "logistics management"), "OPERATIONS", "DOMAIN_SPECIFIC"),
        _definition("operations_planning", "Operations Planning", "Planning operational capacity, processes, resources and execution across recurring business activities.", ("operational planning",), "OPERATIONS", "DOMAIN_SPECIFIC"),
        _definition("digital_platform_development", "Digital Platform Development", "Designing, developing or delivering digital platforms, software systems and technical product capabilities.", ("platform development", "software development"), "DIGITAL_PLATFORM", "CORE"),
        _definition("team_leadership", "Team Leadership", "Leading, coordinating, mentoring or managing people and team delivery.", ("team management", "people management"), "LEADERSHIP", "CORE"),
        _definition("process_optimization", "Process Optimization", "Analyzing, improving or standardizing processes to increase efficiency, quality or reliability.", ("process improvement",), "OPERATIONS", "CORE"),
    ),
)


def get_taxonomy(taxonomy_id: str, version: str) -> CapabilityTaxonomy:
    if taxonomy_id != TAXONOMY_ID:
        raise ValueError("unknown_taxonomy")
    if version != TAXONOMY_VERSION:
        raise ValueError("taxonomy_version_mismatch")
    return PROFESSIONAL_CAPABILITY_CORE


def validate_taxonomy_selection(selection: TaxonomySelection, facts: ExperimentalCvFacts) -> None:
    taxonomy = get_taxonomy(selection.taxonomy_id, selection.taxonomy_version)
    known_ids = {item.id for item in taxonomy.capabilities}
    statement_ids = {
        statement.statement_id
        for experience in facts.experiences
        for statement in experience.statements
    }
    for item in selection.capabilities:
        if item.capability_id not in known_ids:
            raise ValueError(f"unknown_capability_id:{item.capability_id}")
        missing = sorted(set(item.supporting_statement_ids) - statement_ids)
        if missing:
            raise ValueError(f"unknown_statement_ref:{missing[0]}")


def merge_taxonomy_selections(selection: TaxonomySelection) -> TaxonomySelection:
    merged: dict[str, TaxonomySelectedCapability] = {}
    for item in selection.capabilities:
        current = merged.get(item.capability_id)
        if current is None:
            merged[item.capability_id] = item.model_copy(
                update={"supporting_statement_ids": list(dict.fromkeys(item.supporting_statement_ids))}
            )
        else:
            merged[item.capability_id] = current.model_copy(
                update={
                    "supporting_statement_ids": list(
                        dict.fromkeys(current.supporting_statement_ids + item.supporting_statement_ids)
                    )
                }
            )
    return selection.model_copy(update={"capabilities": list(merged.values())})


TAXONOMY_SELECTION_PROMPT_ID = "cv_capability_taxonomy_selection"


def register_taxonomy_selection(
    prompts: PromptTemplateRegistry, schemas: OutputSchemaRegistry
) -> None:
    prompts.register(
        PromptTemplate(
            template_id=TAXONOMY_SELECTION_PROMPT_ID,
            version=TAXONOMY_VERSION,
            system_instruction=(
                "Select supported capability IDs from the supplied immutable taxonomy. "
                "Use only grounded statement IDs. Return JSON only."
            ),
            user_instruction=(
                "Return taxonomy_id, taxonomy_version and selected capabilities. Select only IDs "
                "from the supplied taxonomy; do not invent IDs, names, evidence, proficiency or "
                "confidence. Schema:\n"
                + json.dumps(TaxonomySelection.model_json_schema())
                + "\nTaxonomy:\n"
                + json.dumps(PROFESSIONAL_CAPABILITY_CORE.model_dump(mode="json"))
            ),
            payload_boundary="input_data",
        )
    )
    schemas.register(TAXONOMY_SELECTION_PROMPT_ID, TAXONOMY_VERSION, TaxonomySelection)
