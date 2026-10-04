# COURSE-REC-01A.3D-5A — Direct Claim Identity Hardening

## Status and scope

Implemented the bounded identity hardening for direct course capability claims.
This is a source-identity representation change in the Core-AI projection
adapter only. It does not migrate or reinterpret historical mappings, change
generic identity contracts, or add persistence, APIs, UI, or recommendation
behavior. LMS and COURSE-REC-01B remain untouched.

The next compatibility action is **READY_TO_RERUN_3D_6**. The 3D-6 migration,
compatibility, and end-to-end dry run were not run as part of this task.

## Identity contract

`make_direct_claim_source_id(course_ref=..., claim_id=...)` serializes the
structured pair using canonical JSON (`sort_keys=True`, compact separators,
UTF-8, `ensure_ascii=False`) and returns `dc1_` followed by the lowercase
SHA-256 hex digest. The resulting source ID is always 68 characters. Inputs
are preserved exactly; blank-only values are rejected, but no trimming or
Unicode normalization is performed. No decoder, delimiter-composite format,
or generic identity limit was added.

`DirectCourseCapabilityClaim` now carries `course_ref`, `claim_id`, and
`source_ref`. The model verifies the `COURSE_DIRECT_CLAIM` kind, course
namespace, and exact recomputed source ID. Projection independently checks the
claim's exact `course_ref` against `CourseCapabilityProfile.course_ref` and
revalidates its hash identity. Ownership is never inferred by prefix-matching
the opaque source ID. Direct claims still do not fabricate a learning outcome.

Legacy delimiter-based IDs are rejected as current direct-claim input. No
legacy mapping is rewritten or granted authority. Course-learning-outcome
identity behavior remains unchanged.

The reported old collision was reproduced against the prior validator:
`("skillscommons:course-A#segment", "claim-B")` and
`("skillscommons:course-A", "segment#claim-B")` both reduced to the legacy
ID `course-A#segment#claim-B`. The new exact-pair regression asserts distinct
hash IDs.

## Verification

Focused direct-claim, governed projection, identity, mapping, resolution,
definition, release lifecycle, and target-adapter regression tests passed: 248
tests. Catalog, provider, and COURSE-REC-01B regression tests passed: 87
additional tests without live network. Ruff and mypy passed for the changed production/test scope. The new
identity tests cover deterministic fixed-length IDs, the exact blocker pair,
separator-boundary pairs, special characters, Unicode and exact-value
preservation, blank rejection, and long input parts. Projection tests cover
external and internal direct claims, wrong-course rejection, namespace/kind
validation, legacy delimiter rejection, changed source pins and mapping
rejection, and no synthetic outcome.

This verification does not claim a 3D-6 dry run, provider integration run,
database migration, or full repository test suite.

## Changed files

- `services/pai-backend/backend/app/capability_governance/direct_claim_identity.py`
- `services/pai-backend/backend/app/capability_governance/course_projection.py`
- `services/pai-backend/backend/tests/test_direct_claim_identity.py`
- `services/pai-backend/backend/tests/test_governed_course_projection.py`
- `test/results/course-rec-01a-3d-5a/` evidence artifacts

No commit or push was performed.
