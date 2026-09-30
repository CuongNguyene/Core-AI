# Instructional Design Experiment ID-02

## Research question

Does a structured, multi-stage instructional-design pipeline produce better
pedagogical alignment and traceability than one-shot course design when both
receive the same `ResearchLearningBrief`, model configuration, and policy?

This experiment evaluates generated instructional-design artifacts, not actual
learner outcomes.

## Conditions

| Condition | Flow | Output |
|---|---|---|
| One-shot baseline | Brief → one-shot generator → quality gate | Canonical research snapshot |
| Structured | Brief → objectives → assessments → prerequisites → course → lessons → quality gate | Canonical research snapshot |

Both conditions serialize to `InstructionalDesignResearchSnapshot` and use the
same deterministic quality gate. The baseline requests the canonical aggregate
but is not coached through the structured sequence.

## Controls and run strategy

`ExperimentConfig` fixes fixture IDs, model/provider/revision, generation
settings, policy, and prompt/schema versions. Unsupported settings are recorded
explicitly. The default supports three runs per fixture/condition without
hard-coding that count.

The intended full matrix is 12 fixtures × 2 conditions × 3 repetitions = 72
runs. The fixture-only smoke runner validates manifest, provenance,
orchestration, and quality-gate mechanics without a model call.

```bash
cd backend
UV_CACHE_DIR=/private/tmp/pai-uv-cache \
uv run python -m app.instructional_design.experiment_cli \
  --mode smoke \
  --fixture fixture-model-monitoring-limited-application \
  --condition structured
```

The first JSON line is the manifest: fixture IDs, conditions, repetitions,
model configuration, policy, prompt/schema versions, and estimated call count.

## Smoke-2 live execution (2026-08-12)

Smoke-2 ran exactly three public research fixtures — Model Monitoring, Python
Data Processing, and Technical Communication — with one run under each
condition. It made 18 planned stage-level calls through `ModelGateway` using
Vilao (`claude-sonnet-5`), `temperature=0.0`, and
`max_output_tokens=8192`; `top_p` and `seed` were explicitly recorded as
unsupported. Each audit records the external routing decision, provider/model
revision, prompt/schema version, policy version, token usage, and correlation
ID. The external payloads were only explicit `research_fixture` briefs; no
CV/JD or production profile was sent.

All six runs completed. One prerequisite stage returned fenced JSON and used
the gateway's single structured-output repair attempt; the repaired output was
schema-valid and auditable. Raw artifacts are in
`backend/test/results/instructional-design-smoke-2-live-3/`.

| Condition | Completed | Gate pass | Finding count | Mean unresolved prerequisites |
|---|---:|---:|---:|---:|
| One-shot | 3/3 | 2/3 | 1 | 3.0 |
| Structured | 3/3 | 1/3 | 9 | 5.67 |

This is not a winner declaration or statistical result. In particular, the
gate was discriminative in this smoke: it rejected one one-shot and two
structured artifacts. The next valid review step is blinded human evaluation
of the persisted canonical snapshots.

## ID-02B failure analysis

The nine structured findings were annotated separately in
`backend/test/results/instructional-design-smoke-2-live-3/failure-analysis.json`.
The annotation is researcher-authored and references the exact persisted
run/finding index; it does not modify the underlying result or quality gate.

| Root-cause hypothesis | Count | Producer stage | Validator verdict |
|---|---:|---|---|
| `assessment_scope_creep` | 4 | AssessmentDesigner | Correct |
| `under_generation` | 5 | CoursePlanner / LessonPlanner | Correct |
| `validator_false_positive` | 0 | — | Not observed |

The assessment findings use objective IDs as capability dependencies instead
of preserving objective traceability or declaring a separate candidate
dependency. The course/lesson findings omit objective references entirely.
Neither is evidence to relax the quality gate.

This smoke does not reject the structured-pipeline hypothesis. It demonstrates
the expected trade-off: a one-shot output benefits from a single coherent
context, while a staged output gains auditability, replaceability, and
quality-control boundaries only when its cross-stage state, identifiers, scope
and dependency propagation are sufficiently constrained. Prompt v0.3 is
therefore deferred until blinded review evaluates whether the pedagogical plan
is reasonable independently of these machine-validity defects.

The reviewer handoff is prepared under
`backend/test/results/instructional-design-smoke-2-live-3/blinded-review/`.
Reviewers receive only `reviewer-packets/review-001.json` through
`review-006.json` and complete the corresponding files under
`reviewer-submissions/`, following `reviewer-guide.md`. The private mapping,
raw results, failure-analysis annotations, provider metadata, and condition
labels stay with the researcher until all blind submissions are complete.

## Milestone state

