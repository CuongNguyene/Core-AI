# COURSE-REC-01A.3D-5 — Governed Course Projection Adapter

## Purpose and boundary

`app.capability_governance.course_projection` is a pure, provider-neutral adapter
from source-owned course outcomes or direct course claims to canonical course
capability coverage. It consumes mappings; it does not create proposals,
reviews, activations, persistence, APIs, or recommendation decisions. LMS and
COURSE-REC-01B are unchanged.

The input `CourseCapabilityProfile.course_ref` is authoritative for course
identity. An outcome must carry the same explicit `course_ref`. Direct claims
have no synthetic outcome: their source ref must use the course namespace and
`<course-id>#<claim-id>` identity convention, and the claim also carries the
explicit course ref. A mismatch fails closed.

## Current governed mapping

Every supplied mapping is checked against source kind/scope and a freshly built
`SourceSemanticPin`, then passed to
`resolve_governed_mapping_for_use(...)`. The resolver verifies current mapping
authority, source freshness, exact target-definition pin, active definition and
dependency closure. Historical resolution is never used. The resulting
`GovernedCourseMappingTrace` keeps source identity/pin, mapping id/fingerprint,
scope, exact `CapabilityDefinitionPin`, and current-use mode.

The adapter does not infer from title, topic, provider metadata, course
difficulty, or duration. An unmapped semantic creates a warning and no
canonical coverage. Conflicts are delegated to the 3D-3B resolver and fail
closed. Duplicate canonical refs produce one coverage/profile claim while
retaining distinct source traces and evidence provenance.

## Profile and candidate lifecycle

The existing `CourseCapabilityProfile`, `CourseCapability`, and
`NormalizedCourseCandidate` schemas are unchanged. Projected claims use the
existing `DIRECT` coverage value because the input is an explicitly governed
course outcome/direct claim; target level is left null on each generated claim.
Existing profile-level target level, prerequisites, availability, duration,
language, provider facts, title, and provenance are preserved.

For a DRAFT profile, a DRAFT profile candidate is returned only if its existing
capability refs exactly match the current projection. This avoids silently
replacing legacy or experimental refs. No profile is auto-activated. For an
ACTIVE profile, an existing `NormalizedCourseCandidate` is returned only when
its existing capability refs exactly match current governed coverage; the
active profile itself is not rewritten. DEPRECATED profiles never produce a
candidate. An empty/unmapped projection does not fabricate a profile or
candidate.

The 01B engine still owns ACTIVE-profile eligibility, availability,
prerequisite, and exact-intersection gates. Governance metadata remains in the
adapter sidecar and is not added to ranking inputs.

## Provider and parallel-work boundaries

The projection code branches only on the approved course semantic source kind
and mapping scope; it contains no SkillsCommons/Open edX-specific path. Internal
Frappe LMS and external provider course identities use the same adapter
contract. No package parsing is performed.

No `target_adapter.py`, RoleRequirement, LearningNeedProfile,
RecommendationTarget, 3D-1/2/3A/3B, COURSE-REC-01B, or LMS code is changed. Any
concurrent 3D-4 work remains separately owned.

## Explicit non-goals

- No semantic mapping creation, fuzzy matching, taxonomy lookup, or auto-repin.
- No target level, prerequisite, mastery, or recommendation inference.
- No schema migration, persistence, API, UI, or profile activation.
- No migration of opaque legacy refs or activation of experimental drafts.
- No changes to provider facts, recommendation ranking, LMS, or Core-AI APIs.
