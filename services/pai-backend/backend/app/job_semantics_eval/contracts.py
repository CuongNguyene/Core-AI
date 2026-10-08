"""Strict, non-production contracts for JD requirement breakdown evaluation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StatementType = Literal[
    "RESPONSIBILITY",
    "EXPERIENCE_REQUIREMENT",
    "EDUCATION_REQUIREMENT",
    "QUALIFICATION_REQUIREMENT",
    "BEHAVIORAL_REQUIREMENT",
    "OTHER",
]
CapabilityRelevance = Literal["CAPABILITY_BEARING", "NON_CAPABILITY", "UNCLEAR"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProviderSourceBlock(_StrictModel):
    block_id: str = Field(min_length=1, max_length=128)
    source_field: Literal["JOB_DESCRIPTION", "JOB_REQUIREMENTS"]
    text: str = Field(min_length=1, max_length=8000)


class ProviderInputV1(_StrictModel):
    source_blocks: tuple[ProviderSourceBlock, ...] = Field(max_length=200)


class PredictedJobRequirementStatement(_StrictModel):
    source_block_ids: list[str] = Field(min_length=1, max_length=8)
    source_text: str = Field(min_length=1, max_length=4000)
    normalized_statement: str = Field(min_length=1, max_length=4000)
    statement_type: StatementType
    capability_relevance: CapabilityRelevance
    capability_signal_text: str | None = Field(default=None, max_length=1000)


class JobRequirementExtractionOutputV1(_StrictModel):
    statements: list[PredictedJobRequirementStatement] = Field(max_length=200)


class ValidatedRequirementStatement(_StrictModel):
    source_block_ids: tuple[str, ...]
    source_field: Literal["JOB_DESCRIPTION", "JOB_REQUIREMENTS"]
    block_order: int = Field(gt=0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    source_text: str = Field(min_length=1)
    normalized_statement: str = Field(min_length=1)
    statement_type: StatementType
    capability_relevance: CapabilityRelevance
    capability_signal_text: str | None = None
    output_index: int = Field(ge=0)
