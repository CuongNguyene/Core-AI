import pytest

from app.capability_analysis.semantic_core.compatibility import (
    EvidenceDirectness,
    evaluate_compatibilities,
    evaluate_evidence_compatibility,
)
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


def _constraint(
    dimension: SemanticConstraintDimension,
    *values: str,
    operator: SemanticConstraintOperator = SemanticConstraintOperator.ONE_OF,
) -> SemanticConstraint:
    return SemanticConstraint(
        dimension=dimension,
        operator=operator,
        values=values,
        source_field="fixture_requirement",
    )


def _requirement(
    *,
    expectation: EvidenceExpectation = EvidenceExpectation.UNKNOWN,
    constraints: tuple[SemanticConstraint, ...] = (),
) -> RequirementSemantics:
    return RequirementSemantics(
        requirement_id="requirement-1",
        concepts=("concept-a",),
        behaviors=(),
        objects=(),
        constraints=constraints,
        evidence_expectation=expectation,
        source_requirement_ref="source-requirement-1",
        source_locator=None,
        provenance=(),
        unresolved_fields=(),
    )


def _evidence(
    *,
    evidence_ref: str = "evidence-1",
    context: SemanticContext = SemanticContext.MENTIONED,
    participation: str | None = None,
    source_kind: EvidenceSourceKind = EvidenceSourceKind.SKILL,
    confidence: float = 0.9,
    concepts: tuple[str, ...] = ("concept-a",),
) -> EvidenceSemantics:
    return EvidenceSemantics(
        evidence_ref=evidence_ref,
        concepts=concepts,
        behaviors=(),
        objects=(),
        context=context,
        participation=participation,
        source_kind=source_kind,
        confidence=confidence,
        original_evidence_type="fixture_evidence",
        source_locator=SemanticSourceLocator(
            document_id="accepted-cv",
            section="fixture",
            start_offset=10,
            end_offset=20,
        ),
        source_value="source value",
        source_excerpt="source-backed fixture observation",
        provenance=(("source", "fixture"),),
        unresolved_fields=(),
    )


def test_participated_or_assisted_does_not_satisfy_owned_or_led_constraint() -> None:
    requirement = _requirement(
        constraints=(
            _constraint(SemanticConstraintDimension.PARTICIPATION, "owned", "led"),
        )
    )

    participated = evaluate_evidence_compatibility(
        requirement, _evidence(participation="participated")
    )
    assisted = evaluate_evidence_compatibility(requirement, _evidence(participation="assisted"))
    owned = evaluate_evidence_compatibility(requirement, _evidence(participation="owned"))

    assert participated.eligible is False
    assert participated.directness is EvidenceDirectness.INCOMPATIBLE
    assert participated.reason_codes == ("participation_mismatch",)
    assert assisted.eligible is False
    assert assisted.reason_codes == ("participation_mismatch",)
    assert owned.eligible is True
    assert owned.directness is EvidenceDirectness.DIRECT
    assert owned.rank > participated.rank


def test_adjacent_context_is_retained_but_ineligible_for_required_context() -> None:
    requirement = _requirement(
        constraints=(
            _constraint(
                SemanticConstraintDimension.CONTEXT,
                SemanticContext.USED_IN_PRODUCTION.value,
                operator=SemanticConstraintOperator.EQUALS,
            ),
        )
    )

    result = evaluate_evidence_compatibility(
        requirement,
        _evidence(context=SemanticContext.USED_IN_PROJECT),
    )

    assert result.evidence_ref == "evidence-1"
    assert result.eligible is False
    assert result.directness is EvidenceDirectness.INCOMPATIBLE
    assert result.reason_codes == ("context_mismatch",)


def test_retrieved_candidates_remain_visible_when_all_are_ineligible() -> None:
    requirement = _requirement(
        constraints=(
            _constraint(SemanticConstraintDimension.PARTICIPATION, "owned", "led"),
        )
    )
    evidence = (
        _evidence(evidence_ref="participated", participation="participated"),
        _evidence(evidence_ref="assisted", participation="assisted"),
    )

    results = evaluate_compatibilities(requirement, evidence)

    assert [result.evidence_ref for result in results] == ["participated", "assisted"]
    assert len(results) == 2
    assert all(result.eligible is False for result in results)


def test_directness_uses_generic_dimensions_not_concept_labels() -> None:
    requirement = _requirement(
        constraints=(
            _constraint(
                SemanticConstraintDimension.SOURCE_KIND,
                EvidenceSourceKind.PROJECT.value,
            ),
        )
    )

    first = evaluate_evidence_compatibility(
        requirement,
        _evidence(source_kind=EvidenceSourceKind.PROJECT, concepts=("concept-x",)),
    )
    second = evaluate_evidence_compatibility(
        requirement,
        _evidence(source_kind=EvidenceSourceKind.PROJECT, concepts=("concept-y",)),
    )

    assert first.eligible is second.eligible is True
    assert first.directness is second.directness is EvidenceDirectness.DIRECT
    assert first.rank == second.rank
    assert first.reason_codes == second.reason_codes == ()


def test_education_expectation_requires_education_source_without_becoming_work() -> None:
    requirement = _requirement(expectation=EvidenceExpectation.EDUCATION)

    education = evaluate_evidence_compatibility(
        requirement,
        _evidence(
            context=SemanticContext.STUDIED,
            source_kind=EvidenceSourceKind.EDUCATION,
        ),
    )
    work = evaluate_evidence_compatibility(
        requirement,
        _evidence(
            context=SemanticContext.USED_IN_EMPLOYMENT,
            source_kind=EvidenceSourceKind.EMPLOYMENT,
        ),
    )

    assert education.eligible is True
    assert education.directness is EvidenceDirectness.DIRECT
    assert work.eligible is False
    assert work.directness is EvidenceDirectness.INCOMPATIBLE
    assert work.reason_codes == ("education_evidence_required",)


