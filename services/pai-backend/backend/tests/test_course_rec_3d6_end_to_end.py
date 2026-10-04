from __future__ import annotations

import pytest
import test_governed_target_adapter as target_fixtures

from app.capability_governance.course_projection import (
    GovernedOutcomeMappingInput,
    project_governed_course_capabilities,
)
from app.capability_governance.definitions import CapabilityDefinition
from app.capability_governance.evidence import SemanticEvidence, SemanticEvidenceKind
from app.capability_governance.governed_mapping import deprecate_governed_mapping
from app.capability_governance.identity import (
    CanonicalCapabilityRef,
    SourceSemanticKind,
    SourceSemanticRef,
)
from app.capability_governance.mapping import MappingScope
from app.capability_governance.mapping_errors import MappingGovernanceError
from app.capability_governance.mapping_resolution import (
    BindingResolutionMode,
    resolve_governed_mapping_historical,
)
from app.capability_governance.outcomes import CourseLearningOutcome
from app.capability_governance.packs import (
    CapabilityGovernanceDecision,
    CapabilityGovernanceReview,
    CapabilityReleaseApproval,
    activate_capability_pack_release,
    build_capability_pack_release,
)
from app.capability_governance.resolution import CapabilityDefinitionPin
from app.capability_governance.target_adapter import (
    RequiredTargetFacet,
)
from app.course_catalog.schemas import (
    CourseAvailability,
    CourseCapability,
    CourseCapabilityProfile,
    CourseProfileStatus,
    CourseProvenance,
    CourseSourceType,
    CoverageType,
)
from app.course_recommendation.engine import CourseRecommendationEngine
from app.course_recommendation.schemas import (
    CourseRecommendationCandidate,
    CourseRecommendationRequest,
    candidate_from_profile,
)

CAPABILITY_COMMUNICATION = "capability:test_core:communication"
CAPABILITY_WRITING = "capability:test_core:writing"


def _active_domain_release(
    capability_ref: str, *, version: str = "1.0", description: str | None = None
):
    namespace = CanonicalCapabilityRef.parse(capability_ref).namespace_key
    draft = build_capability_pack_release(
        pack_id=f"test_{namespace}_pack",
        namespace_key=namespace,
        version=version,
        owner_ref="team:synthetic-test",
        definitions=(
            CapabilityDefinition(
                canonical_ref=capability_ref,
                label=f"Synthetic {namespace} capability",
                definition=description or f"Synthetic definition for {capability_ref}.",
            ),
        ),
    )
    return activate_capability_pack_release(
        draft,
        review=CapabilityGovernanceReview(
            review_ref=f"review:{namespace}:{version}",
            reviewer_ref="actor:synthetic-reviewer",
            decision=CapabilityGovernanceDecision.APPROVE,
            collision_review_ref=f"collision:{namespace}:{version}",
        ),
        approval=CapabilityReleaseApproval(
            approval_ref=f"approval:{namespace}:{version}",
            approver_ref="actor:synthetic-approver",
            decision=CapabilityGovernanceDecision.APPROVE,
        ),
    )


def _require_exact_pin_compatibility(
    target_pins: tuple[CapabilityDefinitionPin, ...],
    course_pins: tuple[CapabilityDefinitionPin, ...],
) -> None:
    if set(target_pins) != set(course_pins):
        raise ValueError("canonical_definition_pin_mismatch")


def _target_projection(capability_refs: tuple[str, ...], release):
    role, gaps, need, role_pin, need_pin = target_fixtures._inputs()
    mappings = []
    facets = []
    for index, capability_ref in enumerate(capability_refs):
        source_pin = role_pin if index == 0 else need_pin
        scope = (
            MappingScope.CAPABILITY_FACET if index == 0 else MappingScope.DIRECT_CAPABILITY_CLAIM
        )
        evidence_text = "Explain decisions clearly." if index == 0 else "Improve communication."
        mapping, _ = target_fixtures._mapped(
            source_pin.source_ref, release, capability_ref, scope, evidence_text
        )
        mappings.append(mapping)
        facets.append(
            RequiredTargetFacet(facet_id=f"synthetic-target-facet:{index}", source_pin=source_pin)
        )
    projection = target_fixtures._project(
        role, gaps, need, facets, mappings=mappings, releases=[release]
    )
    return projection, tuple(mappings)


