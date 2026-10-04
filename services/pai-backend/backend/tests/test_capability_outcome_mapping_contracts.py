import pytest
from pydantic import ValidationError

from app.capability_governance.evidence import SemanticEvidence, SemanticEvidenceKind
from app.capability_governance.identity import (
    CanonicalCapabilityRef,
    SourceSemanticKind,
    SourceSemanticRef,
)
from app.capability_governance.mapping import (
    CapabilityMappingProposal,
    CapabilityMappingReview,
    MappingDecision,
    MappingScope,
    MappingType,
    ProposalMethod,
    UnmappedSemantic,
    UnmappedSemanticReason,
    validate_mapping_review_for_proposal,
)
from app.capability_governance.outcomes import CourseLearningOutcome


def outcome_ref() -> SourceSemanticRef:
    return SourceSemanticRef(
        source_namespace="skillscommons",
        entity_kind=SourceSemanticKind.COURSE_LEARNING_OUTCOME,
        source_id="course-123#objective-3",
        source_version="metadata-v2",
    )


def course_outcome() -> CourseLearningOutcome:
    return CourseLearningOutcome(
        outcome_ref=outcome_ref(),
        course_ref="skillscommons:course-123",
        statement="Write Python programs using functions and control flow.",
        source_locator="dspace:item:course-123:package:imscc:objective:3",
    )


def evidence() -> SemanticEvidence:
    return SemanticEvidence(
        source_ref=outcome_ref(),
        source_locator="dspace:item:course-123:package:imscc:objective:3",
        evidence_text="Write Python programs using functions and control flow.",
        evidence_kind=SemanticEvidenceKind.EXPLICIT_OUTCOME,
    )


def proposal(
    *,
    proposal_id: str = "proposal:course-123:objective-3",
    target: str = "capability:test_unregistered:synthetic_capability",
    source: SourceSemanticRef | None = None,
    mapping_scope: MappingScope = MappingScope.OUTCOME_CAPABILITY_FACET,
    proposal_method: ProposalMethod = ProposalMethod.MANUAL,
    proposer_ref: str = "actor:source-steward",
    rationale: str | None = None,
    evidence_items: tuple[SemanticEvidence, ...] | None = None,
) -> CapabilityMappingProposal:
    return CapabilityMappingProposal(
        proposal_id=proposal_id,
        source_ref=source if source is not None else outcome_ref(),
        target_capability_ref=CanonicalCapabilityRef.parse(target),
        mapping_type=MappingType.EXACT,
        mapping_scope=mapping_scope,
        evidence=evidence_items if evidence_items is not None else (evidence(),),
        proposal_method=proposal_method,
        proposer_ref=proposer_ref,
        rationale=rationale,
    )


def test_course_learning_outcome_keeps_course_source_and_capability_identities_distinct() -> None:
    item = course_outcome()
    canonical_ref = CanonicalCapabilityRef.parse("capability:software:programming_fundamentals")

    assert item.outcome_ref.source_id == "course-123#objective-3"
    assert item.course_ref == "skillscommons:course-123"
    assert item.outcome_ref != canonical_ref
    assert item.statement == "Write Python programs using functions and control flow."


def test_course_learning_outcome_requires_course_outcome_source_kind() -> None:
    with pytest.raises(ValidationError, match="course_learning_outcome_ref_required"):
        CourseLearningOutcome(
            outcome_ref=SourceSemanticRef(
                source_namespace="skillscommons",
                entity_kind=SourceSemanticKind.COURSE_DIRECT_CLAIM,
                source_id="course-123#claim-1",
            ),
            course_ref="skillscommons:course-123",
            statement="Write Python programs using functions and control flow.",
            source_locator="dspace:item:course-123:package:imscc:objective:3",
        )


@pytest.mark.parametrize("missing", ["outcome_ref", "course_ref", "statement", "source_locator"])
def test_course_learning_outcome_requires_source_identity_course_statement_and_locator(
    missing: str,
) -> None:
    payload = {
        "outcome_ref": outcome_ref(),
        "course_ref": "skillscommons:course-123",
        "statement": "Write Python programs using functions and control flow.",
        "source_locator": "dspace:item:course-123:package:imscc:objective:3",
    }
    payload.pop(missing)

    with pytest.raises(ValidationError):
        CourseLearningOutcome.model_validate(payload)


@pytest.mark.parametrize("field", ["course_ref", "statement", "source_locator"])
def test_course_learning_outcome_rejects_blank_required_text(field: str) -> None:
    payload = {
        "outcome_ref": outcome_ref(),
        "course_ref": "skillscommons:course-123",
        "statement": "A stated outcome.",
        "source_locator": "dspace:item:course-123:metadata:outcome",
    }
    payload[field] = "  "

    with pytest.raises(ValidationError):
        CourseLearningOutcome.model_validate(payload)


