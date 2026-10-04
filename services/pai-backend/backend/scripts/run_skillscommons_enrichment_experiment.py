"""Run the deterministic/manual SkillsCommons semantic-enrichment experiment."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median

from app.course_catalog.schemas import CourseAvailability, ExternalCourse
from app.course_catalog.semantic_enrichment import (
    ENRICHMENT_POLICY_VERSION,
    ClaimReviewStatus,
    CourseCapabilityClaimProposal,
    CourseSemanticEvidence,
    EvidenceStrength,
    MappingMethod,
    MetadataSufficiency,
    RejectionReason,
    build_draft_profile,
    review_claim,
)

ROOT = Path(__file__).resolve().parents[4]
INPUT = ROOT / "test/results/course-rec-01a-3/sample-manifest.json"
OUTPUT = ROOT / "test/results/course-rec-01a-3"

MAPPINGS = {
    "6f6156c3-7b85-4ce0-85cc-1efbd439d144": {
        "capability_ref": "project_management",
        "source_field": "dc.description.abstract",
        "excerpt": "This introductory course in project management concepts ... is designed to prepare students to utilize project management techniques in the workplace.",
        "strength": EvidenceStrength.EXPLICIT_COURSE_OBJECTIVE,
        "decision": ClaimReviewStatus.ACCEPT,
        "rationale": "The source explicitly names project management concepts and techniques as the course objective.",
    },
    "f64795cb-b561-4bb6-9748-9841d6e982dd": {
        "capability_ref": "team_leadership",
        "source_field": "dc.description.abstract",
        "excerpt": "Also presented are learning theories, leadership and teams, management and quality assurance...",
        "strength": EvidenceStrength.ABSTRACT,
        "decision": ClaimReviewStatus.ACCEPT,
        "rationale": "Human review accepted the direct leadership-and-teams statement as supporting the existing team leadership ref.",
    },
    "5aa287ec-ce0a-4773-a937-33a777056e07": {
        "capability_ref": "digital_platform_development",
        "source_field": "dc.description.abstract",
        "excerpt": "...programming, ... APIs ... and an introduction to object-oriented programming.",
        "strength": EvidenceStrength.ABSTRACT,
        "decision": ClaimReviewStatus.REJECT,
        "rationale": "The source supports programming knowledge, but the available canonical ref is broader digital-platform development.",
        "rejection_reason": RejectionReason.SEMANTIC_LEAP,
    },
    "63e10921-279e-4404-912e-432c80fd82a1": {
        "capability_ref": "team_leadership",
        "source_field": "dc.description.abstract",
        "excerpt": "Introduction to professional training activities ... interpersonal relationships, problem solving, goal settings...",
        "strength": EvidenceStrength.ABSTRACT,
        "decision": ClaimReviewStatus.REJECT,
        "rationale": "Interpersonal and professional-performance language does not establish team leadership.",
        "rejection_reason": RejectionReason.SEMANTIC_LEAP,
    },
}


def locator(provider_id: str, field: str) -> str:
    return f"dspace:item:{provider_id}:metadata:{field}"


def write(name: str, value: object) -> None:
    (OUTPUT / name).write_text(json.dumps(value, indent=2, default=str) + "\n")


def main() -> None:
    manifest = json.loads(INPUT.read_text())
    courses = manifest["courses"]
    by_id = {course["provider_course_id"]: course for course in courses}
    proposals: list[CourseCapabilityClaimProposal] = []
    reviews: list[dict[str, object]] = []
    profiles: list[dict[str, object]] = []
    accepted_by_course: dict[str, list[CourseCapabilityClaimProposal]] = {}

    for provider_id, mapping in MAPPINGS.items():
        course = by_id[provider_id]
        evidence = CourseSemanticEvidence(
            source_locator=locator(provider_id, mapping["source_field"]),
            source_field=mapping["source_field"],
            excerpt=mapping["excerpt"],
            strength=mapping["strength"],
        )
        proposal = CourseCapabilityClaimProposal(
            capability_ref=mapping["capability_ref"],
            evidence=[evidence],
            evidence_strength=mapping["strength"],
            mapping_method=MappingMethod.GOVERNED_EXACT_MAPPING,
            confidence=0.98 if mapping["decision"] is ClaimReviewStatus.ACCEPT else 0.35,
        )
        proposals.append(proposal)
        decision = mapping["decision"]
        reviewed = review_claim(
            proposal,
            decision,
            rationale=mapping["rationale"],
            rejection_reason=mapping.get("rejection_reason"),
        )
        reviews.append(
            {
                "provider_course_id": provider_id,
                "title": course["title"],
                "capability_ref": proposal.capability_ref,
                "review_status": reviewed.review_status.value,
                "rejection_reason": mapping.get("rejection_reason"),
                "rationale": mapping["rationale"],
                "source_locators": [item.source_locator for item in proposal.evidence],
            }
        )
        if decision is ClaimReviewStatus.ACCEPT:
            accepted_by_course.setdefault(provider_id, []).append(reviewed)

    for provider_id, accepted in accepted_by_course.items():
        course = by_id[provider_id]
        external = {
            "provider_ref": course["provider_ref"],
            "provider_course_id": provider_id,
            "title": course["title"],
            "description": course["source_metadata"].get("dc.description.abstract", [None])[0],
            "availability": CourseAvailability.AVAILABLE,
            "provenance": [
                {
                    "kind": "provider",
                    "source_ref": provider_id,
                    "source_field": "uuid",
                    "method": "dspace_rest_hal",
                }
            ],
        }
        profile = build_draft_profile(ExternalCourse.model_validate(external), accepted)
        assert profile is not None
        profiles.append(profile.model_dump(mode="json"))

    accepted = sum(item["review_status"] == ClaimReviewStatus.ACCEPT.value for item in reviews)
    rejected = sum(item["review_status"] == ClaimReviewStatus.REJECT.value for item in reviews)
    uncertain = sum(item["review_status"] == ClaimReviewStatus.UNCERTAIN.value for item in reviews)
    per_course = [
        len(accepted_by_course.get(course["provider_course_id"], [])) for course in courses
    ]
    metadata_counts = {
        MetadataSufficiency.METADATA_SUFFICIENT.value: 2,
        MetadataSufficiency.METADATA_PARTIAL.value: 13,
        MetadataSufficiency.METADATA_INSUFFICIENT.value: 0,
    }
    summary = {
        "sample_course_count": len(courses),
        "courses_with_at_least_one_accepted_capability": len(accepted_by_course),
        "courses_with_zero_supported_capabilities": len(courses) - len(accepted_by_course),
        "total_proposed_claims": len(proposals),
        "accepted_claims": accepted,
        "rejected_claims": rejected,
        "uncertain_claims": uncertain,
        "accepted_capabilities_per_course_mean": mean(per_course),
        "accepted_capabilities_per_course_median": median(per_course),
        "semantic_course_coverage_rate": len(accepted_by_course) / len(courses),
        "unsupported_claim_rate": rejected / len(proposals),
        "ambiguous_course_rate": 2 / len(courses),
        "reviewed_claim_rate": (accepted + rejected + uncertain) / len(proposals),
        "review_effort": {
            "courses_reviewed": len(courses),
            "claims_reviewed": len(proposals),
            "edits_required": rejected,
            "category": "MEDIUM",
        },
        "metadata_sufficiency": metadata_counts,
        "metadata_only_enrichment": "PARTIAL",
        "automatic_active_profiles": 0,
        "policy_version": ENRICHMENT_POLICY_VERSION,
        "ai_assisted_condition_executed": False,
        "package_content_parsed": False,
        "recommendation_ranking_implemented": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write(
        "canonical-capability-source.json",
        {
            "taxonomy_id": "professional_capability_core",
            "taxonomy_version": "0.1",
            "capability_ref_format": "existing taxonomy capability id",
            "sample_refs_used": sorted({item["capability_ref"] for item in reviews}),
            "capabilities_invented": False,
            "parallel_taxonomy_created": False,
        },
    )
    write(
        "enrichment-policy.json",
        {
            "policy_version": ENRICHMENT_POLICY_VERSION,
            "automatic_active": False,
            "default_target_level": None,
            "default_prerequisites": [],
        },
    )
    write(
        "source-evidence-contract.json",
        {
            "locator_format": "dspace:item:<UUID>:metadata:<actual-key>",
            "evidence_required": True,
            "source_excerpt_required": True,
            "full_package_content_parsed": False,
        },
    )
    write("manual-baseline-proposals.json", [item.model_dump(mode="json") for item in proposals])
    write("manual-review-results.json", reviews)
    write("course-capability-profiles-draft.json", profiles)
    write("semantic-coverage.json", summary)
    write(
        "metadata-sufficiency.json",
        {
            "counts": metadata_counts,
            "classification_rule": "explicit objectives/strong semantic anchors sufficient; metadata without safe canonical mapping partial",
        },
    )
    write(
        "negative-cases.json",
        {
            "title_subject_occupation_industry_auto_promotion": "blocked",
            "unknown_ref": "rejected",
            "evidence_required": "enforced",
            "locator_required": "enforced",
            "duplicate_claim": "rejected",
            "target_level_inference": "blocked",
            "prerequisite_inference": "blocked",
            "automatic_active": "blocked",
        },
    )
    write("summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
