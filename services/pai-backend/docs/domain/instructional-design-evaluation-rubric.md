# Instructional Design Evaluation Rubric

## Deterministic metrics

For each snapshot, record quality-gate pass, findings by code/severity,
objective/assessment coverage, unresolved prerequisites, cognitive-demand
mismatches, prerequisite violations, and assessment dependency failures. These
are policy signals, not SME approval.

## Human rubric

Reviewers score objective measurability, objective-assessment alignment,
cognitive alignment, evidence validity, prerequisite quality, sequence
coherence, instruction-assessment alignment, under-teaching, over-teaching,
and overall edit effort. Each uses 1 poor, 2 weak, 3 acceptable, 4 good, or 5
strong. For under-/over-teaching, the score indicates the issue level under the
study protocol; it is not merged into a composite score.

`HumanEvaluation` requires `source="human"`, reviewer ID, time, notes, and
edit effort: `none`, `minor`, `moderate`, `major`, or `rewrite_required`.
Optional counts capture objectives, assessments, prerequisites, modules, and
lessons changed.

## Blinded review and limitations

The blinded payload contains an opaque `review_id`, a reviewable design
artifact, rubric version, and this additional question:

> Ignoring machine traceability or schema issues, is this instructional design
> pedagogically reasonable?

It excludes run ID, condition, prompt/schema provenance, generation metadata,
and quality-gate report. The private `review_id → run_id/condition` mapping is
stored separately and must not be shared with reviewers. No LLM score is stored
as human review. ID-02 produces no semantic edit-distance score, weighting
policy, composite score, winner, significance claim, factual-content result, or
learner-outcome result.
