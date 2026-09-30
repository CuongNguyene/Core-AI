# ID-02D Contract Semantics Hardening Design

## Goal

Make the instructional-design pipeline enforce semantic relationships as typed
intermediate representation before an artifact reaches the next stage. This
iteration addresses the recurring Smoke-2/Smoke-3 findings without changing
the five-stage architecture, quality-gate severity policy, or the one-shot
baseline.

## Versioning and compatibility

Smoke-3 used structured prompt/schema version `0.3`; its artifacts are
immutable. ID-02D introduces an additive structured patch version `0.3.1`.
The one-shot baseline stays `instructional_design_one_shot_baseline@0.1`.
Historical `0.2` and `0.3` contracts remain registered and readable.

`0.3.1` accepts legacy `is_summative` and `required_capability_refs` fields
for old fixture compatibility, but new model output uses typed fields. If both
the legacy and typed form are supplied, they must agree. No model output is
silently repaired.

## Typed semantic intermediate representation

### Assessment capability semantics

`AssessmentSpec` gains `required_capabilities`, a list of typed capability
requirements. Each item contains a capability semantic string and optional
source objective references. It cannot be an assessment, objective, module,
lesson, or prerequisite artifact ID. `required_capability_refs` remains a
deprecated compatibility field and is rejected by the `0.3.1` stage validator
when it contains any known artifact ID.

`AssessmentDependencyCandidate` remains candidate-only and is never promoted
to an assessed capability or confirmed prerequisite. It is the only place an
assessment task may record an extra task dependency.

### Assessment taxonomy

`AssessmentRole` has `FORMATIVE` and `SUMMATIVE`. `AssessmentSpec.role` is
the new source of truth. A legacy `is_summative` value is mapped only when
`role` is absent; conflicting values are rejected. A lesson may reference only
FORMATIVE assessment IDs from `formative_assessment_ids`.

### Graph ownership

The LessonPlanner proposes lessons. Orchestration derives module `lesson_ids`
from `LessonSpec.module_id`, but does not repair a lesson's objectives. Before
snapshot construction, a lesson objective must belong both to the course and
to its owning module. The quality gate applies the same checks to one-shot and
historical aggregate outputs, reporting findings rather than dropping lessons.

### Planning warnings

`CourseOutline.planning_warnings` contains typed warnings. The first supported
warning is `scope_time_conflict` with decision
`prioritized_core_objectives`. The CoursePlanner must emit it when its explicit
module durations exceed the explicit course duration and it cannot fit the
proposed scope. Deterministic validation checks only arithmetic of declared
durations; it does not infer a domain-specific objective-per-minute heuristic.

### Prerequisite structural minimality review

The existing candidate/model-proposed boundary remains. A deterministic review
labels a required candidate as `STRUCTURALLY_SUPPORTED` only when it has a
non-vague rationale and at least one valid dependent objective/assessment ref;
otherwise it is `INSUFFICIENT_RATIONALE` or `UNRESOLVED_REFERENCE`. This is a
review finding, not confirmation, rejection, or LLM-based semantic judgement.

## Validation flow

```text
AssessmentDesigner@0.3.1
  -> typed assessment/dependency IR
  -> artifact-ID and role validation
PrerequisiteProposer@0.3.1
  -> candidate-only prerequisite IR + structural minimality review
CoursePlanner@0.3.1
  -> objective/module IR + declared-duration warning validation
LessonPlanner@0.3.1
  -> module/objective/formative-ref validation
Orchestration
  -> derive module.lesson_ids, no hidden semantic repair
Quality gate
  -> replay the same semantic checks for all aggregate outputs
```

## Non-goals

- No prompt `0.4`, full Smoke rerun, TEXT-01, production learning path, or
  capability-analysis change.
- No quality-gate relaxation or severity downgrade.
- No LLM-based prerequisite acceptance/rejection.
- No mutation of Smoke-2/Smoke-3 artifacts.

## Acceptance criteria

1. Artifact IDs in capability fields fail `0.3.1` validation and produce
   deterministic quality findings for aggregate outputs.
2. A summative assessment ID in a lesson formative list fails validation;
   valid formative references pass.
3. A lesson objective outside its module/course produces an explicit graph
   finding; the lesson is retained.
4. Declared module duration exceeding declared course duration requires a
   `scope_time_conflict` planning warning.
5. Minimality review never changes candidate status; it only returns a
   structural review result.
6. Regression tests reproduce the Smoke-2/Smoke-3 finding classes and all
   existing instructional-design tests remain green.
