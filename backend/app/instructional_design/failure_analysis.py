"""Researcher-authored root-cause annotations for immutable experiment findings."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FindingRootCause(StrEnum):
    PROMPT_CONTRACT = "prompt_contract"
    ID_REFERENCE_DRIFT = "id_reference_drift"
    OVER_GENERATION = "over_generation"
    UNDER_GENERATION = "under_generation"
    ASSESSMENT_SCOPE_CREEP = "assessment_scope_creep"
    PREREQUISITE_OVER_PROPOSAL = "prerequisite_over_proposal"
    SEQUENCING_ERROR = "sequencing_error"
    VALIDATOR_FALSE_POSITIVE = "validator_false_positive"
    OTHER = "other"


class RootCauseAnnotation(BaseModel):
    """A human research hypothesis; it cannot rewrite the source experiment result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    annotation_source: Literal["researcher"] = "researcher"
    run_id: str = Field(min_length=1)
    finding_index: int = Field(ge=0)
    finding_code: str = Field(min_length=1)
    entity_type: str | None = None
    entity_id: str | None = None
    field: str | None = None
    root_cause: FindingRootCause
    producer_stage: str = Field(min_length=1)
    validator_correct: bool
    rationale: str = Field(min_length=1)


class FailureAnalysisReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: str = Field(min_length=1)
    source_results_artifact: str = Field(min_length=1)
    annotations: list[RootCauseAnnotation] = Field(min_length=1)


def validate_annotations_against_results(
    report: FailureAnalysisReport, source_results: Mapping[str, object]
) -> None:
    """Fail closed unless every annotation matches a persisted quality-gate finding exactly."""

    result_items = source_results.get("results")
    if not isinstance(result_items, list):
        raise ValueError("source results must contain a results list")

    finding_keys: set[tuple[str, int, str, str | None, str | None, str | None]] = set()
    for result in result_items:
        if not isinstance(result, dict):
            continue
        run = result.get("run")
        snapshot = result.get("snapshot")
        if not isinstance(run, dict) or not isinstance(snapshot, dict):
            continue
        run_id = run.get("run_id")
        quality_report = snapshot.get("quality_report")
        if not isinstance(run_id, str) or not isinstance(quality_report, dict):
            continue
        findings = quality_report.get("findings")
        if not isinstance(findings, list):
            continue
        for finding_index, finding in enumerate(findings):
            if not isinstance(finding, dict) or not isinstance(finding.get("code"), str):
                continue
            finding_keys.add(
                (
                    run_id,
                    finding_index,
                    finding["code"],
                    finding.get("entity_type") if isinstance(finding.get("entity_type"), str) else None,
                    finding.get("entity_id") if isinstance(finding.get("entity_id"), str) else None,
                    finding.get("field") if isinstance(finding.get("field"), str) else None,
                )
            )

    for annotation in report.annotations:
        key = (
            annotation.run_id,
            annotation.finding_index,
            annotation.finding_code,
            annotation.entity_type,
            annotation.entity_id,
            annotation.field,
        )
        if key not in finding_keys:
            raise ValueError("annotation does not match a source finding")
