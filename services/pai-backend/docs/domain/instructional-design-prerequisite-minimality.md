# ID-04B Prerequisite Minimality Semantics

ID-03C.3 recorded a mean `prerequisite_quality` score of 3.6/5. Reviewers
reported prerequisite inflation, broad entry requirements, and supporting
knowledge that could reasonably be taught inside the course. ID-04B adds an
explicit planning disposition; it does not change verification governance.

## Dispositions

- `ENTRY_PREREQUISITE`: candidate knowledge that should reasonably exist before
  course entry. It requires an explicit rationale explaining why entry is
  necessary.
- `IN_COURSE_SUPPORT`: a dependency needed for the target performance that can
  reasonably be introduced, refreshed, scaffolded, or practiced in the course.
- `NOT_REQUIRED`: a proposed dependency not necessary for the objective or
  assessment. It remains in the trace rather than being silently deleted.

The disposition is not evidence that a learner possesses or lacks the
capability. Every model-proposed result remains `status=candidate` and
`basis=model_proposed`; no disposition auto-confirms a prerequisite.

## Integrity and propagation

Each disposition carries `source_dependency_refs`. Missing provenance,
missing entry rationale, model-proposed confirmation, and contradictory
dispositions for the same source dependency are deterministic findings. The
validator fails closed on contradictory dispositions. CoursePlanner and
LessonPlanner receive the enriched `PrerequisiteSpec`, so the disposition is
available downstream without forcing content generation for every support item.

Workload context from ID-04A is informational input to planning. It is not used
by deterministic code to infer a disposition from remaining minutes. The
ID-04A arithmetic and missing-time behavior remain unchanged.

## Prompt and compatibility

The active structured prerequisite prompt is patch-versioned as `0.3.3`.
Prompt versions `0.3.1` and `0.3.2` remain available for historical replay.
No ID-03 artifacts are rewritten. Deterministic research fixtures for Python,
Accounting, Legal, HR, and Construction are written to
`backend/test/results/instructional-design-id-04b-prerequisite-minimality/`.

This milestone does not decide whether a learner actually has a prerequisite,
does not remediate practice coverage, and does not make production-readiness
claims.

## ID-04E provenance recovery

The ID-04D live run exposed a mechanical regression for the Construction
fixture: prerequisite dispositions were model-proposed and correctly
classified, but `source_dependency_refs` was empty even when the preceding
assessment stage contained a dependency with the same capability. The loss was
at the PrerequisiteProposer output boundary, not in the prompt, schema, policy,
or validator.

The orchestration layer now restores only this deterministic edge by exact
normalized capability equality, using a `dependency_candidate:` provenance
reference. Existing references are never overwritten and unmatched values
remain unresolved. CoursePlanner, LessonPlanner, and the final snapshot all
receive the recovered refs. Status remains `candidate` and basis remains
`model_proposed`; no prerequisite is auto-confirmed.
