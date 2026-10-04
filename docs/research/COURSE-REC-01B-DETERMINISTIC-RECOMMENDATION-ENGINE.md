# COURSE-REC-01B — Deterministic Course Recommendation Engine

## Scope

This milestone implements a pure deterministic domain engine that selects courses for an already-defined learning target. It does not decide what a learner should learn, generate capabilities, call providers, persist results, expose an API, or modify LMS.

## 1. Repository

Core-AI path: `/Users/mac/Developers/work/LMS/Core-AI`
Branch: `feat/deterministic-ai-course-planning-workspace`
HEAD: `a078526ab7ea38327fdeece142aba325f3de3352`
Working tree: Existing COURSE-REC-01A changes plus this engine/docs/tests/evidence work.
Pre-existing changes: Preserved.

LMS path: `/Users/mac/Developers/work/LMS/lms`
Branch: `dev`
Working tree: Clean and unchanged.

## 2. Domain Boundary

Recommendation answers:

```text
Which governed course best satisfies this existing learning target?
```

Recommendation does NOT answer:

- what capability gap exists;
- whether a LearningNeed should exist;
- LearningNeed generation;
- LearningPath sequencing;
- career progression or adjacent skills.

Input upstream objects: explicit `RecommendationTarget`, `NormalizedCourseCandidate`, and lifecycle status from `CourseCapabilityProfile` assembly.

Mutated upstream objects: **NONE**

## 3. Recommendation Target

Model/class: `RecommendationTarget`

Fields:

- `target_ref`
- `target_capability_refs[]`
- optional `target_level`
- LearningNeed, LearningPath, path-step, gap, and role-requirement references
- explicit prerequisite context

Target capability source: explicit governed capability refs supplied by the caller.

Target level source: explicit target field only.

Trace refs supported: LearningNeed, LearningPath, path step, gap, and role requirement references.

Free-text capability inference: **NO**

## 4. Candidate Contract

Engine candidate model: `CourseRecommendationCandidate` wrapping `NormalizedCourseCandidate` and `CourseProfileStatus`.

Semantic capability source: governed `CourseCapability` entries projected from `CourseCapabilityProfile`.

ACTIVE profile required: **YES**

Provider-only `capabilities=[]` eligible: **NO**

`candidate_from_profile()` keeps profile lifecycle and semantic claims separate from provider metadata.

## 5. Eligibility Gates

| Gate | Rule | Rejection reason |
|---|---|---|
| Profile lifecycle | `profile_status == ACTIVE` | `PROFILE_NOT_ACTIVE` |
| Semantic capability presence | capabilities must be non-empty | `NO_SEMANTIC_CAPABILITIES` |
| Capability intersection | at least one exact target ref | `NO_CAPABILITY_MATCH` |
| Availability | `UNAVAILABLE` is excluded; `UNKNOWN` remains conditional | `COURSE_UNAVAILABLE` |
| Hard prerequisites | explicit `UNSATISFIED` is excluded | `PREREQUISITE_UNSATISFIED` |

## 6. Capability Coverage

FULL_COVERAGE: every target capability ref is matched.

PARTIAL_COVERAGE: at least one, but not every, target ref is matched.

NO_COVERAGE: no target ref is matched; candidate is excluded.

Exact capability refs only: **YES**

Fuzzy matching: **NO**

## 7. Prerequisite Semantics

Statuses: `SATISFIED`, `UNSATISFIED`, `UNKNOWN`, `NOT_APPLICABLE`

SATISFIED rule: explicit context proves the capability, completed course, or provider condition.

UNSATISFIED rule: explicit context proves a required prerequisite is absent or false.

UNKNOWN rule: evidence is missing or prerequisite kind is unsupported.

Missing evidence treated as unsatisfied: **NO**

## 8. Target Level Semantics

Governed ordered level policy exists: **NO**

Comparison strategy: equality-only.

Invented ordering: **NO**

Equal values are `EXACT`; missing values are `UNKNOWN` or `NOT_APPLICABLE`; different opaque values are `DIFFERENT` without automatic incompatibility.

## 9. Ranking

Ranking strategy: `LEXICOGRAPHIC`

Rank factors in order:

1. capability coverage;
2. matched capability count;
3. prerequisite status;
4. target-level status;
5. availability;
6. `course_ref` ascending tie-break.

Stable tie-breaker: `course_ref` ascending.

Source/provider preference: **NO**

Duration preference: **NO**

No arbitrary weighted score is used.

## 10. Availability

AVAILABLE: eligible and ranked above equivalent UNKNOWN candidates.

UNAVAILABLE: excluded.

UNKNOWN: retained with explicit warning and ranked below equivalent AVAILABLE candidates.

