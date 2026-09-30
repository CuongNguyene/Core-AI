# ID-03A Cross-Domain Instructional-Design Validation

## Motivation

The existing instructional-design evidence is concentrated in IT/AI fixtures.
ID-03A adds a clean, domain-diverse input set so the same objective,
assessment, prerequisite, course, lesson, and quality-gate pipeline can be
evaluated outside software workflows. This milestone creates input
infrastructure only; it does not execute a model experiment or produce text
lesson content.

## Research question

Does the Instructional Design pipeline preserve observable objectives,
evidence-based assessments, minimal prerequisites, sequencing, and
traceability across professional domains without assuming IT terminology,
coding tasks, software workflows, or technical artifacts?

## Fixture boundary

`CrossDomainFixture` is intentionally input-only. It contains exactly:

- `metadata`: controlled experiment labels;
- `brief`: a `ResearchLearningBrief`.

It cannot contain generated objectives, assessments, prerequisites, course
outlines, lessons, or other output artifacts (`extra="forbid"`). The existing
`ResearchFixtureBundle` remains the generated-artifact fixture used by prior
deterministic tests; ID-03A does not mix those two roles.

The registry is `cross_domain_validation_fixtures()` in
`backend/app/instructional_design/fixtures.py`. It returns fresh deterministic
brief-only fixtures and performs no provider calls.

## Domain matrix

| Domain | Fixture | Learning type | Difficulty | Industry family |
|---|---|---|---|---|
| IT / AI | `python_data_processing` | procedural technical skill | medium | technology |
| Accounting / Finance | `accounting_financial_reporting_basic` | regulated professional skill | medium | finance |
| Legal / Compliance | `legal_contract_review_basic` | analytical judgment skill | high | legal services |
| HR / Management | `hr_recruitment_planning_basic` | scenario-based professional skill | medium | human resources |
| Construction / Engineering | `construction_drawing_and_method_basic` | procedural safety skill | high | construction |

The labels are controlled vocabulary for experiment grouping only. They are
not a competency ontology and do not drive generation behavior.

## Domain-neutral invariants

The pipeline must not assume:

- IT terminology or coding tasks;
- software workflows or technical artifacts;
- a universal professional context for evidence.

For every domain, generated output should preserve these contracts:

### Objective quality

An objective describes observable learner behavior. “Understand accounting
principles” is insufficient; “prepare a basic financial statement and identify
discrepancies” is observable.

### Assessment alignment

An assessment must collect evidence of the objective. A contract-review quiz
alone does not show analysis; reviewing a clause and explaining identified
risks does. A construction assessment should elicit procedural sequencing and
stated safety considerations without requiring unsupported expert authority.

### Prerequisite quality

Prerequisites distinguish what is required to perform the target from what is
merely helpful. Basic accounting concepts may be required for a financial
reporting task; advanced auditing knowledge is not silently added. Existing
candidate/confirmed governance remains unchanged.

### Sequencing

Course and lesson order must follow supplied objective, module, lesson, and
prerequisite references. Domain labels never authorize synthetic references or
automatic ordering assumptions.

### Traceability

Every objective, assessment, prerequisite, module, and lesson must preserve
its typed references and provenance through the existing deterministic quality
gate. The ID-02D dependency ownership and normalization rules remain in force.

## Evaluation dimensions

ID-03A defines dimensions but intentionally does not create scores:

- objective quality;
- assessment alignment;
- prerequisite quality;
- sequencing;
- traceability.

Human review and model execution belong to later ID-03 milestones. Smoke-5,
prompt tuning, RAG, and TEXT-01 are outside this task.

## ID-03B live-smoke findings

ID-03B ran one `structured_v0.3.1` execution for every fixture. All 25
planned Vilao calls completed, but the pipeline did not validate domain
generalization: two snapshots reached the quality gate and three stopped at
fail-closed reference validation.

