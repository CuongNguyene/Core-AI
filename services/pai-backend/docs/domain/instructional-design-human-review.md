# ID-02 Smoke-2 human review results

Three SME reviewers completed all six condition-blind Smoke-2 packets. The
raw submissions remain under
`backend/test/results/instructional-design-smoke-2-live-3/blinded-review/reviewer_1/`,
`reviewer_2/`, and `reviewer_3/`. The researcher-only condition join and the
machine-readable aggregation are in
`blinded-review/human-review-summary.json`.

## Review completeness and separation

- 18 reviews were received: 3 reviewers × 6 packets.
- Every review contains all 10 rubric scores, prerequisite acceptance, and
  edit-effort information.
- Reviewers did not receive condition labels; the private mapping was joined
  only after all submissions were present.
- Technical/traceability observations are not folded into pedagogical scores.
- Reviewer comments are qualitative evidence, not a composite score or a
  winner declaration.

## Descriptive result after the blind join

| Condition | Review observations | Mean rubric score | Technical issue observations | Prerequisite decisions | Edit effort |
|---|---:|---:|---:|---|---|
| One-shot | 9 | 3.51 | 27 | 3 accept, 6 revise, 0 reject | 1 none, 3 minor, 5 moderate |
| Structured | 9 | 3.67 | 40 | 1 accept, 7 revise, 1 reject | 0 none, 2 minor, 6 moderate, 1 major |

These are descriptive numbers from three fixtures and three reviewers. They do
not establish that structured is better. The structured packets had more
traceability observations, while the rubric means were close and the
reviewers' qualitative judgements were mixed by fixture.

## What reviewers consistently saw

The positive pedagogical signal is real: most reviews answered the special
question affirmatively or affirmatively with reservations. Common strengths
were coherent sequencing, observable objectives, and assessments that were
directionally aligned with the target workflow.

The recurring design problems were also consistent:

- time budgets that attempt too much for the stated learner state;
- assessment tasks used as the only practice, leaving no independent evidence;
- prerequisite sets that are too broad or insufficiently minimal;
- missing integrated practice for the final combined performance;
- structured reference/shape defects such as empty `module.lesson_ids`, mixed
  entity types in `prerequisite_refs`, and orphan modules/lessons.

The last group is an upstream generation/interface problem. It is not a reason
to weaken the deterministic quality gate. The human review supports keeping
machine-validity and pedagogical quality as separate axes, then fixing
cross-stage ID and dependency propagation before another smoke.

## Milestone decision

ID-02 human evaluation is complete for the six-artifact calibration round.
Structured design quality remains **NEEDS ITERATION**. Prompt v0.3 should be
based on these observed root causes and should preserve the existing boundaries:
AssessmentDesigner cannot invent assessed capabilities, CoursePlanner must use
supplied objective IDs, and LessonPlanner must use supplied module/objective
IDs. No TEXT-01 generation or quality-gate relaxation follows from this small
sample.

