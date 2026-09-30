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


def _constraint(
    dimension: SemanticConstraintDimension,
    *values: str,
) -> SemanticConstraint:
    return SemanticConstraint(
        dimension=dimension,
        operator=SemanticConstraintOperator.ONE_OF,
        values=values,
        source_field="fixture_requirement",
    )


def _requirement(
    *concepts: str,
    expectation: EvidenceExpectation,
    constraints: tuple[SemanticConstraint, ...] = (),
) -> RequirementSemantics:
    return RequirementSemantics(
        requirement_id="requirement-1",
        concepts=concepts,
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
    evidence_ref: str,
    concept: str,
    *,
    context: SemanticContext,
    source_kind: EvidenceSourceKind,
    participation: str | None = None,
    confidence: float = 0.9,
) -> EvidenceSemantics:
    return EvidenceSemantics(
        evidence_ref=evidence_ref,
        concepts=(concept,),
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
        source_value=concept,
        source_excerpt="source-backed fixture observation",
        provenance=(("source", "fixture"),),
        unresolved_fields=(),
    )


def test_identity_baseline_is_nfkc_casefolded_and_whitespace_collapsed() -> None:
    requirement = _requirement(
        "Ｆｉｅｌｄ   Practice",
        expectation=EvidenceExpectation.DEMONSTRATED_USAGE,
    )
    evidence = _evidence(
        "work",
        "field practice",
        context=SemanticContext.USED_IN_EMPLOYMENT,
        source_kind=EvidenceSourceKind.EMPLOYMENT,
    )

    candidates = retrieve_candidates(requirement, (evidence,))

    assert normalize_identity_phrase("  Ｆｉｅｌｄ   Practice ") == "field practice"
    assert len(candidates) == 1
    assert candidates[0].matched_concepts == ("field practice",)


def test_identity_baseline_does_not_add_aliases_morphology_or_substring_matches() -> None:
    requirement = _requirement("lead outcome", "sql", expectation=EvidenceExpectation.UNKNOWN)
    evidence = (
        _evidence(
            "morphology",
            "led outcomes",
            context=SemanticContext.USED_IN_EMPLOYMENT,
            source_kind=EvidenceSourceKind.EMPLOYMENT,
        ),
        _evidence(
            "substring",
            "nosql",
            context=SemanticContext.USED_IN_EMPLOYMENT,
            source_kind=EvidenceSourceKind.EMPLOYMENT,
        ),
    )

    assert retrieve_candidates(requirement, evidence) == ()


def test_demonstrated_usage_assessment_uses_eligible_project_over_mention() -> None:
    requirement = _requirement(
        "concept-a",
        expectation=EvidenceExpectation.DEMONSTRATED_USAGE,
    )
    evidence = (
        _evidence(
            "mention",
            "concept-a",
            context=SemanticContext.MENTIONED,
            source_kind=EvidenceSourceKind.SKILL,
            confidence=0.99,
        ),
        _evidence(
            "project",
            "concept-a",
            context=SemanticContext.USED_IN_PROJECT,
            source_kind=EvidenceSourceKind.PROJECT,
            confidence=0.9,
        ),
    )

    result = assess_retrieval(requirement, retrieve_candidates(requirement, evidence), 0.8)

    assert result.status is SemanticAssessmentStatus.SUPPORTED
    assert result.retrieved_candidate_count == 2
    assert result.eligible_candidate_count == 1
    assert result.strongest_evidence_refs == ("project",)
    assert result.covered_concepts == ("concept-a",)
    assert result.missing_concepts == ()


def test_degree_requirement_uses_direct_education_without_becoming_work() -> None:
    requirement = _requirement("field-a", expectation=EvidenceExpectation.EDUCATION)
    evidence = (
        _evidence(
            "education",
            "field-a",
            context=SemanticContext.STUDIED,
            source_kind=EvidenceSourceKind.EDUCATION,
        ),
        _evidence(
            "work",
            "field-a",
            context=SemanticContext.USED_IN_EMPLOYMENT,
            source_kind=EvidenceSourceKind.EMPLOYMENT,
        ),
    )

    result = assess_retrieval(requirement, retrieve_candidates(requirement, evidence), 0.8)

    assert result.status is SemanticAssessmentStatus.SUPPORTED
    assert result.retrieved_candidate_count == 2
    assert result.eligible_candidate_count == 1
    assert result.strongest_evidence_refs == ("education",)