| Domain | Observed failure | Producer/root cause | Correct fix layer |
|---|---|---|---|
| Accounting | A capability requirement cited `obj-bfr-001` outside its parent assessment's objective set. | `AssessmentDesigner` produced globally valid IDs with invalid parent ownership. | prompt |
| HR | A summative assessment required `obj-hrb-01` while owning only objectives 2 and 3. | `AssessmentDesigner` ownership violation. | prompt |
| Construction | Capability requirements cited objective IDs 1 or 2 outside their parent formative/summative assessment. | `AssessmentDesigner` ownership violation. | prompt |
| Python | Seven `assessment_dependency_not_covered` errors. One explicit external prerequisite was incorrectly a required capability; the remaining requirements had no explicit semantic coverage from objective `capability_refs`. | assessment scope creep plus missing dependency propagation. | prompt |
| Legal | Six `assessment_dependency_not_covered` errors. Two requirements duplicated explicit dependency candidates; four lacked a safe exact semantic coverage link to objective capability refs. | assessment scope creep plus missing dependency propagation. | prompt |

The reference validator is correct: all seven rejected IDs existed in the
ObjectiveDesigner output but were not owned by the parent `AssessmentSpec`.
No objective was synthesized and no fuzzy mapping was attempted.

The quality gate is also correct. It accepts only learner-known evidence,
capability refs of objectives actually taught by lessons, or confirmed
prerequisites. ID-03B objectives emitted empty `capability_refs`; model
prerequisites remained candidates as required by policy, so neither can be
treated as confirmed coverage. The trace deliberately records rephrased
prerequisites as unmatched rather than treating them as semantic equivalents.

The `DependencyNormalizer` is not the source of these failures: identical
legacy and typed requirements merged with both provenance sources, and
supporting dependency candidates remained `candidate` rather than being
promoted. Durable evidence is in
`backend/test/results/instructional-design-id-03b-root-cause/`.

ID-03B therefore remains **NEEDS ITERATION**. The next change must target the
AssessmentDesigner/ObjectiveDesigner prompt contracts and be validated with
the existing fail-closed validator and unchanged quality gate; this document
does not claim cross-domain generalization success.

## ID-03B.4 dependency and lesson-ownership trace

ID-03B.4 is analysis-only. It reuses the ID-03B.3 artifacts and does not rerun
Vilao or change prompts, schemas, the quality gate, validators, or the
DependencyNormalizer.

### Python dependency propagation

The nine findings are emitted for confirmed assessment capabilities (four
unique capability values across formative and summative assessments). The
AssessmentDesigner creates them correctly as semantic requirements and the
normalizer preserves both legacy and typed provenance. They are not supporting
dependency candidates, so candidate non-promotion is intentional. The first
invalid state is the absence of an explicit capability-ownership link from the
assessment requirement to objective/course/lesson coverage: objectives have
empty `capability_refs`, while course modules and lessons are only objective
linked. The quality gate therefore cannot prove coverage without inferring
semantic equivalence.

| Finding | Root cause | Fix layer |
|---|---|---|
| `assessment_dependency_not_covered` (9) | missing dependency propagation from required assessment capabilities into structured instructional coverage | orchestration |

The gate is correct under its current contract: learner-known, taught
objective capability refs, and confirmed prerequisites are the only accepted
coverage sources. Model-proposed prerequisites remain candidates and are not
promoted. Detailed per-capability traces are in
`backend/test/results/instructional-design-id-03b4-root-cause/python-dependency-trace.json`.

### Legal lesson objective ownership

CoursePlanner produced valid module ownership: `module-lcrb-03` owns only
`obj-lcrb-03`. LessonPlanner then created `lesson-lcrb-03-summative` with
`obj-lcrb-01`, `obj-lcrb-02`, and `obj-lcrb-03`; the first two are outside that
module. The validator correctly failed closed. The responsible producer is
LessonPlanner; the future enforcement fix belongs in orchestration (derive a
module-scoped allow-list and reject invalid output before downstream use), not
in automatic reference repair.

| Finding | Root cause | Fix layer |
|---|---|---|
| `lesson_objective_outside_module` | LessonPlanner emitted cross-module objective refs | orchestration |

The partial artifact and exact invalid refs are recorded in
`backend/test/results/instructional-design-id-03b4-root-cause/legal-objective-trace.json`.

ID-03B.4 confirms the AssessmentDesigner allow-list and dependency provenance
invariants, but ID-03B remains **NEEDS ITERATION**. No production fixes or
human review were performed.

## ID-03B.5A dependency propagation fix

