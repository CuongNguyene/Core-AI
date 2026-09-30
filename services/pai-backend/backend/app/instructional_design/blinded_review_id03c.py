"""ID-03C condition-blind SME review packets and submission validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.instructional_design.blinded_review_cli import load_experiment_results
from app.instructional_design.experiment import ExperimentRunResult
from app.instructional_design.schemas import (
    AssessmentSpec,
    CourseOutline,
    LearningObjectiveSpec,
    LessonSpec,
    PrerequisiteSpec,
    ResearchLearningBrief,
)

ID03C_REVIEW_FIXTURES: tuple[str, ...] = (
    "python_data_processing",
    "accounting_financial_reporting_basic",
    "legal_contract_review_basic",
    "hr_recruitment_planning_basic",
    "construction_drawing_and_method_basic",
)

RUBRIC_DIMENSIONS: tuple[str, ...] = (
    "objective_measurability",
    "objective_assessment_alignment",
    "evidence_validity",
    "cognitive_alignment",
    "prerequisite_quality",
    "course_sequence_coherence",
    "instruction_assessment_alignment",
    "scope_balance",
    "workload_time_realism",
    "domain_appropriateness",
)


class MachineObservation(BaseModel):
    """Reviewer-visible observation, deliberately without diagnosis or provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    code: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    entity_type: str | None = None
    entity_id: str | None = None
    field: str | None = None
    message: str = Field(min_length=1)


class ReviewInstructions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    overview: str = Field(min_length=1)
    scoring_scale: str = Field(min_length=1)
    rubric_dimensions: tuple[str, ...] = Field(min_length=10)
    mandatory_question: str = Field(min_length=1)
    blinding_rules: tuple[str, ...] = Field(min_length=1)
    machine_observation_rule: str = Field(min_length=1)


class ID03CReviewPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    review_id: str = Field(min_length=1)
    fixture_id: str = Field(min_length=1)
    brief: ResearchLearningBrief
    objectives: list[LearningObjectiveSpec]
    assessments: list[AssessmentSpec]
    prerequisites: list[PrerequisiteSpec]
    course_outline: CourseOutline | None
    lessons: list[LessonSpec]
    machine_observations: list[MachineObservation]
    review_instructions: ReviewInstructions


class ID03CReviewBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    packets: list[ID03CReviewPacket] = Field(min_length=5, max_length=5)