def _course_projection(
    *,
    course_ref: str,
    capability_refs: tuple[str, ...],
    release,
    source_type: CourseSourceType = CourseSourceType.EXTERNAL,
    profile_status: CourseProfileStatus = CourseProfileStatus.ACTIVE,
):
    namespace, separator, course_id = course_ref.partition(":")
    assert separator
    outcomes = []
    mappings = []
    course_capabilities = []
    for index, capability_ref in enumerate(capability_refs, start=1):
        source_ref = SourceSemanticRef(
            source_namespace=namespace,
            entity_kind=SourceSemanticKind.COURSE_LEARNING_OUTCOME,
            source_id=f"{course_id}#outcome-{index}",
            source_version="v1",
        )
        statement = f"Synthetic course outcome {index} for {capability_ref}."
        source_locator = f"source:{source_ref.source_id}"
        outcome = CourseLearningOutcome(
            outcome_ref=source_ref,
            course_ref=course_ref,
            statement=statement,
            source_locator=source_locator,
        )
        evidence = (
            SemanticEvidence(
                source_ref=source_ref,
                source_locator=source_locator,
                evidence_text=statement,
                evidence_kind=SemanticEvidenceKind.SOURCE_TEXT,
            ),
        )
        mapping, _ = target_fixtures._mapped(
            source_ref,
            release,
            capability_ref,
            MappingScope.OUTCOME_CAPABILITY_FACET,
            statement,
        )
        outcomes.append(
            GovernedOutcomeMappingInput(outcome=outcome, evidence=evidence, mapping=mapping)
        )
        mappings.append(mapping)
        course_capabilities.append(
            CourseCapability(
                capability_ref=capability_ref,
                coverage_type=CoverageType.DIRECT,
                target_level=None,
                provenance=[
                    CourseProvenance(
                        kind="governed_outcome",
                        source_ref=source_ref.source_id,
                        source_locator=source_locator,
                        evidence_text=statement,
                        method="synthetic_3d6_fixture",
                    )
                ],
            )
        )

    profile = CourseCapabilityProfile(
        id=f"profile:{course_ref}",
        version=1,
        course_ref=course_ref,
        source_type=source_type,
        source_system="frappe_lms" if source_type is CourseSourceType.INTERNAL else namespace,
        provider_ref=None if source_type is CourseSourceType.INTERNAL else namespace,
        provider_course_id=None if source_type is CourseSourceType.INTERNAL else course_id,
        title_snapshot=f"Synthetic course {course_ref}",
        capabilities=course_capabilities,
        status=profile_status,
        availability=CourseAvailability.AVAILABLE,
        provenance=[
            CourseProvenance(
                kind="synthetic_course_source", source_ref=course_ref, method="test_fixture"
            )
        ],
    )
    projection = project_governed_course_capabilities(
        profile, outcomes=tuple(outcomes), active_release_context=(release,)
    )
    return profile, projection, tuple(mappings), tuple(outcomes)


