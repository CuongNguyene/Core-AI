"""Fail-closed, explicitly approved reuse contract for Stage-1 evaluation facts."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.extraction.two_stage_capability_schema import (
    ExperimentalCvFacts,
    validate_facts_references,
)


class ReusableStage1FactsArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fixture_id: str = Field(min_length=1)
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fact_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    privacy_status: Literal["SANITIZED_APPROVED"]
    facts: ExperimentalCvFacts

    @model_validator(mode="after")
    def validate_fact_identity(self) -> "ReusableStage1FactsArtifact":
        if self.fact_identity != fact_identity(self.facts):
            raise ValueError("stage1_fact_identity_mismatch")
        return self


def fact_identity(facts: ExperimentalCvFacts) -> str:
    payload = json.dumps(facts.model_dump(mode="json"), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def build_reusable_stage1_artifact(
    *,
    fixture_id: str,
    fixture_sha256: str,
    facts: ExperimentalCvFacts,
    privacy_approved: bool,
) -> ReusableStage1FactsArtifact:
    if not privacy_approved:
        raise ValueError("stage1_artifact_persistence_not_approved")
    return ReusableStage1FactsArtifact(
        fixture_id=fixture_id,
        fixture_sha256=fixture_sha256,
        fact_identity=fact_identity(facts),
        privacy_status="SANITIZED_APPROVED",
        facts=facts,
    )


def load_reusable_stage1_facts(
    artifact: ReusableStage1FactsArtifact,
    *,
    fixture_id: str,
    fixture_sha256: str,
    page_count: int,
) -> ExperimentalCvFacts:
    if artifact.privacy_status != "SANITIZED_APPROVED":
        raise ValueError("stage1_artifact_persistence_not_approved")
    if (artifact.fixture_id, artifact.fixture_sha256) != (
        fixture_id,
        fixture_sha256,
    ):
        raise ValueError("stage1_fixture_checksum_mismatch")
    if artifact.fact_identity != fact_identity(artifact.facts):
        raise ValueError("stage1_fact_identity_mismatch")
    validate_facts_references(
        artifact.facts,
        expected_document_id=artifact.facts.document_id,
        page_count=page_count,
    )
    return artifact.facts
