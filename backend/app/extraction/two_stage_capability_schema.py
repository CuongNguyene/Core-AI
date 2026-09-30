"""Contracts for the bounded EXT-03A.4 two-stage CV experiment.

These schemas are evaluation-only.  Stage 1 records factual, document-grounded
statements; Stage 2 can only refer to those statements and cannot receive the PDF.
"""

import json
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.model_gateway.prompts import PromptTemplate, PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry

FACT_EXTRACTION_EXPERIMENT_PROMPT_ID = "cv_fact_extraction_experiment"
CAPABILITY_DERIVATION_EXPERIMENT_PROMPT_ID = "cv_capability_derivation_experiment"
FACT_EXTRACTION_EXPERIMENT_VERSION = "1"
CAPABILITY_DERIVATION_EXPERIMENT_VERSION = "1"


class ExperimentalStatement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    statement_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)


class ExperimentalExperienceFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    experience_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    organization: str | None = Field(default=None, min_length=1)
    period: str | None = Field(default=None, min_length=1)
    statements: list[ExperimentalStatement] = Field(default_factory=list)


class ExperimentalEducationFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    degree: str = Field(min_length=1)
    field: str | None = Field(default=None, min_length=1)
    institution: str | None = Field(default=None, min_length=1)
    year: int | None = Field(default=None, ge=0)
    document_id: str | None = Field(default=None, min_length=1)
    page_number: int | None = Field(default=None, ge=1)


class ExperimentalToolFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    supporting_statement_ids: list[str] = Field(min_length=1)


class ExperimentalCvFacts(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_id: str = Field(min_length=1)
    experiences: list[ExperimentalExperienceFact] = Field(default_factory=list)
    education: list[ExperimentalEducationFact] = Field(default_factory=list)
    tools_platforms: list[ExperimentalToolFact] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "ExperimentalCvFacts":
        experience_ids = [item.experience_id for item in self.experiences]
        if len(experience_ids) != len(set(experience_ids)):
            raise ValueError("duplicate_experience_id")
        statement_ids = [
            statement.statement_id
            for experience in self.experiences
            for statement in experience.statements
        ]
        if len(statement_ids) != len(set(statement_ids)):
            raise ValueError("duplicate_statement_id")
        return self


class ExperimentalCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    supporting_statement_ids: list[str] = Field(min_length=1)


class ExperimentalCapabilityDerivation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    capabilities: list[ExperimentalCapability] = Field(default_factory=list)


_BOUNDED_ALIASES = {
    "omni-channel": "Omnichannel Commerce",
    "omnichannel": "Omnichannel Commerce",
    "omni channel": "Omnichannel Commerce",
}


def normalize_capabilities(
    output: ExperimentalCapabilityDerivation,
) -> list[ExperimentalCapability]:
    """Normalize only known aliases and merge exact normalized names."""
    merged: dict[str, ExperimentalCapability] = {}
    for capability in output.capabilities:
        key = re.sub(r"\s+", " ", capability.name.strip().casefold())
        name = _BOUNDED_ALIASES.get(key, capability.name.strip())
        identity = name.casefold()
        existing = merged.get(identity)
        if existing is None:
            merged[identity] = capability.model_copy(
                update={"name": name, "supporting_statement_ids": list(dict.fromkeys(capability.supporting_statement_ids))}
            )
        else:
            merged[identity] = existing.model_copy(
                update={
                    "supporting_statement_ids": list(
                        dict.fromkeys(existing.supporting_statement_ids + capability.supporting_statement_ids)
                    )
                }
            )
    return list(merged.values())


def _statements(facts: ExperimentalCvFacts) -> dict[str, ExperimentalStatement]:
    return {
        item.statement_id: item
        for experience in facts.experiences
        for item in experience.statements
    }


def validate_facts_references(
    facts: ExperimentalCvFacts, *, expected_document_id: str, page_count: int
) -> None:
    if facts.document_id != expected_document_id:
        raise ValueError("document_id_mismatch")
    known = _statements(facts)
    for item in known.values():
        if item.document_id != expected_document_id:
            raise ValueError("document_id_mismatch")
        if item.page_number > page_count:
            raise ValueError("page_out_of_range")
    for education in facts.education:
        if education.document_id is not None and education.document_id != expected_document_id:
            raise ValueError("document_id_mismatch")
        if education.page_number is not None and education.page_number > page_count:
            raise ValueError("page_out_of_range")
    for tool in facts.tools_platforms:
        missing = sorted(set(tool.supporting_statement_ids) - known.keys())
        if missing:
            raise ValueError(f"unknown_statement_ref:{missing[0]}")


def validate_capability_references(
    output: ExperimentalCapabilityDerivation, facts: ExperimentalCvFacts
) -> None:
    known = _statements(facts)
    for capability in output.capabilities:
        missing = sorted(set(capability.supporting_statement_ids) - known.keys())
        if missing:
            raise ValueError(f"unknown_statement_ref:{missing[0]}")


def register_two_stage_experiment(
    prompts: PromptTemplateRegistry, schemas: OutputSchemaRegistry
) -> None:
    prompts.register(
        PromptTemplate(
            template_id=FACT_EXTRACTION_EXPERIMENT_PROMPT_ID,
            version=FACT_EXTRACTION_EXPERIMENT_VERSION,
            system_instruction=(
                "Extract only factual CV information grounded in the supplied native PDF. "
                "Do not infer capabilities, proficiency, confidence, taxonomy, or evidence strength. "
                "Return JSON only."
            ),
            user_instruction=(
                "Return exhaustive experiences, factual statements, education, and tools. "
                "Every statement needs a unique statement_id, exact factual text, document_id, "
                "and native PDF page_number. Do not include capabilities. Schema:\n"
                + json.dumps(ExperimentalCvFacts.model_json_schema())
            ),
            payload_boundary="input_data",
        )
    )
    schemas.register(
        FACT_EXTRACTION_EXPERIMENT_PROMPT_ID,
        FACT_EXTRACTION_EXPERIMENT_VERSION,
        ExperimentalCvFacts,
    )
    prompts.register(
        PromptTemplate(
            template_id=CAPABILITY_DERIVATION_EXPERIMENT_PROMPT_ID,
            version=CAPABILITY_DERIVATION_EXPERIMENT_VERSION,
            system_instruction=(
                "Derive capability names only from the supplied factual CV JSON. "
                "Return JSON only; never invent evidence or references."
            ),
            user_instruction=(
                "Return capabilities with one or more supporting_statement_ids. "
                "Use only statement IDs present in the input. Do not return raw excerpts, "
                "pages, document IDs, confidence, proficiency, or evidence strength. Schema:\n"
                + json.dumps(ExperimentalCapabilityDerivation.model_json_schema())
            ),
            payload_boundary="input_data",
        )
    )
    schemas.register(
        CAPABILITY_DERIVATION_EXPERIMENT_PROMPT_ID,
        CAPABILITY_DERIVATION_EXPERIMENT_VERSION,
        ExperimentalCapabilityDerivation,
    )
