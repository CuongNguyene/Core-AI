# ID-04A Workload & Time Budget Semantics

ID-03C.3 gave `workload_time_realism` a mean of 2.7/5. ID-04A addresses only
that signal. It does not change prerequisite minimality, practice coverage,
assessment semantics, graph ownership, or historical ID-03 artifacts.

## Declared versus planned time

The single declared budget is `ResearchLearningBrief.constraints.estimated_total_minutes`.
Planner estimates are compared with it; downstream output cannot redefine it.
The result is a planning estimate, not a measurement or prediction of learner
completion time.

The arithmetic source of truth is the category allocation:

- instruction
- guided practice
- independent practice
- formative assessment
- summative assessment
- feedback/revision

`planned_total_minutes` is the sum of those category allocations. Assessment
time consumes the same budget by default. If a required category is unresolved,
ID-04A emits `workload_time_allocation_missing`; missing time is never treated as
zero. A lesson/module aggregate must not be added again when its category
allocations already account for that time.

## Status and findings

`workload_budget_policy@0.1` uses whole-minute estimates and a 10% slack
threshold for `near_limit` (exactly full is `within_budget`). Over-budget plans
produce the non-fatal quality finding `workload_time_budget_exceeded` with
declared, planned, and over-budget minutes. Existing quality findings remain
independent and are not suppressed.

The additive `AssessmentSpec.estimated_minutes` field is optional. It is a
planning estimate only; no duration is inferred from task complexity.

## Planner boundary and compatibility

Structured planner patch version `0.3.2` instructs CoursePlanner and
LessonPlanner to receive and respect the declared budget, include assessment
time, use conservative whole-minute values, and expose unresolved allocation.
Prompt versions `0.3.1` and earlier remain unchanged for replay.

The deterministic artifact set is under
`backend/test/results/instructional-design-id-04a-workload-semantics/` and uses
zero external model calls. The five cross-domain fixtures exercise varied
activity patterns without domain-specific validation logic.

## Limitations

This milestone does not estimate cognitive load, schedule sessions, optimize
learning, or prove that a learner can finish within the budget. It only makes
declared-versus-planned workload explicit and auditable.