def test_real_3d4_and_3d5_outputs_join_in_unchanged_01b_engine() -> None:
    role, gaps, need, role_pin, _ = target_fixtures._inputs()
    release = target_fixtures._active_release()
    target_mapping, _ = target_fixtures._mapped(
        role_pin.source_ref,
        release,
        CAPABILITY_COMMUNICATION,
        MappingScope.CAPABILITY_FACET,
        "Explain decisions clearly.",
    )
    target_projection = target_fixtures._project(
        role,
        gaps,
        need,
        [RequiredTargetFacet(facet_id="role:communication", source_pin=role_pin)],
        mappings=[target_mapping],
        releases=[release],
    )

    course_ref = "skillscommons:course-e2e"
    outcome_ref = SourceSemanticRef(
        source_namespace="skillscommons",
        entity_kind=SourceSemanticKind.COURSE_LEARNING_OUTCOME,
        source_id="course-e2e#outcome-1",
        source_version="v1",
    )
    outcome = CourseLearningOutcome(
        outcome_ref=outcome_ref,
        course_ref=course_ref,
        statement="Explain decisions clearly.",
        source_locator="source:course-e2e#outcome-1",
    )
    evidence = (
        SemanticEvidence(
            source_ref=outcome_ref,
            source_locator="source:course-e2e#outcome-1",
            evidence_text="Explain decisions clearly.",
            evidence_kind=SemanticEvidenceKind.SOURCE_TEXT,
        ),
    )
    course_mapping, _ = target_fixtures._mapped(
        outcome_ref,
        release,
        CAPABILITY_COMMUNICATION,
        MappingScope.OUTCOME_CAPABILITY_FACET,
        "Explain decisions clearly.",
    )
    profile = CourseCapabilityProfile(
        id="profile:skillscommons:course-e2e",
        version=1,
        course_ref=course_ref,
        source_type=CourseSourceType.EXTERNAL,
        source_system="skillscommons",
        provider_ref="skillscommons",
        provider_course_id="course-e2e",
        title_snapshot="Synthetic communication course",
        capabilities=[
            CourseCapability(
                capability_ref=CAPABILITY_COMMUNICATION,
                coverage_type=CoverageType.DIRECT,
                target_level=None,
                provenance=[
                    CourseProvenance(
                        kind="governed_outcome",
                        source_ref=outcome_ref.source_id,
                        source_locator=outcome.source_locator,
                        method="synthetic_3d6_fixture",
                    )
                ],
            )
        ],
        target_level=None,
        status=CourseProfileStatus.ACTIVE,
        availability=CourseAvailability.AVAILABLE,
        provenance=[
            CourseProvenance(
                kind="provider",
                source_ref=course_ref,
                method="synthetic_3d6_fixture",
            )
        ],
    )
    course_projection = project_governed_course_capabilities(
        profile,
        outcomes=(
            GovernedOutcomeMappingInput(
                outcome=outcome,
                evidence=evidence,
                mapping=course_mapping,
            ),
        ),
        active_release_context=(release,),
    )

    assert target_projection.recommendation_target.target_capability_refs == [
        CAPABILITY_COMMUNICATION
    ]
    assert course_projection.normalized_candidate is not None
    assert (
        course_projection.coverage[0].sources[0].definition_pin in target_projection.definition_pins
    )
    target_refs = set(target_projection.recommendation_target.target_capability_refs)
    candidate_refs = {
        item.capability_ref for item in course_projection.normalized_candidate.capabilities
    }
    assert target_refs & candidate_refs == {CAPABILITY_COMMUNICATION}

    result = CourseRecommendationEngine().recommend(
        CourseRecommendationRequest(
            recommendation_target=target_projection.recommendation_target,
            candidates=[
                CourseRecommendationCandidate(
                    course=course_projection.normalized_candidate,
                    profile_status=profile.status,
                )
            ],
        )
    )

    assert [item.course_ref for item in result.recommendations] == [course_ref]
    assert result.recommendations[0].matched_target_capability_refs == [CAPABILITY_COMMUNICATION]
    assert result.provenance.role_requirement_refs == ["req-1"]
    assert result.provenance.learning_need_ref == "need-record-1"
    assert result.provenance.gap_refs == ["gap-1"]
    assert result.provenance.learning_path_ref == "path:1"
    assert result.provenance.path_step_ref == "step:2"
    assert target_projection.role_requirement.id == "req-1"
    assert target_projection.learning_need.id == "need-record-1"
    assert (
        target_projection.mapping_provenance[0].mapping_fingerprint
        == target_mapping.mapping_fingerprint
    )
    assert course_projection.coverage[0].sources[0].source_ref == outcome_ref
    assert (
        course_projection.coverage[0].sources[0].mapping_fingerprint
        == course_mapping.mapping_fingerprint
    )
    assert course_projection.normalized_candidate.target_level is None
    assert course_projection.normalized_candidate.prerequisites == []