| Milestone | State |
|---|---|
| ID-01 contracts and quality gate | PASS |
| ID-02 experiment infrastructure | PASS |
| ID-02 real comparative smoke | PASS |
| ID-02 structured design quality | NEEDS ITERATION |
| ID-02 human evaluation | NEXT |
| TEXT-01 | NOT READY |

## ID-02D contract-semantics hardening

ID-02D addresses the repeated Smoke-2/Smoke-3 defects as compiler-style
intermediate-representation rules, not quality-gate exceptions and not a new
prompt generation strategy. Structured patch version `0.3.1` is additive;
historical `0.2`/`0.3` artifacts and the one-shot baseline remain readable.
No new live Smoke run was performed for this change.

The patch adds typed assessment roles and typed capability requirements. An
assessment capability must be a semantic capability/dependency, never an
objective, assessment, lesson, module, or prerequisite artifact ID. Lessons
may list only FORMATIVE assessment IDs in `formative_assessment_ids`, and each
lesson objective must be owned by both its course outline and its referenced
module. The orchestration layer continues to derive only `module.lesson_ids`;
it does not repair model-authored objective or assessment references.

For explicit durations only, a CoursePlanner must declare
`scope_time_conflict` / `prioritized_core_objectives` when module time exceeds
course time. This is arithmetic over authored durations, not an
objective-per-minute heuristic. Required model-proposed prerequisites receive
a deterministic structural review (traceable reference plus non-vague
rationale), but remain `candidate`; the review never confirms, rejects, or
uses an LLM to judge the prerequisite.

The aggregate quality gate replays the same semantic checks for one-shot and
historical artifacts, emitting findings instead of removing artifacts. This
closes the recurring review patterns while preserving the conclusion of
Smoke-3: structured design needs tighter typed contracts and cross-stage state
management before it is compared again pedagogically.

## Fixtures, metrics, and limitations

Fixtures are explicitly authored `research_fixture` briefs: Model Monitoring,
Python Data Processing, and Technical Communication; each has limited and
substantial prior-evidence plus application and analysis variants. They do not
derive from role profiles, capability PREVIEW, CVs, or JDs.

The result groups runs into a per-fixture `ExperimentComparison`, retaining
separate one-shot and structured runs plus any human evaluations. The report
records gate pass, findings by code/severity, coverage, unresolved
prerequisites, cognitive mismatches, prerequisite violations, and dependency
failures. Aggregation is descriptive only: count, mean, median, min, max, and
standard deviation where applicable. It has no composite score or winner.

ID-02 does not measure factual correctness, learner outcomes, competency
verification, production readiness, or statistical significance.

## ID-02C Smoke-3 protocol

ID-02C keeps the five-stage structured architecture and introduces structured
prompt/schema version `0.3` after the Smoke-2 failure analysis and blinded SME
review. The one-shot comparison remains
`instructional_design_one_shot_baseline@0.1`.

Smoke-3 uses the same three fixtures, one run per condition, Vilao/
`claude-sonnet-5`, temperature `0.0`, `max_output_tokens=8192`, and explicit
unsupported `top_p`/`seed` fields. Its conditions are `one_shot` and
`structured_v0.3`; the manifest is persisted before any model call under a new
`backend/test/results/instructional-design-smoke-3/` directory. The expected
call count is 18. Smoke-2 artifacts are never overwritten.

The v0.3 implementation hardens canonical reference ownership, exact
prerequisite deduplication, assessment dependency candidates, and practice
coverage. Unknown references fail closed; module lesson ownership is derived
by orchestration and then checked by the unchanged quality-gate boundary. Human
review fields remain rubric v0.1 and continue to separate machine validity from
pedagogical quality.

## ID-02C Smoke-3 execution result

The controlled Vilao run was written to
`backend/test/results/instructional-design-smoke-3-live-network-3/`. Its
manifest was persisted before calls and records 3 fixtures, `one_shot` and
`structured_v0.3`, one run per fixture/condition, 18 planned model calls,
Vilao/`claude-sonnet-5`, temperature `0.0`, `max_output_tokens=8192`, and
unsupported `top_p`/`seed`.

The missing Technical Communication structured slot was recovered in a
separate run using the same provider/model/config/policy and v0.3 contracts.
The provider returned invalid JSON on the first bounded attempt and the
existing gateway repair path produced a valid schema-conforming result; no raw
model output was persisted and no artifact was manually patched. The recovery
artifact is under `recovery-run-1/`.

`results-complete.json` replaces only that missing slot while preserving the
original partial `results.json`. It contains 6/6 completed runs (one-shot 3/3,
structured v0.3 3/3), and six condition-blind reviewer packets are now under
`blinded-review/reviewer-packets/`. The private mapping remains separate.
No winner is declared. The completed structured condition has four
`assessment_dependency_not_covered` errors; their RCA is recorded in
`dependency-trace.json` and classifies all four as AssessmentDesigner scope
creep, with the deterministic validator correct. `final-status.json` records
`READY_FOR_BLINDED_REVIEW`; TEXT-01 remains NOT READY.

