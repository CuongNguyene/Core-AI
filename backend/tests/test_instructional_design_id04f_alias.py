from app.instructional_design.orchestrator import attach_prerequisite_dependency_provenance
from app.instructional_design.provenance_aliases import (
    DependencyIdentity,
    resolve_dependency_identity,
)
from app.instructional_design.schemas import (
    AssessmentDependencyCandidate,
    DesignFinding,
    PrerequisiteBasis,
    PrerequisiteDisposition,
    PrerequisiteSpec,
    PrerequisiteStatus,
)


def _candidate(name: str) -> AssessmentDependencyCandidate:
    return AssessmentDependencyCandidate(
        capability=name,
        reason="explicit test dependency",
        required_for_refs=["objective-1"],
    )


def _identity(*aliases: str) -> DependencyIdentity:
    return DependencyIdentity(
        dependency_ref="dependency_candidate:contract_clause_structure",
        canonical_name="contract clause structure",
        aliases=aliases,
    )


def test_canonical_name_matches() -> None:
    result = resolve_dependency_identity(
        "Contract   Clause Structure",
        [_candidate("contract clause structure"), _candidate("commercial clause structure")],
        identities=[_identity("commercial contract clause structure")],
    )
    assert result.dependency_ref == "dependency_candidate:contract_clause_structure"
    assert result.conflict is False


def test_declared_alias_matches_and_preserves_ref() -> None:
    result = resolve_dependency_identity(
        "commercial contract clause structure",
        [_candidate("contract clause structure")],
        identities=[_identity("commercial contract clause structure")],
    )
    assert result.dependency_ref == "dependency_candidate:contract_clause_structure"
    assert result.conflict is False


def test_unknown_paraphrase_fails_closed() -> None:
    result = resolve_dependency_identity(
        "advanced commercial legal drafting structure",
        [_candidate("contract clause structure")],
        identities=[_identity("commercial contract clause structure")],
    )
    assert result.dependency_ref is None
    assert result.conflict is False


def test_semantic_neighbor_fails_closed() -> None:
    result = resolve_dependency_identity(
        "contract negotiation strategy",
        [_candidate("contract clause structure")],
        identities=[_identity("commercial contract clause structure")],
    )
    assert result.dependency_ref is None
    assert result.conflict is False


def test_alias_conflict_fails_closed_without_selection() -> None:
    result = resolve_dependency_identity(
        "commercial contract clause structure",
        [
            _candidate("contract clause structure"),
            _candidate("commercial contract clause structure"),
        ],
        identities=[
            _identity("commercial contract clause structure"),
            DependencyIdentity(
                dependency_ref="dependency_candidate:commercial_clause_structure",
                canonical_name="commercial clause structure",
                aliases=("commercial contract clause structure",),
            ),
        ],
    )
    assert result.dependency_ref is None
    assert result.conflict is True


def test_alias_attach_preserves_candidate_governance_and_source_ref() -> None:
    prerequisite = PrerequisiteSpec(
        id="prereq-legal",
        capability="commercial contract clause structure",
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
        disposition=PrerequisiteDisposition.ENTRY_PREREQUISITE,
        rationale="must be known before entry",
        required_for_refs=["objective-1"],
    )
    recovered = attach_prerequisite_dependency_provenance(
        [prerequisite],
        [_candidate("contract clause structure"), _candidate("other")],
        dependency_identities=[_identity("commercial contract clause structure")],
    )
    assert recovered[0].source_dependency_refs == [
        "dependency_candidate:contract_clause_structure"
    ]
    assert recovered[0].status is PrerequisiteStatus.CANDIDATE
    assert recovered[0].basis is PrerequisiteBasis.MODEL_PROPOSED


def test_alias_conflict_emits_finding_and_does_not_select() -> None:
    prerequisite = PrerequisiteSpec(
        id="prereq-conflict",
        capability="commercial contract clause structure",
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
        disposition=PrerequisiteDisposition.IN_COURSE_SUPPORT,
        rationale="can be scaffolded",
        required_for_refs=["objective-1"],
    )
    findings: list[DesignFinding] = []
    recovered = attach_prerequisite_dependency_provenance(
        [prerequisite],
        [_candidate("contract clause structure"), _candidate("other")],
        dependency_identities=[
            _identity("commercial contract clause structure"),
            DependencyIdentity(
                dependency_ref="dependency_candidate:other",
                canonical_name="other",
                aliases=("commercial contract clause structure",),
            ),
        ],
        findings=findings,
    )
    assert recovered[0].source_dependency_refs == []
    assert [item.code for item in findings] == ["dependency_alias_conflict"]