ID-03B.4 showed that supporting dependency candidates stopped at the
AssessmentDesigner boundary. ID-03B.5A adds an orchestration/planning boundary
that passes the same candidate collection, without reinterpretation, to the
PrerequisiteProposer, CoursePlanner, and LessonPlanner.

The flow is now:

```text
AssessmentSpec.required_capabilities
AssessmentSpec.dependency_candidates
        ↓
planning-stage inputs
        ↓
prerequisite / course / lesson proposals
        ↓
canonical dependency snapshot and quality gate
```

The two dependency roles remain distinct. A `required_capability` is directly
measured by an assessment; a `supporting_dependency` is only a model-proposed
candidate until reviewer/policy processing confirms otherwise. Propagation
does not promote candidates, create lesson content automatically, or change
the DependencyNormalizer's merge semantics. The candidate's source
assessment reference and `candidate` status remain in the canonical snapshot.

Changed layer: orchestration/planning propagation only. AssessmentDesigner,
schemas, quality-gate severity, validator, and DependencyNormalizer semantics
are unchanged. The lesson objective ownership failure from ID-03B.4 remains a
separate ID-03B.5B issue and is intentionally not fixed here.

## ID-03B.5B objective graph ownership

The Legal failure from ID-03B.4 was caused by a lesson carrying objectives that
were not owned by its parent module. The ownership invariant is now enforced at
the orchestration boundary:

```text
course.objective_ids
    ⊇ module.objective_ids
    ⊇ lesson.objective_ids
```

Course output is converted into an application-owned
`objective_ids_by_module` allow-list before LessonPlanner execution. A module
objective outside the supplied course objectives fails closed before the lesson
stage. Lesson references are still validated after generation, so an output
that ignores the allow-list cannot be repaired, moved, or supplemented; it is
rejected with the existing ownership error.

This keeps ObjectiveDesigner as the only objective creator. CoursePlanner owns
module membership, and LessonPlanner may select only a subset of its parent
module's objectives. No objective is renamed, synthesized, or inferred. The
strict validator remains unchanged in severity and continues to protect the
same subset invariant.

ID-03B.5B changes only the CoursePlanner/LessonPlanner orchestration boundary.
AssessmentDesigner, schemas, quality gate, validator, and DependencyNormalizer
remain unchanged. Dependency candidate propagation from ID-03B.5A is preserved
alongside the new module-scoped objective map.

## ID-03B.6 controlled cross-domain validation

After ID-03B.5A and ID-03B.5B, a new controlled Vilao run used exactly five
fixtures, `structured_v0.3.1`, one run per fixture, and 25 planned stage calls:
`vilao / claude-sonnet-5`, temperature `0`, and `8192` max output tokens.
Historical smoke artifacts were not overwritten.

| Fixture | Pipeline/snapshot | Reference graph | Dependency findings |
|---|---|---|---:|
| Python | complete | pass | 5 |
| Accounting | complete | pass | 10 |
| Legal | complete | pass | 5 |
| HR | complete | pass | 6 |
| Construction | complete | pass | 5 |

The former AssessmentDesigner ownership collisions did not recur. The Legal
`lesson objective outside module` failure also did not recur: all module
objectives were subsets of course objectives and every lesson objective was a
subset of its parent module.

Dependency propagation and pedagogical coverage are reported separately. All
generated supporting candidates survived the orchestration boundary with
candidate status and dependency-candidate provenance; none was promoted to a
required capability or confirmed prerequisite. This propagation result does
not make `assessment_dependency_not_covered` disappear: the deterministic gate
still reported 5 Python findings (compared with 7 in ID-03B and 9 in ID-03B.3),
because candidate survival is not equivalent to taught or confirmed coverage.

No explicit `assessment_scope_creep` finding occurred. The outcome is
`not_evaluable` for global scope-creep claims, not proof that the boundary is
solved. Detailed immutable artifacts are in
`backend/test/results/instructional-design-id-03b6-cross-domain-smoke/`.

All five pipelines completed without contract or orchestration failures, so
the result is **HUMAN_REVIEW_READY** for blinded SME review. This does not mean
the quality gate passed or that pedagogical quality is established; remaining
coverage findings must be reviewed as design issues. No human review was
started in this milestone.