def test_multi_capability_projection_is_exact_ranked_and_order_independent() -> None:
    capabilities = (CAPABILITY_COMMUNICATION, CAPABILITY_WRITING)
    release = target_fixtures._active_release()
    target_projection, _ = _target_projection(capabilities, release)
    full_profile, full_projection, _, _ = _course_projection(
        course_ref="skillscommons:course-full",
        capability_refs=capabilities,
        release=release,
    )
    partial_profile, partial_projection, _, _ = _course_projection(
        course_ref="frappe_lms:course-partial",
        capability_refs=(CAPABILITY_COMMUNICATION,),
        release=release,
        source_type=CourseSourceType.INTERNAL,
    )
    assert full_projection.normalized_candidate is not None
    assert partial_projection.normalized_candidate is not None
    candidates = [
        CourseRecommendationCandidate(
            course=full_projection.normalized_candidate, profile_status=full_profile.status
        ),
        CourseRecommendationCandidate(
            course=partial_projection.normalized_candidate, profile_status=partial_profile.status
        ),
    ]

    engine = CourseRecommendationEngine()
    first = engine.recommend(
        CourseRecommendationRequest(
            recommendation_target=target_projection.recommendation_target,
            candidates=candidates,
        )
    )
    reversed_result = engine.recommend(
        CourseRecommendationRequest(
            recommendation_target=target_projection.recommendation_target,
            candidates=list(reversed(candidates)),
        )
    )

    assert first.model_dump(mode="json") == reversed_result.model_dump(mode="json")
    assert [item.course_ref for item in first.recommendations] == [
        "skillscommons:course-full",
        "frappe_lms:course-partial",
    ]
    assert first.recommendations[0].coverage_status.value == "FULL_COVERAGE"
    assert first.recommendations[1].coverage_status.value == "PARTIAL_COVERAGE"
    assert first.recommendations[1].missing_target_capability_refs == [CAPABILITY_WRITING]
    assert target_projection.definition_pins == tuple(
        coverage.sources[0].definition_pin for coverage in full_projection.coverage
    )


def test_no_intersection_returns_no_suitable_course_without_fallback() -> None:
    release = target_fixtures._active_release()
    target_projection, _ = _target_projection((CAPABILITY_COMMUNICATION,), release)
    profile, course_projection, _, _ = _course_projection(
        course_ref="skillscommons:course-no-match",
        capability_refs=(CAPABILITY_WRITING,),
        release=release,
    )
    assert course_projection.normalized_candidate is not None

    result = CourseRecommendationEngine().recommend(
        CourseRecommendationRequest(
            recommendation_target=target_projection.recommendation_target,
            candidates=[
                CourseRecommendationCandidate(
                    course=course_projection.normalized_candidate,
                    profile_status=profile.status,
                )
            ],
        )
    )

    assert result.recommendations == []
    assert result.no_suitable_reason == "NO_SUITABLE_COURSE"
    assert result.rejected_summary["NO_CAPABILITY_MATCH"] == 1


def test_stale_target_mapping_is_rejected_before_engine_call() -> None:
    role, gaps, need, role_pin, _ = target_fixtures._inputs()
    release = target_fixtures._active_release()
    stale_mapping, _ = target_fixtures._mapped(
        role_pin.source_ref,
        release,
        CAPABILITY_COMMUNICATION,
        MappingScope.CAPABILITY_FACET,
        "stale source wording",
    )

    with pytest.raises(MappingGovernanceError, match="stale_source"):
        target_fixtures._project(
            role,
            gaps,
            need,
            [RequiredTargetFacet(facet_id="role:communication", source_pin=role_pin)],
            mappings=[stale_mapping],
            releases=[release],
        )


