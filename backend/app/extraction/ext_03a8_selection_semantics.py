"""Evaluation-only strict selection semantics for EXT-03A.8."""

import json
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.extraction.capability_taxonomy import (
    TAXONOMY_ID,
    TAXONOMY_VERSION,
    TaxonomySelection,
    get_taxonomy,
)
from app.model_gateway.prompts import PromptTemplate, PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


class CapabilitySelectionCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    capability_id: str = Field(min_length=1)
    positive_signals: tuple[str, ...] = Field(min_length=1)
    negative_signals: tuple[str, ...] = Field(min_length=1)


class CriteriaSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    criteria_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    taxonomy_id: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    criteria: tuple[CapabilitySelectionCriteria, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_taxonomy_binding(self) -> "CriteriaSet":
        taxonomy = get_taxonomy(self.taxonomy_id, self.taxonomy_version)
        known = {item.id for item in taxonomy.capabilities}
        for item in self.criteria:
            if item.capability_id not in known:
                raise ValueError(f"unknown_criteria_capability:{item.capability_id}")
        ids = [item.capability_id for item in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_criteria_capability")
        return self


STRICT_CRITERIA = CriteriaSet(
    criteria_id="strict-demonstrated-evidence",
    version="0.1",
    taxonomy_id=TAXONOMY_ID,
    taxonomy_version=TAXONOMY_VERSION,
    criteria=tuple(
        CapabilitySelectionCriteria(
            capability_id=item.id,
            positive_signals=("planned", "designed", "built", "implemented", "owned", "led", "managed", "optimized", "delivered", "analyzed", "coordinated", "operated", "executed"),
            negative_signals=("title only", "used tool only", "participated only", "generic exposure"),
        )
        for item in get_taxonomy(TAXONOMY_ID, TAXONOMY_VERSION).capabilities
    ),
)


def strict_evidence_decision(statement: str, capability_name: str) -> bool:
    """Small deterministic fixture helper, not a replacement for model review."""
    text = re.sub(r"\s+", " ", statement.casefold()).strip()
    if text in {"sales manager", "project manager"}:
        return False
    if text.startswith("used ") or "used shopify" in text:
        return False
    if "sold product" in text and capability_name.casefold() == "product management":
        return False
    action_words = ("planned", "designed", "built", "implemented", "owned", "led", "managed", "optimized", "delivered", "analyzed", "coordinated", "operated", "executed")
    return any(word in text for word in action_words)


def calculate_selection_scores(
    selected_ids: list[str], supported_selected_ids: list[str], expected_supported_ids: list[str], demonstrated_count: int, represented_count: int
) -> dict[str, float | int]:
    selected = len(selected_ids)
    supported = len(supported_selected_ids)
    expected = len(expected_supported_ids)
    precision = supported / selected if selected else 0.0
    recall = len(set(supported_selected_ids) & set(expected_supported_ids)) / expected if expected else 0.0
    return {
        "selected": selected,
        "supported": supported,
        "unsupported": selected - supported,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "taxonomy_coverage": represented_count / demonstrated_count if demonstrated_count else 0.0,
    }


STRICT_PROMPT_ID = "cv_capability_selection_strict"
CRITERIA_PROMPT_ID = "cv_capability_selection_criteria"


def register_selection_semantics(
    prompts: PromptTemplateRegistry, schemas: OutputSchemaRegistry
) -> None:
    taxonomy = get_taxonomy(TAXONOMY_ID, TAXONOMY_VERSION)
    base = (
        "The taxonomy is a list of possible capabilities, not a checklist. Select zero or more. "
        "Select only when a supplied factual statement directly demonstrates professional action, "
        "responsibility, ownership, delivery or outcome matching the definition. Title-only, tool-only, "
        "keyword-only, generic management and domain association are insufficient. Use only statement IDs."
    )
    prompts.register(PromptTemplate(
        template_id=STRICT_PROMPT_ID, version="1.0",
        system_instruction="Apply strict demonstrated-evidence semantics to factual CV JSON. Return JSON only.",
        user_instruction=base + " Return taxonomy_id, taxonomy_version and selected IDs. Taxonomy:\n" + json.dumps(taxonomy.model_dump(mode="json")) + "\nSchema:\n" + json.dumps(TaxonomySelection.model_json_schema()),
        payload_boundary="input_data",
    ))
    schemas.register(STRICT_PROMPT_ID, "1.0", TaxonomySelection)
    prompts.register(PromptTemplate(
        template_id=CRITERIA_PROMPT_ID, version="1.0",
        system_instruction="Apply strict evidence semantics plus explicit positive and negative criteria. Return JSON only.",
        user_instruction=base + " Positive examples: project management requires accountable project planning/delivery; product management requires roadmap, feature or product lifecycle ownership; team leadership requires leading or managing team delivery; process optimization requires redesign or measurable improvement; digital platform development requires building or implementing a platform. Negative examples: selling a product, using Shopify/SAP, merely participating, or a role title alone do not qualify. Return only selected IDs. Taxonomy:\n" + json.dumps(taxonomy.model_dump(mode="json")) + "\nSchema:\n" + json.dumps(TaxonomySelection.model_json_schema()),
        payload_boundary="input_data",
    ))
    schemas.register(CRITERIA_PROMPT_ID, "1.0", TaxonomySelection)
