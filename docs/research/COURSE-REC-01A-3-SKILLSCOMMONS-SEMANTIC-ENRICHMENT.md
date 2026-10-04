# COURSE-REC-01A.3 — SkillsCommons Semantic Enrichment Experiment

## Scope

This experiment evaluates whether verified SkillsCommons ExternalCourse records can be transformed into traceable, governed CourseCapabilityProfile drafts. It does not implement recommendation ranking, persistence, API/UI, LMS changes, package extraction, AI inference, or automatic activation.

## 1. Repository

Core-AI path: /Users/mac/Developers/work/LMS/Core-AI
Branch: feat/deterministic-ai-course-planning-workspace
HEAD: a078526ab7ea38327fdeece142aba325f3de3352
Working tree: Existing COURSE-REC-01A work plus this experiment.
Pre-existing changes: Preserved.

LMS path: /Users/mac/Developers/work/LMS/lms
Branch: dev
HEAD: 289174af73ad648a2e42c7d55a2273d815790235
Working tree: Clean and unchanged.

## 2. Experiment Goal

Question tested: can real verified SkillsCommons courses produce trustworthy, reviewable semantic profile drafts without treating provider metadata as semantic truth?

Sample size: 15 strict provider candidates.

Sampling method: deterministic stratified selection from the 27 strict 01A.2C package candidates, covering business/accounting, healthcare, technical, workforce, general, and ambiguous cases. No new course identity was created.

Live provider data used: YES

## 3. Canonical Capability Source

Source: app/extraction/capability_taxonomy.py

Taxonomy: professional_capability_core@0.1

Capability identity format: existing taxonomy capability IDs, including project_management, team_leadership, and digital_platform_development.

Capabilities invented: NO
Parallel taxonomy created: NO

## 4. SkillsCommons Sample

Courses sampled: 15

Domains/categories observed:

- business/accounting
- business/project-management
- healthcare
- healthcare/nutrition
- healthcare/physical-therapy
- healthcare/patient-care
- healthcare/pharmacy
- healthcare/pain-management
- healthcare/medical-coding
- technical/hardware
- technical/programming
- technical/operating-systems
- workforce/professional-performance
- general/ambiguous

Strict provider candidates only: YES

Provider IDs preserved: YES

## 5. Source Evidence

Metadata fields used:

dc.title, dc.description.abstract, dc.subject, taaccct.occupation, taaccct.industry, taaccct.credentialType, taaccct.deliveryFormat, dc.publisher, taaccct.projectName, dc.language, dc.type, lastModified, handle.

Bundle/bitstream metadata used: bundle names and bitstream names/types were retained as source context. No full package content was parsed.

Full package content parsed: NO

Source evidence classes:

EXPLICIT_COURSE_OBJECTIVE, ABSTRACT, TITLE, STRUCTURED_SUBJECT_METADATA, OCCUPATION_METADATA, INDUSTRY_METADATA, OTHER.

## 6. Semantic Boundary

Subject mapped directly to capability: NO

Occupation mapped directly to capability: NO

Industry mapped directly to capability: NO

Title keyword auto-promoted: NO

Description keyword auto-promoted: NO

These fields are evidence only. They do not independently define canonical semantic identity.

## 7. Enrichment Claim Contract

Model/class: CourseCapabilityClaimProposal

Fields:

- capability_ref
- evidence[]
- evidence_strength
- mapping_method
- review_status
- optional confidence and rationale

Canonical capability ref required: YES

Evidence required: YES

Source locator required: YES

Review status required: YES

Source locators use:

    dspace:item:<UUID>:metadata:<actual-key>

## 8. Enrichment Methods

Manual/governed baseline: YES

Exact mapping registry: YES, experiment-scoped and versioned

AI-assisted proposal: NO

Automatic ACTIVE profile: NO

## 9. Review

Review outcomes:

- ACCEPT: 2
- REJECT: 2
- UNCERTAIN: 0

Reviewer model: SINGLE_REVIEWER_REFERENCE

This is a bounded engineering reference, not objective ground truth.

## 10. Semantic Coverage

Sample courses: 15

Courses with >=1 accepted capability: 2

Courses with zero accepted capabilities: 13

Semantic course coverage rate: 2/15 = 13.33%

Accepted capabilities per course mean: 0.1333

Accepted capabilities per course median: 0

## 11. Claim Quality

Total proposed claims: 4

Accepted: 2
Rejected: 2
Uncertain: 0

Unsupported claim rate: 2/4 = 50%

Ambiguous course rate: 2/15 = 13.33%

Reviewed claim rate: 100%

The rejected claims attempted to map programming or professional-performance language to broader canonical capabilities and were rejected as semantic leaps.

## 12. Metadata Sufficiency

METADATA_SUFFICIENT: 2

METADATA_PARTIAL: 13

METADATA_INSUFFICIENT: 0

Metadata-only enrichment adequate: PARTIAL

The metadata was generally sufficient to review and reject claims, but only two courses had a sufficiently direct match to the current canonical taxonomy.

## 13. Target Level

Mapped automatically: NO

Governed level mapping used: NO

Null retained when unsupported: YES

## 14. Prerequisites

Inferred from free text: NO

Structured compatible source found: NO

Default when unsupported: []

## 15. CourseCapabilityProfile

DRAFT profiles produced: 2

ACTIVE profiles produced: 0

Expected: 0 ACTIVE

Canonical schema changed: NO