def test_stale_course_evidence_is_rejected_before_candidate_reaches_engine() -> None:
    release = target_fixtures._active_release()
    _, _, _, outcomes = _course_projection(
        course_ref="skillscommons:course-stale",
        capability_refs=(CAPABILITY_COMMUNICATION,),
        release=release,
    )
    original = outcomes[0]
    changed_evidence = (
        SemanticEvidence(
            source_ref=original.outcome.outcome_ref,
            source_locator=original.evidence[0].source_locator,
            evidence_text="Changed after mapping approval.",
            evidence_kind=original.evidence[0].evidence_kind,
        ),
    )
    stale_input = original.model_copy(update={"evidence": changed_evidence})
    profile, _, _, _ = _course_projection(
        course_ref="skillscommons:course-stale",
        capability_refs=(CAPABILITY_COMMUNICATION,),
        release=release,
    )

    with pytest.raises(MappingGovernanceError, match="stale_source"):
        project_governed_course_capabilities(
            profile, outcomes=(stale_input,), active_release_context=(release,)
        )


def test_draft_profile_remains_ineligible_after_governed_projection() -> None:
    release = target_fixtures._active_release()
    target_projection, _ = _target_projection((CAPABILITY_COMMUNICATION,), release)
    profile, course_projection, _, _ = _course_projection(
        course_ref="skillscommons:course-draft",
        capability_refs=(CAPABILITY_COMMUNICATION,),
        release=release,
        profile_status=CourseProfileStatus.DRAFT,
    )
    assert course_projection.profile_candidate is not None
    assert course_projection.profile_candidate.status is CourseProfileStatus.DRAFT
    candidate = candidate_from_profile(course_projection.profile_candidate)

    result = CourseRecommendationEngine().recommend(
        CourseRecommendationRequest(
            recommendation_target=target_projection.recommendation_target,
            candidates=[candidate],
        )
    )

    assert result.recommendations == []
    assert result.rejected_summary["PROFILE_NOT_ACTIVE"] == 1


def test_internal_and_external_candidates_have_equal_semantic_treatment() -> None:
    release = target_fixtures._active_release()
    target, _ = _target_projection((CAPABILITY_COMMUNICATION,), release)
    _, internal, _, _ = _course_projection(
        course_ref="frappe_lms:course-parity",
        capability_refs=(CAPABILITY_COMMUNICATION,),
        release=release,
        source_type=CourseSourceType.INTERNAL,
    )
    _, external, _, _ = _course_projection(
        course_ref="skillscommons:course-parity",
        capability_refs=(CAPABILITY_COMMUNICATION,),
        release=release,
        source_type=CourseSourceType.EXTERNAL,
    )
    assert internal.normalized_candidate is not None
    assert external.normalized_candidate is not None
    engine = CourseRecommendationEngine()
    internal_result = engine.recommend(
        CourseRecommendationRequest(
            recommendation_target=target.recommendation_target,
            candidates=[
                CourseRecommendationCandidate(
                    course=internal.normalized_candidate,
                    profile_status=CourseProfileStatus.ACTIVE,
                )
            ],
        )
    )
    external_result = engine.recommend(
        CourseRecommendationRequest(
            recommendation_target=target.recommendation_target,
            candidates=[
                CourseRecommendationCandidate(
                    course=external.normalized_candidate,
                    profile_status=CourseProfileStatus.ACTIVE,
                )
            ],
        )
    )

    assert internal_result.recommendations[0].rank == external_result.recommendations[0].rank == 1
    assert (
        internal_result.recommendations[0].decision_details
        == external_result.recommendations[0].decision_details
    )
    assert (
        internal_result.recommendations[0].matched_target_capability_refs
        == external_result.recommendations[0].matched_target_capability_refs
    )