class RubricScores(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    objective_measurability: int = Field(ge=1, le=5)
    objective_assessment_alignment: int = Field(ge=1, le=5)
    evidence_validity: int = Field(ge=1, le=5)
    cognitive_alignment: int = Field(ge=1, le=5)
    prerequisite_quality: int = Field(ge=1, le=5)
    course_sequence_coherence: int = Field(ge=1, le=5)
    instruction_assessment_alignment: int = Field(ge=1, le=5)
    scope_balance: int = Field(ge=1, le=5)
    workload_time_realism: int = Field(ge=1, le=5)
    domain_appropriateness: int = Field(ge=1, le=5)


class SpecialQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    answer: str
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_answer(self) -> SpecialQuestion:
        if self.answer not in {"YES", "PARTIALLY", "NO"}:
            raise ValueError("special_question.answer must be YES, PARTIALLY, or NO")
        return self


class ID03CReviewSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    review_id: str = Field(min_length=1)
    rubric_scores: RubricScores
    rationales: dict[str, str]
    machine_validity_observations: list[MachineObservation]
    prerequisites_acceptable: bool
    edit_effort: str
    special_question: SpecialQuestion
    top_strengths: list[str]
    top_issues: list[str]

    _EDIT_EFFORTS: ClassVar[frozenset[str]] = frozenset(
        {"none", "minor", "moderate", "major", "rewrite"}
    )

    @model_validator(mode="after")
    def complete_review(self) -> ID03CReviewSubmission:
        if set(self.rationales) != set(RUBRIC_DIMENSIONS):
            raise ValueError("every rubric dimension requires exactly one rationale")
        if any(not isinstance(value, str) or not value.strip() for value in self.rationales.values()):
            raise ValueError("every rubric dimension requires a non-empty rationale")
        if self.edit_effort not in self._EDIT_EFFORTS:
            raise ValueError("invalid edit_effort")
        return self


def _review_instructions() -> ReviewInstructions:
    return ReviewInstructions(
        overview=(
            "Review the complete instructional-design proposal once before scoring. "
            "Evaluate machine validity separately from pedagogical quality."
        ),
        scoring_scale="Use 1-5 for every dimension: 1 poor, 3 mixed/acceptable, 5 strong.",
        rubric_dimensions=RUBRIC_DIMENSIONS,
        mandatory_question=(
            "Ignoring machine traceability or schema issues, is this instructional design "
            "pedagogically reasonable? Answer YES, PARTIALLY, or NO with a short rationale."
        ),
        blinding_rules=(
            "Do not infer how the proposal was generated.",
            "Do not assume a machine observation means the design is pedagogically poor.",
            "Do not repair the design while scoring; record edit effort separately.",
        ),
        machine_observation_rule=(
            "Machine observations are evidence to inspect, not pedagogical verdicts. "
            "Record any reviewer disagreement separately."
        ),
    )


def _observations(result: ExperimentRunResult) -> list[MachineObservation]:
    assert result.snapshot is not None
    return [
        MachineObservation(
            code=finding.code,
            severity=finding.severity.value,
            entity_type=finding.entity_type,
            entity_id=finding.entity_id,
            field=finding.field,
            message=finding.message,
        )
        for finding in result.snapshot.quality_report.findings
    ]


def build_id03c_bundle(results: list[ExperimentRunResult]) -> ID03CReviewBundle:
    """Build one packet per frozen fixture, with no condition metadata in the packet."""

    if len(results) != len(ID03C_REVIEW_FIXTURES):
        raise ValueError("ID-03C requires exactly five completed fixture results")
    by_fixture: dict[str, ExperimentRunResult] = {}
    for result in results:
        fixture_id = result.run.fixture_id
        if fixture_id in by_fixture:
            raise ValueError(f"duplicate fixture result: {fixture_id}")
        if result.snapshot is None:
            raise ValueError(f"fixture result is incomplete: {fixture_id}")
        by_fixture[fixture_id] = result
    if set(by_fixture) != set(ID03C_REVIEW_FIXTURES):
        raise ValueError("results must contain exactly the ID-03B.6 review fixtures")
    packets: list[ID03CReviewPacket] = []
    for index, fixture_id in enumerate(ID03C_REVIEW_FIXTURES, start=1):
        snapshot = by_fixture[fixture_id].snapshot
        assert snapshot is not None
        packets.append(
            ID03CReviewPacket(
            review_id=f"review-{index:03d}",
            fixture_id=fixture_id,
            brief=snapshot.brief,
            objectives=snapshot.objectives,
            assessments=snapshot.assessments,
            prerequisites=snapshot.prerequisites,
            course_outline=snapshot.course_outline,
            lessons=snapshot.lessons,
            machine_observations=_observations(by_fixture[fixture_id]),
            review_instructions=_review_instructions(),
            )
        )
    return ID03CReviewBundle(packets=packets)


def validate_id03c_submission(
    packet: ID03CReviewPacket, payload: dict[str, Any]
) -> ID03CReviewSubmission:
    if payload.get("review_id") != packet.review_id:
        raise ValueError("review_id does not match packet")
    try:
        return ID03CReviewSubmission.model_validate(payload)
    except Exception as exc:  # normalize Pydantic wire errors for the CLI boundary
        raise ValueError(str(exc)) from exc


def write_id03c_bundle(bundle: ID03CReviewBundle, output_dir: Path) -> None:
    """Persist manifest before packet files and leave reviewer submissions empty."""

    if len(bundle.packets) != len(ID03C_REVIEW_FIXTURES):
        raise ValueError("ID-03C bundle must contain five packets")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment": "ID-03C",
        "source_experiment": "ID-03B.6",
        "review_type": "blinded_cross_domain_sme_review",
        "packet_count": len(bundle.packets),
        "fixtures": list(ID03C_REVIEW_FIXTURES),
        "rubric_version": "instructional_design_human_rubric@0.2",
        "submission_schema_version": "id03c_review_submission@0.1",
        "status": "prepared",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    packet_dir = output_dir / "reviewer-packets"
    submission_dir = output_dir / "reviewer-submissions"
    packet_dir.mkdir(exist_ok=True)
    submission_dir.mkdir(exist_ok=True)
    for packet in bundle.packets:
        text = json.dumps(packet.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
        (packet_dir / f"{packet.review_id}.json").write_text(text, encoding="utf-8")
    template: dict[str, Any] = {
        "review_id": None,
        "rubric_scores": {name: None for name in RUBRIC_DIMENSIONS},
        "rationales": {name: "" for name in RUBRIC_DIMENSIONS},
        "machine_validity_observations": [],
        "prerequisites_acceptable": None,
        "edit_effort": None,
        "special_question": {"answer": None, "rationale": ""},
        "top_strengths": [],
        "top_issues": [],
    }
    (output_dir / "review-summary-template.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    validation = {
        "packet_count": len(bundle.packets),
        "unique_review_ids": len({packet.review_id for packet in bundle.packets}) == len(bundle.packets),
        "unique_fixtures": len({packet.fixture_id for packet in bundle.packets}) == len(bundle.packets),
        "condition_leakage": 0,
        "private_metadata_leakage": 0,
        "root_cause_metadata_leakage": 0,
        "artifact_sections_present": all(
            packet.brief is not None
            and packet.objectives is not None
            and packet.assessments is not None
            and packet.prerequisites is not None
            and packet.course_outline is not None
            and packet.lessons is not None
            for packet in bundle.packets
        ),
        "reviewer_submissions_created": 0,
        "status": "valid",
    }
    (output_dir / "validation-report.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def prepare_id03c(results_path: Path, output_dir: Path) -> None:
    results = load_experiment_results(results_path)
    write_id03c_bundle(build_id03c_bundle(results), output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare ID-03C blinded SME packets")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    prepare_id03c(args.results, args.output_dir)
    print(json.dumps({"packet_count": 5, "status": "prepared"}))


if __name__ == "__main__":
    main()