def test_course_learning_outcome_enforces_documented_text_bounds() -> None:
    with pytest.raises(ValidationError):
        CourseLearningOutcome(
            outcome_ref=outcome_ref(),
            course_ref="skillscommons:course-123",
            statement="x" * 4001,
            source_locator="dspace:item:course-123:metadata:outcome",
        )
    with pytest.raises(ValidationError):
        CourseLearningOutcome(
            outcome_ref=outcome_ref(),
            course_ref="skillscommons:course-123",
            statement="A stated outcome.",
            source_locator="x" * 2049,
        )


def test_course_learning_outcome_serialization_is_stable() -> None:
    item = course_outcome()

    assert item.model_dump(mode="json") == CourseLearningOutcome.model_validate(
        item.model_dump(mode="python")
    ).model_dump(mode="json")
    assert (
        item.model_dump_json()
        == CourseLearningOutcome.model_validate_json(item.model_dump_json()).model_dump_json()
    )


def test_semantic_evidence_requires_source_and_nonblank_bounded_locator_and_excerpt() -> None:
    assert evidence().evidence_text == "Write Python programs using functions and control flow."

    invalid_payloads = [
        {
            "source_locator": "dspace:item:course-123:metadata:outcome",
            "evidence_text": "Evidence text.",
            "evidence_kind": SemanticEvidenceKind.SOURCE_TEXT,
        },
        {
            "source_ref": outcome_ref(),
            "evidence_text": "Evidence text.",
            "evidence_kind": SemanticEvidenceKind.SOURCE_TEXT,
        },
        {
            "source_ref": outcome_ref(),
            "source_locator": "dspace:item:course-123:metadata:outcome",
            "evidence_kind": SemanticEvidenceKind.SOURCE_TEXT,
        },
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            SemanticEvidence.model_validate(payload)

    for field in ("source_locator", "evidence_text"):
        with pytest.raises(ValidationError):
            SemanticEvidence(
                source_ref=outcome_ref(),
                source_locator=("  " if field == "source_locator" else "dspace:item:course-123"),
                evidence_text=("  " if field == "evidence_text" else "A concise source excerpt."),
                evidence_kind=SemanticEvidenceKind.SOURCE_TEXT,
            )


@pytest.mark.parametrize("field,maximum", [("evidence_text", 500), ("source_locator", 2048)])
def test_semantic_evidence_enforces_repository_bounds(field: str, maximum: int) -> None:
    payload = {
        "source_ref": outcome_ref(),
        "source_locator": "dspace:item:course-123:metadata:outcome",
        "evidence_text": "A concise source excerpt.",
        "evidence_kind": SemanticEvidenceKind.SOURCE_TEXT,
    }
    payload[field] = "x" * (maximum + 1)

    with pytest.raises(ValidationError):
        SemanticEvidence.model_validate(payload)


def test_semantic_evidence_retains_source_version_and_serializes_deterministically() -> None:
    item = evidence()

    assert item.source_ref.source_version == "metadata-v2"
    assert (
        item.model_dump_json()
        == SemanticEvidence.model_validate_json(item.model_dump_json()).model_dump_json()
    )


def test_exact_mapping_proposal_accepts_syntactically_valid_unregistered_target() -> None:
    item = proposal()

    assert str(item.target_capability_ref) == "capability:test_unregistered:synthetic_capability"
    assert item.mapping_type is MappingType.EXACT
    assert item.source_ref == outcome_ref()
    assert not hasattr(item, "authority")
    assert not hasattr(item, "active")


@pytest.mark.parametrize(
    "missing",
    [
        "proposal_id",
        "source_ref",
        "target_capability_ref",
        "mapping_scope",
        "evidence",
        "proposal_method",
        "proposer_ref",
    ],
)
def test_mapping_proposal_requires_traceable_source_target_evidence_and_proposer(
    missing: str,
) -> None:
    payload = proposal().model_dump(mode="python")
    payload.pop(missing)

    with pytest.raises(ValidationError):
        CapabilityMappingProposal.model_validate(payload)


def test_mapping_proposal_rejects_invalid_target_syntax_and_non_exact_mapping() -> None:
    with pytest.raises(ValidationError):
        proposal(target="not-a-canonical-ref")

    payload = proposal().model_dump(mode="python")
    payload["mapping_type"] = "related_to"
    with pytest.raises(ValidationError):
        CapabilityMappingProposal.model_validate(payload)


@pytest.mark.parametrize(
    "scope",
    [
        MappingScope.CAPABILITY_FACET,
        MappingScope.OUTCOME_CAPABILITY_FACET,
        MappingScope.DIRECT_CAPABILITY_CLAIM,
    ],
)
def test_mapping_proposal_requires_one_bounded_facet_scope(scope: MappingScope) -> None:
    assert proposal(mapping_scope=scope).mapping_scope is scope


@pytest.mark.parametrize(
    "method",
    [ProposalMethod.MANUAL, ProposalMethod.GOVERNED_RULE, ProposalMethod.AI_ASSISTED],
)
def test_mapping_method_is_explicit_and_proposal_never_implies_review(
    method: ProposalMethod,
) -> None:
    item = proposal(proposal_method=method)

    assert item.proposal_method is method
    assert not hasattr(item, "review_status")
    assert not hasattr(item, "active")


def test_mapping_evidence_is_immutable_sorted_and_deduplicated_by_full_value() -> None:
    first = evidence()
    same_locator_other_excerpt = SemanticEvidence(
        source_ref=outcome_ref(),
        source_locator=first.source_locator,
        evidence_text="A different statement in the same source location.",
        evidence_kind=SemanticEvidenceKind.EXPLICIT_OUTCOME,
    )

    ordered = proposal(evidence_items=(first, same_locator_other_excerpt))
    reversed_order = proposal(evidence_items=(same_locator_other_excerpt, first))

    assert isinstance(ordered.evidence, tuple)
    assert ordered.model_dump(mode="json") == reversed_order.model_dump(mode="json")
    assert ordered.proposal_fingerprint == reversed_order.proposal_fingerprint
    with pytest.raises(ValidationError, match="duplicate_semantic_evidence"):
        proposal(evidence_items=(first, first))


def test_proposal_fingerprint_is_stable_and_changes_with_content() -> None:
    original = proposal()
    identical = proposal()
    changed = proposal(rationale="Reviewed source facet semantics.")

    assert original.proposal_fingerprint == identical.proposal_fingerprint
    assert original.proposal_fingerprint.startswith("sha256:")
    assert original.proposal_fingerprint != changed.proposal_fingerprint


@pytest.mark.parametrize(
    "decision",
    [MappingDecision.APPROVE, MappingDecision.REJECT, MappingDecision.UNCERTAIN],
)
def test_mapping_review_pins_exact_proposal_without_activating_it(
    decision: MappingDecision,
) -> None:
    item = proposal()
    review = CapabilityMappingReview(
        proposal_id=item.proposal_id,
        proposal_fingerprint=item.proposal_fingerprint,
        reviewer_ref="actor:independent-reviewer",
        decision=decision,
        rationale="Reviewed the bounded semantic facet.",
    )

    validate_mapping_review_for_proposal(item, review)

    assert review.decision is decision
    assert review.proposal_fingerprint == item.proposal_fingerprint
    assert not hasattr(review, "active")
    assert not hasattr(item, "authority")


def test_mapping_review_rejects_changed_proposal_id_or_fingerprint() -> None:
    item = proposal()
    mismatched_id = CapabilityMappingReview(
        proposal_id="proposal:other",
        proposal_fingerprint=item.proposal_fingerprint,
        reviewer_ref="actor:reviewer",
        decision=MappingDecision.APPROVE,
        rationale="Reviewed.",
    )
    mismatched_fingerprint = CapabilityMappingReview(
        proposal_id=item.proposal_id,
        proposal_fingerprint="sha256:" + "0" * 64,
        reviewer_ref="actor:reviewer",
        decision=MappingDecision.APPROVE,
        rationale="Reviewed.",
    )

    with pytest.raises(ValueError, match="review_proposal_id_mismatch"):
        validate_mapping_review_for_proposal(item, mismatched_id)
    with pytest.raises(ValueError, match="review_proposal_fingerprint_mismatch"):
        validate_mapping_review_for_proposal(item, mismatched_fingerprint)


def test_mapping_review_requires_reviewer_independent_of_proposer() -> None:
    item = proposal(proposer_ref="actor:same-person")
    review = CapabilityMappingReview(
        proposal_id=item.proposal_id,
        proposal_fingerprint=item.proposal_fingerprint,
        reviewer_ref="actor:same-person",
        decision=MappingDecision.APPROVE,
        rationale="Reviewed.",
    )

    with pytest.raises(ValueError, match="reviewer_must_be_independent"):
        validate_mapping_review_for_proposal(item, review)


def test_unmapped_semantic_is_valid_without_a_canonical_target() -> None:
    item = UnmappedSemantic(
        source_ref=outcome_ref(),
        evidence=(evidence(),),
        reason=UnmappedSemanticReason.INSUFFICIENT_EVIDENCE,
    )

    assert item.source_ref == outcome_ref()
    assert item.evidence == (evidence(),)
    assert not hasattr(item, "target_capability_ref")
    assert not hasattr(item, "canonical_capability_ref")


@pytest.mark.parametrize(
    "reason",
    [
        UnmappedSemanticReason.NO_CANONICAL_MATCH,
        UnmappedSemanticReason.INSUFFICIENT_EVIDENCE,
        UnmappedSemanticReason.MAPPING_REJECTED,
        UnmappedSemanticReason.DEFERRED_GOVERNANCE,
    ],
)
def test_unmapped_semantic_supports_bounded_non_inferred_reasons(
    reason: UnmappedSemanticReason,
) -> None:
    item = UnmappedSemantic(source_ref=outcome_ref(), evidence=(evidence(),), reason=reason)

    assert item.reason is reason


def test_unmapped_semantic_rejects_nearest_match_reason() -> None:
    with pytest.raises(ValidationError):
        UnmappedSemantic.model_validate(
            {
                "source_ref": outcome_ref(),
                "evidence": (evidence(),),
                "reason": "nearest_match_failed",
            }
        )


@pytest.mark.parametrize("missing", ["source_ref", "evidence"])
def test_unmapped_semantic_requires_source_and_evidence(missing: str) -> None:
    payload = {
        "source_ref": outcome_ref(),
        "evidence": (evidence(),),
        "reason": UnmappedSemanticReason.NO_CANONICAL_MATCH,
    }
    payload.pop(missing)

    with pytest.raises(ValidationError):
        UnmappedSemantic.model_validate(payload)

    with pytest.raises(ValidationError):
        UnmappedSemantic(
            source_ref=outcome_ref(),
            evidence=(),
            reason=UnmappedSemanticReason.NO_CANONICAL_MATCH,
        )


def test_unmapped_evidence_uses_immutable_full_value_canonical_tuple() -> None:
    first = evidence()
    second = SemanticEvidence(
        source_ref=outcome_ref(),
        source_locator=first.source_locator,
        evidence_text="A distinct excerpt at the same source locator.",
        evidence_kind=SemanticEvidenceKind.EXPLICIT_OUTCOME,
    )
    forward = UnmappedSemantic(
        source_ref=outcome_ref(),
        evidence=(first, second),
        reason=UnmappedSemanticReason.DEFERRED_GOVERNANCE,
    )
    reverse = UnmappedSemantic(
        source_ref=outcome_ref(),
        evidence=(second, first),
        reason=UnmappedSemanticReason.DEFERRED_GOVERNANCE,
    )

    assert isinstance(forward.evidence, tuple)
    assert forward.model_dump(mode="json") == reverse.model_dump(mode="json")
    with pytest.raises(ValidationError, match="duplicate_semantic_evidence"):
        UnmappedSemantic(
            source_ref=outcome_ref(),
            evidence=(first, first),
            reason=UnmappedSemanticReason.NO_CANONICAL_MATCH,
        )


def test_direct_capability_claim_does_not_require_a_fake_outcome() -> None:
    direct_claim_ref = SourceSemanticRef(
        source_namespace="skillscommons",
        entity_kind=SourceSemanticKind.COURSE_DIRECT_CLAIM,
        source_id="course-123#direct-claim-1",
    )
    item = proposal(
        source=direct_claim_ref,
        mapping_scope=MappingScope.DIRECT_CAPABILITY_CLAIM,
    )

    assert item.source_ref == direct_claim_ref
    assert item.source_ref.entity_kind is SourceSemanticKind.COURSE_DIRECT_CLAIM
    assert not hasattr(item.source_ref, "outcome_ref")


def test_role_and_learning_need_source_ids_remain_source_owned() -> None:
    role_requirement_ref = SourceSemanticRef(
        source_namespace="role_profile",
        entity_kind=SourceSemanticKind.ROLE_REQUIREMENT,
        source_id="requirement-17",
        source_version="role-v4",
    )
    learning_need_ref = SourceSemanticRef(
        source_namespace="learning_need",
        entity_kind=SourceSemanticKind.LEARNING_NEED_COMPETENCY,
        source_id="competency-17",
        source_version="need-v2",
    )
    item = proposal(source=role_requirement_ref)

    assert item.source_ref.source_id == "requirement-17"
    assert learning_need_ref.source_id == "competency-17"
    assert role_requirement_ref != learning_need_ref


def test_topic_text_alone_cannot_construct_a_provenanced_outcome_record() -> None:
    with pytest.raises(ValidationError):
        CourseLearningOutcome.model_validate({"statement": "Python"})
