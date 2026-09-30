import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from app.capability_analysis.semantic_core.contracts import (
    EvidenceExpectation,
    EvidenceSemantics,
    EvidenceSourceKind,
    RequirementSemantics,
    SemanticConstraint,
    SemanticConstraintDimension,
    SemanticConstraintOperator,
    SemanticContext,
    SemanticSourceLocator,
)
from app.capability_analysis.semantic_core.retrieval import (
    SemanticAssessmentStatus,
    assess_retrieval,
    normalize_identity_phrase,
    retrieve_candidates,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "semantic_expectations"
FIXTURE_NAMES = ("ai_engineer", "sales_executive", "accountant", "hr_recruiter")


@dataclass(frozen=True, slots=True)
class FixtureSemanticHints:
    """Exact fixture-declared phrase mappings; deliberately not a production pack."""

    phrases: dict[str, str]

    @classmethod
    def from_fixture(cls, fixture: dict[str, Any]) -> "FixtureSemanticHints":
        return cls(
            phrases={
                normalize_identity_phrase(source): target
                for source, target in fixture["hints"].items()
            }
        )

    def concept_for(self, phrase: str) -> str:
        return self.phrases[normalize_identity_phrase(phrase)]


@dataclass(frozen=True, slots=True)
class FixtureMetrics:
    expected_positive_pairs: int
    retrieved_positive_pairs: int
    retrieved_negative_pairs: int

    @property
    def positive_recall(self) -> float:
        return self.retrieved_positive_pairs / self.expected_positive_pairs

    @property
    def retrieval_precision(self) -> float:
        retrieved = self.retrieved_positive_pairs + self.retrieved_negative_pairs
        return self.retrieved_positive_pairs / retrieved


def _load_fixture(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8")),
    )


def _requirement(
    raw: dict[str, Any],
    hints: FixtureSemanticHints,
) -> RequirementSemantics:
    constraints = tuple(
        SemanticConstraint(
            dimension=SemanticConstraintDimension(item["dimension"]),
            operator=SemanticConstraintOperator(item.get("operator", "one_of")),
            values=tuple(item["values"]),
            source_field=f"fixture:{raw['id']}",
            source_reference=raw["id"],
        )
        for item in raw.get("constraints", [])
    )
    return RequirementSemantics(
        requirement_id=raw["id"],
        concepts=(hints.concept_for(raw["phrase"]),),
        behaviors=(),
        objects=(),
        constraints=constraints,
        evidence_expectation=EvidenceExpectation(raw["expectation"]),
        source_requirement_ref=raw["id"],
        source_locator=None,
        provenance=(("fixture_phrase", raw["phrase"]),),
        unresolved_fields=(),
    )


def _evidence(
    raw: dict[str, Any],
    hints: FixtureSemanticHints,
    offset: int,
) -> EvidenceSemantics:
    return EvidenceSemantics(
        evidence_ref=raw["ref"],
        concepts=(hints.concept_for(raw["phrase"]),),
        behaviors=(),
        objects=(),
        context=SemanticContext(raw["context"]),
        participation=raw.get("participation"),
        source_kind=EvidenceSourceKind(raw["source_kind"]),
        confidence=raw["confidence"],
        original_evidence_type="fixture_observation",
        source_locator=SemanticSourceLocator(
            document_id=f"fixture-{raw['ref']}",
            section="labelled_observation",
            start_offset=offset,
            end_offset=offset + len(raw["phrase"]),
        ),
        source_value=raw["phrase"],
        source_excerpt="deterministic source-backed fixture observation",
        provenance=(("fixture_evidence_ref", raw["ref"]),),
        unresolved_fields=(),
    )


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_cross_domain_labelled_semantic_expectations(fixture_name: str) -> None:
    fixture = _load_fixture(fixture_name)
    hints = FixtureSemanticHints.from_fixture(fixture)
    evidence = tuple(
        _evidence(raw, hints, index * 100)
        for index, raw in enumerate(fixture["evidence"], start=1)
    )
    all_evidence_refs = {item.evidence_ref for item in evidence}
    expected_positive_pairs = 0
    retrieved_positive_pairs = 0
    retrieved_negative_pairs = 0

    assert 5 <= len(fixture["requirements"]) <= 8
    for raw_requirement in fixture["requirements"]:
        requirement = _requirement(raw_requirement, hints)
        candidates = retrieve_candidates(requirement, evidence)
        projection = assess_retrieval(requirement, candidates, confidence_threshold=0.8)
        actual_refs = {item.evidence.evidence_ref for item in candidates}
        expected_refs = set(raw_requirement["expected_refs"])

        assert actual_refs == expected_refs, raw_requirement["id"]
        assert projection.retrieved_candidate_count == len(expected_refs)
        assert projection.eligible_candidate_count == raw_requirement["eligible"]
        assert projection.status is SemanticAssessmentStatus(raw_requirement["status"])
        assert set(projection.strongest_evidence_refs) == set(
            raw_requirement["strongest_refs"]
        )

        expected_positive_pairs += len(expected_refs)
        retrieved_positive_pairs += len(actual_refs & expected_refs)
        retrieved_negative_pairs += len(actual_refs & (all_evidence_refs - expected_refs))

    metrics = FixtureMetrics(
        expected_positive_pairs=expected_positive_pairs,
        retrieved_positive_pairs=retrieved_positive_pairs,
        retrieved_negative_pairs=retrieved_negative_pairs,
    )
    assert metrics.positive_recall == 1.0
    assert metrics.retrieval_precision == 1.0


def test_fixture_hints_are_exact_and_semantic_core_has_no_fixture_vocabulary() -> None:
    fixture = _load_fixture("ai_engineer")
    hints = FixtureSemanticHints.from_fixture(fixture)

    with pytest.raises(KeyError):
        hints.concept_for("Python engineering")

    core_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            Path(__file__).parents[1] / "app" / "capability_analysis" / "semantic_core"
        ).glob("*.py")
    ).casefold()
    for forbidden in (
        "ai_engineer",
        "sales_executive",
        "accountant",
        "hr_recruiter",
        "python",
        "mlops",
        "crm",
        "ifrs",
    ):
        assert forbidden not in core_source