def test_credential_expectation_requires_credential_source_without_becoming_practice() -> None:
    requirement = _requirement(expectation=EvidenceExpectation.CREDENTIAL)

    credential = evaluate_evidence_compatibility(
        requirement,
        _evidence(
            context=SemanticContext.CREDENTIALED,
            source_kind=EvidenceSourceKind.CREDENTIAL,
        ),
    )
    practice = evaluate_evidence_compatibility(
        requirement,
        _evidence(
            context=SemanticContext.USED_IN_EMPLOYMENT,
            source_kind=EvidenceSourceKind.SKILL,
        ),
    )

    assert credential.eligible is True
    assert credential.directness is EvidenceDirectness.DIRECT
    assert practice.eligible is False
    assert practice.reason_codes == ("credential_evidence_required",)


def test_demonstrated_usage_rejects_mention_but_accepts_project_usage() -> None:
    requirement = _requirement(expectation=EvidenceExpectation.DEMONSTRATED_USAGE)

    mention = evaluate_evidence_compatibility(requirement, _evidence())
    project = evaluate_evidence_compatibility(
        requirement,
        _evidence(
            context=SemanticContext.USED_IN_PROJECT,
            source_kind=EvidenceSourceKind.PROJECT,
        ),
    )

    assert mention.eligible is False
    assert mention.directness is EvidenceDirectness.INDIRECT
    assert mention.reason_codes == ("demonstrated_usage_required",)
    assert project.eligible is True
    assert project.directness is EvidenceDirectness.DIRECT
    assert project.rank > mention.rank


def test_matching_secondary_constraint_does_not_override_expectation_mismatch() -> None:
    requirement = _requirement(
        expectation=EvidenceExpectation.DEMONSTRATED_USAGE,
        constraints=(
            _constraint(
                SemanticConstraintDimension.SOURCE_KIND,
                EvidenceSourceKind.SKILL.value,
            ),
        ),
    )

    mention = evaluate_evidence_compatibility(requirement, _evidence())

    assert mention.eligible is False
    assert mention.directness is EvidenceDirectness.INDIRECT
    assert mention.reason_codes == ("demonstrated_usage_required",)


@pytest.mark.parametrize("failing_constraint_first", [False, True])
def test_constraint_failure_is_retained_regardless_of_constraint_order(
    failing_constraint_first: bool,
) -> None:
    context_match = _constraint(
        SemanticConstraintDimension.CONTEXT,
        SemanticContext.USED_IN_PROJECT.value,
        operator=SemanticConstraintOperator.EQUALS,
    )
    source_kind_mismatch = _constraint(
        SemanticConstraintDimension.SOURCE_KIND,
        EvidenceSourceKind.EMPLOYMENT.value,
    )
    constraints = (
        (source_kind_mismatch, context_match)
        if failing_constraint_first
        else (context_match, source_kind_mismatch)
    )
    requirement = _requirement(constraints=constraints)

    result = evaluate_evidence_compatibility(
        requirement,
        _evidence(
            context=SemanticContext.USED_IN_PROJECT,
            source_kind=EvidenceSourceKind.PROJECT,
        ),
    )

    assert result.eligible is False
    assert result.directness is EvidenceDirectness.INCOMPATIBLE
    assert result.reason_codes == ("source_kind_mismatch",)


def test_unresolved_constraint_fails_closed_when_other_semantics_match() -> None:
    requirement = _requirement(
        expectation=EvidenceExpectation.EDUCATION,
        constraints=(
            _constraint(
                SemanticConstraintDimension.SOURCE_KIND,
                EvidenceSourceKind.EDUCATION.value,
            ),
            _constraint(
                SemanticConstraintDimension.UNRESOLVED,
                "opaque source-authored constraint",
                operator=SemanticConstraintOperator.DECLARED,
            ),
        ),
    )

    result = evaluate_evidence_compatibility(
        requirement,
        _evidence(
            context=SemanticContext.STUDIED,
            source_kind=EvidenceSourceKind.EDUCATION,
        ),
    )

    assert result.eligible is False
    assert result.directness is EvidenceDirectness.INCOMPATIBLE
    assert result.reason_codes == ("unresolved_constraint",)


def test_minimum_strength_constraint_is_generic_and_deterministic() -> None:
    requirement = _requirement(
        constraints=(
            _constraint(
                SemanticConstraintDimension.MINIMUM_STRENGTH,
                "work",
                operator=SemanticConstraintOperator.AT_LEAST,
            ),
        )
    )

    project = evaluate_evidence_compatibility(
        requirement,
        _evidence(
            context=SemanticContext.USED_IN_PROJECT,
            source_kind=EvidenceSourceKind.PROJECT,
        ),
    )
    employment = evaluate_evidence_compatibility(
        requirement,
        _evidence(
            context=SemanticContext.USED_IN_EMPLOYMENT,
            source_kind=EvidenceSourceKind.EMPLOYMENT,
        ),
    )

    assert project.eligible is False
    assert project.reason_codes == ("minimum_evidence_strength_not_met",)
    assert employment.eligible is True
    assert employment.directness is EvidenceDirectness.DIRECT