@pytest.mark.parametrize(
    "capability_ref",
    (
        "capability:domain_software:software_testing",
        "capability:domain_sales:consultative_selling",
        "capability:domain_finance:accounting_controls",
        "capability:domain_hr:workplace_communication",
    ),
)
def test_cross_domain_target_and_course_join_is_domain_neutral(capability_ref: str) -> None:
    release = _active_domain_release(capability_ref)
    target, _ = _target_projection((capability_ref,), release)
    profile, course, _, _ = _course_projection(
        course_ref="frappe_lms:course-domain-neutral",
        capability_refs=(capability_ref,),
        release=release,
        source_type=CourseSourceType.INTERNAL,
    )
    assert course.normalized_candidate is not None
    _require_exact_pin_compatibility(
        target.definition_pins,
        tuple(source.definition_pin for coverage in course.coverage for source in coverage.sources),
    )

    result = CourseRecommendationEngine().recommend(
        CourseRecommendationRequest(
            recommendation_target=target.recommendation_target,
            candidates=[
                CourseRecommendationCandidate(
                    course=course.normalized_candidate, profile_status=profile.status
                )
            ],
        )
    )

    assert [item.course_ref for item in result.recommendations] == [profile.course_ref]
    assert result.recommendations[0].matched_target_capability_refs == [capability_ref]


def test_incompatible_exact_definition_pins_are_rejected_by_dry_run_gate() -> None:
    capability_ref = "capability:domain_software:software_testing"
    target_release = _active_domain_release(capability_ref, version="1.0")
    course_release = _active_domain_release(
        capability_ref,
        version="2.0",
        description="A different exact definition for the same stable ref.",
    )
    target, _ = _target_projection((capability_ref,), target_release)
    profile, course, _, _ = _course_projection(
        course_ref="skillscommons:course-pin-conflict",
        capability_refs=(capability_ref,),
        release=course_release,
    )
    assert course.normalized_candidate is not None
    course_pins = tuple(
        source.definition_pin for coverage in course.coverage for source in coverage.sources
    )

    assert target.recommendation_target.target_capability_refs == [capability_ref]
    assert target.definition_pins != course_pins
    with pytest.raises(ValueError, match="canonical_definition_pin_mismatch"):
        _require_exact_pin_compatibility(target.definition_pins, course_pins)


def test_historical_mapping_replays_exact_pins_but_is_not_current_use() -> None:
    release = target_fixtures._active_release()
    _, _, mappings, outcomes = _course_projection(
        course_ref="skillscommons:course-history",
        capability_refs=(CAPABILITY_COMMUNICATION,),
        release=release,
    )
    mapping = deprecate_governed_mapping(
        mappings[0], actor_ref="actor:governance", reason="Historical fixture only."
    )

    historical = resolve_governed_mapping_historical(
        mapping,
        historical_source_pin=mapping.source_pin,
        release_context=(release,),
    )

    assert historical.resolution_mode is BindingResolutionMode.HISTORICAL
    assert historical.source_ref == outcomes[0].outcome.outcome_ref
    assert historical.target_definition_pin == mapping.target_definition_pin
    with pytest.raises(MappingGovernanceError, match="mapping_deprecated"):
        project_governed_course_capabilities(
            profile=_course_projection(
                course_ref="skillscommons:course-history",
                capability_refs=(CAPABILITY_COMMUNICATION,),
                release=release,
            )[0],
            outcomes=(outcomes[0].model_copy(update={"mapping": mapping}),),
            active_release_context=(release,),
        )


def test_repeated_end_to_end_fixture_is_byte_equivalent() -> None:
    def snapshot() -> dict[str, object]:
        release = target_fixtures._active_release()
        target, target_mappings = _target_projection((CAPABILITY_COMMUNICATION,), release)
        profile, course, course_mappings, _ = _course_projection(
            course_ref="skillscommons:course-repeatable",
            capability_refs=(CAPABILITY_COMMUNICATION,),
            release=release,
        )
        assert course.normalized_candidate is not None
        result = CourseRecommendationEngine().recommend(
            CourseRecommendationRequest(
                recommendation_target=target.recommendation_target,
                candidates=[
                    CourseRecommendationCandidate(
                        course=course.normalized_candidate, profile_status=profile.status
                    )
                ],
            )
        )
        return {
            "target": target.model_dump(mode="json"),
            "course": course.normalized_candidate.model_dump(mode="json"),
            "recommendation": result.model_dump(mode="json"),
            "target_mapping_fingerprint": target_mappings[0].mapping_fingerprint,
            "course_mapping_fingerprint": course_mappings[0].mapping_fingerprint,
        }

    assert snapshot() == snapshot()