Courses with no accepted claims produce a semantic coverage gap rather than a fabricated profile.

## 16. Example Accepted Course

Provider ID: 6f6156c3-7b85-4ce0-85cc-1efbd439d144

Handle: taaccct/2946

Title: MAN2582 Introduction to Project Management

Accepted capability refs: project_management

Evidence: the abstract explicitly names project management concepts and techniques as the course objective.

Source locator:

    dspace:item:6f6156c3-7b85-4ce0-85cc-1efbd439d144:metadata:dc.description.abstract

Target level: null

Prerequisites: []

Profile status: DRAFT

## 17. Example Ambiguous Course

Provider ID: 5aa287ec-ce0a-4773-a937-33a777056e07

Title: COP1510 Programming Concepts I

Candidate semantic claim: digital_platform_development

Review result: REJECT

Reason: the abstract supports programming concepts, APIs, debugging, and object-oriented programming, but the existing canonical ref is broader digital-platform development. Mapping would be a semantic leap.

## 18. Example Zero-Capability Course

Provider ID: f38740c4-657e-4c62-abe1-d9ce94eb30b0

Title: PRN0070 Basic Nutrition

Reason no capability was accepted: source evidence is meaningful, but the current canonical capability source has no governed nutrition capability ref.

Profile outcome: semantic coverage gap; no recommendation-ready profile.

## 19. AI-Assisted Experiment

Executed: NO

Reason: the mandatory deterministic/manual baseline was sufficient to answer the bounded experiment, and no new model/provider dependency was introduced.

No AI proposals, model provenance, prompt, or hidden reasoning were created.

## 20. Review Effort

Courses reviewed: 15

Claims reviewed: 4

Edit effort: MEDIUM

Notes: all sampled courses were inspected; four explicit proposals were reviewed, two accepted and two rejected. No timing instrumentation was added.

## 21. Identity / Provenance

Provider ref: skillscommons

Primary provider ID: DSpace UUID

Handle retained: YES

Source metadata locators retained: YES

Enrichment policy/version: skillscommons_course_semantic_enrichment@0.1

The profile preserves the original skillscommons:<UUID> identity and adds policy provenance. No new course identity is created.

## 22. Negative Semantic Cases

| Case | Result |
|---|---|
| Title auto-mapping blocked | PASS |
| Subject auto-mapping blocked | PASS |
| Occupation auto-mapping blocked | PASS |
| Industry auto-mapping blocked | PASS |
| Unknown capability ref rejected | PASS |
| Claim without evidence rejected | PASS |
| Target-level invention blocked | PASS |
| Prerequisite invention blocked | PASS |
| Automatic activation blocked | PASS |

## 23. Provider Regression

SkillsCommonsCourseProvider: PASS

OpenEdxCourseProvider: PASS

MockExternalProvider: PASS

## 24. Tests

Semantic enrichment tests:

    uv run pytest tests/test_course_catalog_semantic_enrichment.py -q
    20 passed

Course catalog/profile regression:

    uv run pytest tests/test_course_catalog_*.py -q
    pending final rerun after evidence generation

## 25. Static Checks

Ruff format: PASS

Ruff: PASS

mypy: PASS for app/course_catalog

JSON validation: PASS for experiment evidence

git diff --check: PASS

Secret scan: PASS

## 26. Files Changed

DOMAIN:

- services/pai-backend/backend/app/course_catalog/semantic_enrichment.py

SERVICE: none

POLICY/MAPPING: experiment-scoped policy and mapping artifacts under test/results/course-rec-01a-3/

TESTS:

- services/pai-backend/backend/tests/test_course_catalog_semantic_enrichment.py

FIXTURES: sanitized live sample manifest and JSON experiment artifacts

DOCS:

- this report

EVIDENCE: test/results/course-rec-01a-3/

PERSISTENCE: NONE

API: NONE

LMS: NONE

## 27. Experiment Conclusion

Can SkillsCommons metadata support governed semantic enrichment? PARTIAL

Can trustworthy CourseCapabilityProfile drafts be produced? YES

Can provider metadata be used without inventing capabilities? YES

Is package-content inspection required for many courses? YES, likely useful for the 13 partial/zero-coverage cases; not performed here

Is human review still required? YES

## 28. Recommendation Readiness

Raw ExternalCourse recommendation-ready: NO

Reviewed DRAFT CourseCapabilityProfile semantically useful: YES

ACTIVE approval still required: YES

Can future COURSE-REC-01B consume approved profiles without SkillsCommons-specific logic: YES

## 29. Recommended Next Step

B. Add bounded course-package content enrichment research.

Keep the existing canonical taxonomy and review gate. Inspect only bounded, sanitized package metadata/content for a follow-up sample; do not build bulk extraction or automatic activation.

## 30. Final Decision

Decision: METADATA_ONLY_ENRICHMENT_PARTIAL

The experiment is complete, but metadata-only enrichment currently covers only 2 of 15 reviewed courses. The provider is ready for governed enrichment research, not automatic recommendation eligibility.

## 31. Git Status

Core-AI: Existing worktree changes plus semantic enrichment module, tests, scripts, docs, and evidence. No commit.

LMS: Clean and unchanged.

STOP.

Do not implement recommendation ranking.
Do not implement COURSE-REC-01B.
Do not add persistence/API/UI.
Do not activate profiles automatically.
Do not modify LMS.
Do not commit.
Do not push.