## ID-03C blinded SME review protocol

ID-03B.6 produced five complete cross-domain snapshots with the reference
graphs intact, so the next step is human evidence collection rather than more
model generation. ID-03C prepares one condition-blind packet per fixture. The
packet contains the research brief, objectives, assessments, prerequisites,
course outline, lessons, and reviewer-visible machine observations. It omits
condition, prompt/model, quality-gate state, prior findings summaries, and
root-cause or implementation-layer metadata.

Machine validity and pedagogical judgement are separate axes. A traceability
observation is presented as an observation for the reviewer to inspect; it is
not converted into a pedagogical score. Reviewers score ten dimensions from
1--5, provide an evidence-based rationale for every score, record prerequisite
acceptance and edit effort, and answer independently whether the design is
pedagogically reasonable when machine issues are ignored. No weighted composite,
winner, pass/fail judgement, or domain ranking is computed in this milestone.

Reviewer submissions are validated fail-closed: all ten scores and rationales,
the special question, prerequisite decision, edit-effort enum, and matching
review ID are required. The preparation command leaves
`reviewer-submissions/` empty and writes only the submission template; it does
not fabricate human results or alter the ID-03B.6 generated artifacts.

Preparation artifacts are written to
`backend/test/results/instructional-design-id-03c-human-review/`.

## ID-03C.1 submission contract recovery

The ten received reviewer files are immutable source records. They use the
older `@0.1` wrapper (`technical_review` and `pedagogical_review`) while the
ID-03C packet contract targets `@0.2`. Recovery therefore runs as a deterministic
compatibility layer: explicit section flattening and exact aliases are copied
into canonical draft fields, with source paths and SHA-256 checksums recorded.

The recovery maps `sequence_coherence` to
`course_sequence_coherence`, exact enum values for edit effort, and exact
case-insensitive `yes`/`partially`/`no` answers. A mixed special-question value
containing prose or citations is ambiguous and remains unresolved. The three
new dimensions (`scope_balance`, `workload_time_realism`, and
`domain_appropriateness`) are never synthesized. Under-teaching and
over-teaching are preserved as legacy evidence and are not combined into a
scope score. Missing prerequisite decisions and any non-lossless edit-effort
value also become reviewer-completion requests.

Each recovered draft is explicitly `CANONICAL_VALID` or
`NEEDS_REVIEWER_COMPLETION`. Original submissions are not overwritten; only
canonical drafts, an inventory, minimal completion requests, and recovery
reports are written under
`backend/test/results/instructional-design-id-03c1-submission-recovery/`.
Preliminary score signals remain non-canonical until completion requests are
resolved and the strict ID-03C validator passes.

Completion requests use typed field descriptors rather than free-form ranges:
integer scores declare `allowed_range: [1, 5]`, every score field declares
`rationale_required`, booleans declare `type: boolean`, and the special
question declares an explicit enum. Each request is colocated with its review
packet and canonical draft under `review-xxx/`.

## ID-03C.2 reviewer completion merge

Completion submissions are deltas, not re-reviews. The deterministic merger
resolves each submission by the pair `review_id + reviewer_id`, checks the
requested-field allow-list, validates strict score/boolean/enum types, and
fills only unresolved draft fields. An attempt to change an already recovered
judgement is `CONFLICT`; an invalid type, wrong identity, or unexpected field
is `INVALID_COMPLETION`; a valid but incomplete delta is `INCOMPLETE`.

The merge writes final canonical submissions with separate recovery and
completion provenance and never overwrites source submissions, completion
submissions, or ID-03C.1 drafts. `SME_ANALYSIS_READY` is emitted only when all
ten submissions pass the strict validator with zero conflicts, incomplete
records, invalid completions, source mutations, or judgement overwrites.

For the received ID-03C.2 files, the operator supplied one explicit identity
correction, `codex-sme-01` → `codex-sme-reviewer`; the original completion file
remains unchanged and the alias is recorded in the merge manifest. The corrected
completion set now yields 10/10 `CANONICAL_VALID`, zero conflicts, and
`SME_ANALYSIS_READY=true`.

## ID-03C.3 cross-domain SME analysis