Unknown availability warning: **YES**

## 11. Internal / External Parity

Same semantic logic: **YES**

Source type affects rank: **NO**

Parity test: **PASS**

Provider/source values are exposed as provenance only.

## 12. Explainability

Decision detail model: `DecisionDetails`

Fields exposed:

- coverage status, matched refs, missing refs;
- prerequisite status, evaluated refs, unknown refs;
- target-level status;
- availability;
- warnings;
- course provenance.

LLM-generated explanation: **NO**

## 13. Traceability

Course → target: **YES**

Target → LearningPath step: **YES**, when supplied.

Target → LearningNeed: **YES**, when supplied.

LearningNeed → gap: **YES**, through source gap refs.

Gap → role requirement: **YES**, through source role requirement refs.

Raw CV/JD content included: **NO**

## 14. NO_SUITABLE_COURSE

Supported: **YES**

Reasons supported:

- `NO_TARGET_CAPABILITIES`
- `NO_SUITABLE_COURSE`
- rejection counts by machine-readable gate reason

Forced fallback recommendation: **NO**

## 15. Top-K

Default: `5`

Allowed range: `1–20`

Ranking before truncation: **YES**

## 16. Determinism

Input order independent: **PASS**

Repeated runs identical: **PASS**

Randomness used: **NO**

Algorithm ID: `deterministic_course_recommendation`

Algorithm version: `0.1`

## 17. SkillsCommons Boundary

Raw provider-only candidate:

```text
source_system = skillscommons
capabilities = []
availability = available
```

Recommendation eligible: **NO**

Future enriched `CourseCapabilityProfile` uses same engine: **YES**

SkillsCommons-specific ranking branch: **NO**

## 18. Cross-Domain Verification

Software/AI: **PASS**
Sales: **PASS**
Finance/Accounting: **PASS**
HR/Communication: **PASS**

The engine contains no domain-specific capability logic.

## 19. Negative Semantic Cases

Title → capability inference: **PASS**
Description → capability inference: **PASS**
Subject → capability inference: **PASS**
Provider preference absent: **PASS**
Duration bias absent: **PASS**
Level ordering not invented: **PASS**
Prerequisite satisfaction not invented: **PASS**

## 20. Provider Regression

MockExternalProvider: **PASS**
OpenEdxCourseProvider: **PASS**
SkillsCommonsCourseProvider: **PASS**

## 21. Tests

Recommendation engine:

```text
uv run pytest tests/test_course_recommendation.py -q
25 passed
```

Course catalog regression:

```text
uv run pytest tests/test_course_catalog_*.py -q
54 passed
```

Total: **79 passed**

## 22. Static Checks

Ruff format: **PASS**
Ruff: **PASS**
mypy: **PASS** for `app/course_recommendation`; pre-existing `app/course_catalog/semantic_enrichment.py` remains outside this milestone and has baseline mypy/ruff findings
JSON validation: **PASS**
`git diff --check`: **PASS**
Secret scan: **PASS**

## 23. Files Changed

DOMAIN: `services/pai-backend/backend/app/course_recommendation/schemas.py`
SERVICE: `services/pai-backend/backend/app/course_recommendation/engine.py`
SCHEMAS: New recommendation-only schemas; existing catalog schemas unchanged
TESTS: `services/pai-backend/backend/tests/test_course_recommendation.py`
FIXTURES: Deterministic cross-domain/local candidates in focused tests
DOCS: This report
EVIDENCE: `test/results/course-rec-01b/`

PERSISTENCE: **NONE**

API: **NONE**

LMS: **NONE**

## 24. Known Limitations

- No governed ordered level policy exists, so level comparison is equality-only.
- Recommendation target capability refs must be supplied explicitly by an upstream caller.
- Prerequisite satisfaction requires explicit structured context; raw CV/JD text is not parsed.
- SkillsCommons candidates remain ineligible until semantic enrichment supplies governed capabilities.

## 25. COURSE-REC-01C Readiness

Pure engine complete: **YES**

Stable result contract: **YES**

Ready for persistence/API layer: **YES**

Actual blockers: none for the pure engine boundary.

## 26. Final Decision

Deterministic recommendation engine usable: **YES**

Internal/external semantic parity achieved: **YES**

Explainability sufficient: **YES**

No semantic inference boundary violations: **YES**

Can COURSE-REC-01C proceed: **YES**

Decision: `READY_FOR_COURSE_REC_01C`

## 27. Git Status

Core-AI: Existing worktree changes plus recommendation engine, tests, docs, and evidence. No commit.

LMS: Clean and unchanged.

No API, persistence, migration, LMS change, commit, or push was performed.

STOP.