def test_credential_requirement_uses_direct_credential_without_becoming_practice() -> None:
    requirement = _requirement("credential-a", expectation=EvidenceExpectation.CREDENTIAL)
    evidence = (
        _evidence(
            "credential",
            "credential-a",
            context=SemanticContext.CREDENTIALED,
            source_kind=EvidenceSourceKind.CREDENTIAL,
        ),
        _evidence(
            "practice",
            "credential-a",
            context=SemanticContext.USED_IN_EMPLOYMENT,
            source_kind=EvidenceSourceKind.SKILL,
        ),
    )

    result = assess_retrieval(requirement, retrieve_candidates(requirement, evidence), 0.8)

    assert result.status is SemanticAssessmentStatus.SUPPORTED
    assert result.eligible_candidate_count == 1
    assert result.strongest_evidence_refs == ("credential",)


def test_owned_outcome_requirement_rejects_participation_and_uses_owned_evidence() -> None:
    requirement = _requirement("outcome-a", expectation=EvidenceExpectation.OWNED_OUTCOME)
    evidence = (
        _evidence(
            "participated",
            "outcome-a",
            context=SemanticContext.USED_IN_EMPLOYMENT,
            source_kind=EvidenceSourceKind.EMPLOYMENT,
            participation="participated",
        ),
        _evidence(
            "owned",
            "outcome-a",
            context=SemanticContext.OWNED_SYSTEM,
            source_kind=EvidenceSourceKind.EMPLOYMENT,
            participation="owned",
        ),
    )

    result = assess_retrieval(requirement, retrieve_candidates(requirement, evidence), 0.8)

    assert result.status is SemanticAssessmentStatus.SUPPORTED
    assert result.retrieved_candidate_count == 2
    assert result.eligible_candidate_count == 1
    assert result.strongest_evidence_refs == ("owned",)


def test_retrieved_candidates_can_all_be_context_ineligible_without_becoming_missing() -> None:
    requirement = _requirement(
        "deployment-a",
        expectation=EvidenceExpectation.DEMONSTRATED_USAGE,
        constraints=(
            _constraint(
                SemanticConstraintDimension.CONTEXT,
                SemanticContext.USED_IN_PRODUCTION.value,
            ),
        ),
    )
    evidence = (
        _evidence(
            "project-1",
            "deployment-a",
            context=SemanticContext.USED_IN_PROJECT,
            source_kind=EvidenceSourceKind.PROJECT,
            confidence=0.92,
        ),
        _evidence(
            "project-2",
            "deployment-a",
            context=SemanticContext.USED_IN_PROJECT,
            source_kind=EvidenceSourceKind.PROJECT,
            confidence=0.9,
        ),
    )

    result = assess_retrieval(requirement, retrieve_candidates(requirement, evidence), 0.8)

    assert result.status is SemanticAssessmentStatus.CONTEXT_MISMATCH
    assert result.retrieved_candidate_count == 2
    assert result.eligible_candidate_count == 0
    assert result.strongest_evidence_refs == ("project-1",)


def test_partial_concept_coverage_is_not_reported_as_full_support() -> None:
    requirement = _requirement(
        "concept-a",
        "concept-b",
        expectation=EvidenceExpectation.DEMONSTRATED_USAGE,
    )
    evidence = (
        _evidence(
            "project",
            "concept-a",
            context=SemanticContext.USED_IN_PROJECT,
            source_kind=EvidenceSourceKind.PROJECT,
        ),
    )

    result = assess_retrieval(requirement, retrieve_candidates(requirement, evidence), 0.8)

    assert result.status is SemanticAssessmentStatus.REQUIRES_VERIFICATION
    assert result.covered_concepts == ("concept-a",)
    assert result.missing_concepts == ("concept-b",)