ID-03C.3 analyzes only those ten canonical-valid submissions. It reports
descriptive statistics for each of the ten rubric dimensions, per-fixture
distributions, pairwise reviewer differences, explicit special-question
answers, edit effort, prerequisite acceptability, bounded thematic coding, and
machine-observation/human-judgement alignment patterns. It does not alter
scores, rank reviewers or domains, compute a weighted composite winner, or
turn machine traceability findings into pedagogical failures.

The artifact set is written to
`backend/test/results/instructional-design-id-03c3-sme-analysis/`.
The dataset integrity block confirms 10 reviews, two reviewers, five fixtures,
and complete rubric/rationale fields before analysis is allowed. The observed
special-question distribution is 8 `YES` and 2 `PARTIALLY` (no `NO`). The
descriptive sample is intentionally small: two reviewers and one generated
artifact per domain, with no learner-outcome evidence, so these are signals
rather than generalization claims.

The current conservative reading is `CROSS_DOMAIN_PARTIALLY_SUPPORTED` with
`PEDAGOGICAL_SIGNAL_MIXED`; the report is `READY_FOR_NEXT_ID_MILESTONE`, not a
production-readiness or course-generation decision. Technical validity and
pedagogical quality remain separate axes throughout.

| Dimension | Mean | Median | Range |
|---|---:|---:|---:|
| objective_measurability | 4.2 | 4.0 | 4--5 |
| objective_assessment_alignment | 4.6 | 5.0 | 4--5 |
| evidence_validity | 4.3 | 4.0 | 4--5 |
| cognitive_alignment | 4.4 | 4.5 | 3--5 |
| prerequisite_quality | 3.6 | 3.5 | 2--5 |
| course_sequence_coherence | 4.7 | 5.0 | 4--5 |
| instruction_assessment_alignment | 3.6 | 4.0 | 3--4 |
| scope_balance | 3.9 | 4.0 | 2--5 |
| workload_time_realism | 2.7 | 3.0 | 1--4 |
| domain_appropriateness | 5.0 | 5.0 | 5--5 |

The strongest descriptive signals are domain appropriateness and sequence
coherence. Workload/time realism, prerequisite quality, and
instruction/assessment alignment are the weaker dimensions. These are not
weighted into a single score. Pairwise comparison found 22 exact agreements,
47 differences of at most one point, and 3 differences of at least two points;
the largest spread was prerequisite quality (construction had the largest
fixture-level spread). The explicit pedagogical question was YES in 8/10 and
PARTIALLY in 2/10; edit effort was none=1, minor=2, moderate=5, major=2.

ID-04A takes the workload/time signal forward as a separate deterministic
milestone. The SME score is research provenance only; it is not hard-coded into
the validator. See `docs/domain/instructional-design-workload-semantics.md`.

ID-04B similarly addresses the prerequisite-quality signal (`3.6`) with an
explicit distinction between `ENTRY_PREREQUISITE`, `IN_COURSE_SUPPORT`, and
`NOT_REQUIRED`. These are candidate planning dispositions, not learner
verification. Source dependency provenance is preserved and contradictory
dispositions fail closed; no disposition auto-confirms a prerequisite. See
`docs/domain/instructional-design-prerequisite-minimality.md`.

ID-04C addresses `instruction_assessment_alignment` (`3.6`) with explicit
practice-before-summative coverage traces. The deterministic gate distinguishes
instruction, guided/independent practice, formative evidence, and summative
assessment, enforces ordering and self-reference rules, and uses canonical refs
only. It does not prove learner mastery. See
`docs/domain/instructional-design-practice-coverage.md`.

## ID-04E provenance recovery

ID-04D completed all five live pipelines but found a Construction-specific
provenance regression: prerequisite dispositions had no
`source_dependency_refs`. ID-04E fixed this at orchestration propagation by
matching a disposition to the preceding dependency candidate using exact
normalized capability text. Prompt `0.3.4`, schemas, policies, validators,
quality-gate severity, and historical artifacts were unchanged. The targeted
Construction rerun completed five model calls with graph integrity, candidate
governance, workload output, practice coverage, and snapshot provenance
preserved. This is a traceability recovery, not evidence of improved SME
scores or domain generalization.
