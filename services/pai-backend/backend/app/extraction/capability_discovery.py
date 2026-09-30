"""Grounded free-form capability discovery and deterministic taxonomy mapping."""

import json
import re

from pydantic import BaseModel, ConfigDict, Field

from app.extraction.capability_taxonomy import get_taxonomy
from app.extraction.schemas import CapabilityMappingStatus
from app.extraction.two_stage_capability_schema import ExperimentalCvFacts
from app.model_gateway.prompts import PromptTemplate, PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry

DISCOVERY_PROMPT_ID = "cv_capability_discovery"
DISCOVERY_PROMPT_VERSION = "1.0"


class CapabilityDiscoveryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    raw_name: str = Field(min_length=1)
    supporting_statement_ids: list[str] = Field(min_length=1)


class CapabilityDiscoveryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    capabilities: list[CapabilityDiscoveryCandidate] = Field(default_factory=list)


class CanonicalizedCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    raw_name: str = Field(min_length=1)
    status: CapabilityMappingStatus
    canonical_capability_id: str | None = None
    canonical_name: str | None = None
    supporting_statement_ids: list[str] = Field(min_length=1)


def _known_statement_ids(facts: ExperimentalCvFacts) -> set[str]:
    return {
        statement.statement_id
        for experience in facts.experiences
        for statement in experience.statements
    }


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def _is_rejected(candidate: CapabilityDiscoveryCandidate, facts: ExperimentalCvFacts) -> bool:
    role_names = {_normalize(item.role) for item in facts.experiences}
    tool_names = {_normalize(item.name) for item in facts.tools_platforms}
    return _normalize(candidate.raw_name) in role_names | tool_names


def canonicalize_capabilities(
    output: CapabilityDiscoveryOutput, facts: ExperimentalCvFacts
) -> list[CanonicalizedCapability]:
    known_statements = _known_statement_ids(facts)
    taxonomy = get_taxonomy("professional_capability_core", "0.1")
    by_name = {_normalize(item.name): item for item in taxonomy.capabilities}
    aliases = {
        _normalize(alias): item
        for item in taxonomy.capabilities
        for alias in item.aliases
    }
    merged: dict[str, CanonicalizedCapability] = {}
    for candidate in output.capabilities:
        missing = sorted(set(candidate.supporting_statement_ids) - known_statements)
        if missing:
            raise ValueError(f"unknown_statement_ref:{missing[0]}")
        name = re.sub(r"\s+", " ", candidate.raw_name.strip())
        key = _normalize(name)
        existing = merged.get(key)
        if existing is not None:
            merged[key] = existing.model_copy(
                update={
                    "supporting_statement_ids": list(
                        dict.fromkeys(existing.supporting_statement_ids + candidate.supporting_statement_ids)
                    )
                }
            )
            continue
        if _is_rejected(candidate, facts):
            status = CapabilityMappingStatus.REJECTED_UNSUPPORTED
            canonical_id = canonical_name = None
        else:
            definition = by_name.get(key) or aliases.get(key)
            status = (
                CapabilityMappingStatus.MAPPED
                if definition is not None
                else CapabilityMappingStatus.UNMAPPED_BUT_GROUNDED
            )
            canonical_id = definition.id if definition is not None else None
            canonical_name = definition.name if definition is not None else name
        merged[key] = CanonicalizedCapability(
            raw_name=name,
            status=status,
            canonical_capability_id=canonical_id,
            canonical_name=canonical_name,
            supporting_statement_ids=list(dict.fromkeys(candidate.supporting_statement_ids)),
        )
    return [item for item in merged.values() if item.status is not CapabilityMappingStatus.REJECTED_UNSUPPORTED]


def register_capability_discovery(
    prompts: PromptTemplateRegistry, schemas: OutputSchemaRegistry
) -> None:
    taxonomy = get_taxonomy("professional_capability_core", "0.1")
    prompts.register(
        PromptTemplate(
            template_id=DISCOVERY_PROMPT_ID,
            version=DISCOVERY_PROMPT_VERSION,
            system_instruction=(
                "Discover reusable professional capability families from factual CV statements. "
                "Use only grounded statement IDs and return JSON only."
            ),
            user_instruction=(
                "Return capabilities with raw_name and one or more supporting_statement_ids. "
                "Discover capabilities beyond the supplied taxonomy when directly evidenced, "
                "but never infer proficiency, confidence, evidence, or canonical IDs. Do not "
                "turn tools, titles, or generic domain association into capabilities. Schema:\n"
                + json.dumps(CapabilityDiscoveryOutput.model_json_schema())
                + "\nCanonical taxonomy is only a mapping reference:\n"
                + json.dumps(taxonomy.model_dump(mode="json"))
            ),
            payload_boundary="input_data",
        )
    )
    schemas.register(DISCOVERY_PROMPT_ID, DISCOVERY_PROMPT_VERSION, CapabilityDiscoveryOutput)
