# Instructional Design Contract Semantics

## Purpose

This document describes the deterministic semantic boundary for the
research-only instructional-design experiment. It is not a production learning
path or competency-approval contract.

## Assessment semantics

`AssessmentSpec.role` is the semantic taxonomy:

| Role | Meaning | Lesson reference rule |
|---|---|---|
| `formative` | practice or feedback during learning | may appear in `LessonSpec.formative_assessment_ids` |
| `summative` | evaluative evidence after instruction | must not appear in `LessonSpec.formative_assessment_ids` |

`is_summative` remains readable only for historical artifacts. When both it
and `role` are explicitly supplied, they must agree.

`required_capabilities` contains typed semantic capability/dependency strings,
optionally linked to source objectives. It never holds artifact identifiers.
The legacy `required_capability_refs` field is retained for old artifacts but
is checked by the same rule.

If an assessment genuinely needs a capability outside the objective/brief,
the model emits an `AssessmentDependencyCandidate`. Candidates are not
silently converted into assessed requirements or confirmed prerequisites.

## Cross-stage graph rules

The LessonPlanner supplies `module_id`, objective references, prerequisite
references, and formative-assessment references. The orchestrator derives the
reverse module-to-lesson edge only. It never rewrites semantic references.

For structured `0.3.1`, unknown references, an objective outside the lesson's
module, a summative ID in a formative list, or an artifact ID in a capability
field fail closed before snapshot construction. The quality gate emits the
same finding classes for aggregate/one-shot/historical snapshots so reviewers
can see the defect without losing the artifact.

## Planning and prerequisites

`CourseOutline.planning_warnings` is an authored planning declaration. The
first supported warning is:

```json
{
  "type": "scope_time_conflict",
  "decision": "prioritized_core_objectives"
}
```

It is required only when explicitly declared module minutes exceed explicitly
declared course minutes. The system makes no universal duration or
objective-count inference.

Model-proposed required prerequisites remain `candidate`. The deterministic
structural review returns one of `structurally_supported`,
`insufficient_rationale`, `unresolved_reference`, or `not_applicable`. It
does not validate pedagogical truth and never mutates status.

## Dependency ownership and normalization (ID-02D.2)

`AssessmentSpec.required_capabilities` is the canonical semantic owner for
requirements directly assessed by an objective. The historical
`required_capability_refs` field is compatibility input only; it cannot create
an independent downstream requirement. Before the quality gate, the explicit
`DependencyNormalizer` produces `canonical_dependencies` and preserves every
source representation in `provenance.sources`.

Identical legacy and typed values are normalized by NFKC/case-folded,
whitespace-collapsed exact text only. They become one
`dependency_role=required_capability` with both
`typed_required_capability` and `legacy_compatibility` provenance entries.
Different values are not guessed or silently merged: the normalizer emits an
`ERROR` `conflicting_dependency_semantics` finding and retains both values for
review. Artifact IDs remain invalid capability values.

`AssessmentDependencyCandidate` is a supporting dependency proposal, not an
assessed requirement. It is represented as
`dependency_role=supporting_dependency`, `status=candidate`, and keeps its
candidate provenance through the experiment partial artifacts and the
snapshot's `dependency_candidates` plus `canonical_dependencies` fields. The
normalizer never promotes a candidate or changes the existing
`model_proposed prerequisite -> candidate` rule.

This boundary fixes duplicate ownership from the Smoke-4 Python trace without
weakening the quality gate: real uncovered canonical requirements still emit
`assessment_dependency_not_covered`, while an identical legacy/typed pair is
checked once. No fuzzy matching, embeddings, taxonomy inference, prompt
version change, or automatic dependency promotion is performed.

## Version policy

`0.3.1` is an additive structured patch version. It does not mutate Smoke-2
or Smoke-3 artifacts and it does not introduce a `0.4` prompt. A later
controlled Smoke run is required before drawing any quality conclusion from
the patch.