## ID-02C milestone state

| Milestone | State |
|---|---|
| v0.3 typed contracts and prompt registry | PASS |
| Cross-stage reference ownership and fail-closed validation | PASS in focused tests; live model still exposes violations |
| Deterministic practice/lesson ownership gate | PASS in focused tests |
| Smoke-3 manifest and controlled runner | PASS |
| Smoke-3 six-run live comparison | PASS: 6/6 completed after isolated recovery |
| Smoke-3 blinded review handoff | COMPLETE: 6 submissions received |
| ID-02C human review calibration | COMPLETE: 1 reviewer × 6 packets |
| Structured design quality after review | NEEDS_ITERATION |
| TEXT-01 | NOT READY |

## ID-02D Smoke-4 validation

Smoke-4 was run as a new, isolated artifact set under
`backend/test/results/instructional-design-smoke-4/` with exactly the
`structured_v0.3.1` condition and one planned run for each of Model
Monitoring, Python Data Processing, and Technical Communication. The manifest
was persisted before model execution and records Vilao/`claude-sonnet-5`,
temperature `0.0`, `max_output_tokens=8192`, unsupported `top_p`/`seed`, policy
`pai_instructional_design@0.1`, all five `0.3.1` prompt/schema contracts, and
15 planned model calls. Smoke-2 and Smoke-3 directories were not modified.

The controlled run completed 2/3 fixtures. Model Monitoring and Python Data
Processing passed all five Smoke-4 contract checks: capability fields did not
contain artifact IDs, formative/summative references were separated, lesson
objectives respected course/module ownership, model-proposed prerequisites
remained candidates, and declared scope warnings were valid. Python still
produced four existing `assessment_dependency_not_covered` quality-gate
errors; these are reported as quality-gate findings, not relaxed or repaired.

Technical Communication failed in `AssessmentDesigner` with
`StructuredOutputFailedError: invalid_model_json`. The validation report
classifies that as `MODEL_RELIABILITY` and marks semantic checks as not
observed for that run; it does not misreport a contract violation. Because
the required 3/3 runs were not completed, the exact milestone decision is
`ID-02D BLOCKED`. No prompt, validator, severity, or human-review rubric was
changed in response to the live failure.

## ID-02D.1 recovery

The failed Technical Communication artifact was recovered once under
`backend/test/results/instructional-design-smoke-4-recovery-1/` using the
parent Smoke-4 manifest and the existing gateway repair/retry path. The
recovery produced five model audits, a valid structured snapshot, and
completed the merged 3/3 run set. The original Smoke-4 `manifest.json` and
`results.json` remain unchanged.

The merged recovery validation passes all five contract checks and keeps the
quality gate unchanged. Python still has four gate findings, representing two
unique requirements duplicated across the legacy and typed capability fields:
`basic Python programming` and `written justification and reasoning
communication`. The safe trace is persisted in
`python-dependency-trace.json`. Both are classified as
`assessment_scope_creep`, with `missing_dependency_propagation` as the
secondary observation; the validator is correct, lesson graph coverage is
complete, and no candidate prerequisite was promoted.

The recovery decision is `ID-02D NEEDS ITERATION`: reliability is recovered,
but the remaining quality-gate errors require upstream dependency/assessment
semantics work before ID-03. No prompt v0.4 or TEXT-01 work is authorized by
this result.

## ID-02D.2 dependency ownership and normalization

The Smoke-4 Python dependency trace identified duplicate ownership: the same
two semantic requirements were projected through both legacy
`required_capability_refs` and typed `required_capabilities`. The validator was
correct; the missing boundary was an explicit normalization step before gate
evaluation.

ID-02D.2 adds a canonical dependency model and normalizer. Typed capability
requirements are the source of truth, legacy values are compatibility-only, and
source references are retained as provenance. Exact duplicate representations
collapse to one canonical requirement. Conflicting representations produce an
explicit `conflicting_dependency_semantics` error and are not silently merged.
Dependency candidates remain supporting/candidate data and are carried through
structured partial artifacts into the snapshot without promotion.

Focused regression tests cover identical legacy/typed values, conflicts,
artifact-ID misuse, candidate preservation/non-promotion, provenance, and the
Smoke-4 quality-gate path. The existing quality-gate rules, severities, and
prompt/schema versions are unchanged. A new live Smoke-4 conclusion is not
claimed until the controlled Python `structured_v0.3.1` validation is rerun;
TEXT-01 remains NOT READY.
