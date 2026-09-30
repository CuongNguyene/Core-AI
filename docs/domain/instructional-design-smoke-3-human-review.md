# ID-02C Smoke-3 blinded human review

The six raw submissions are preserved under
`backend/test/results/instructional-design-smoke-3-live-network-3/blinded-review/reviewer_submission/`.
The condition join uses the researcher-only private mapping and was performed
after review. The reviewer files contain no condition labels.

This round contains one reviewer (`gemini-sme-01`) scoring all six packets,
not three independent reviewers. It is therefore a calibration round, not an
inter-rater or statistical comparison.

| Condition | Packets | Mean rubric score | Technical observations | Special question |
|---|---:|---:|---:|---|
| One-shot | 3 | 3.667 | 1 | 1 yes, 1 yes with reservations, 1 no |
| Structured v0.3 | 3 | 3.633 | 5 | 2 yes, 1 marginally reasonable |

The raw review scores and joins are in
`blinded-review/human-review-summary.json`.

## What the review confirms

- The pedagogical signal is generally positive, but time/scope feasibility is
  the recurring concern. Python one-shot is the only packet judged “No” on the
  special pedagogical question.
- Structured Model Monitoring has the same `required_capability_refs`
  assessment-ID problem already found by the deterministic RCA. This is an
  AssessmentDesigner scope/reference issue; it is not evidence to weaken the
  validator.
- Python one-shot contains an orphan lesson (`obj-teach-pandas-basics`) that
  is not in the module's derived `lesson_ids`.
- Python structured and Technical Communication structured use summative
  assessment IDs in `formative_assessment_ids`. This is a real boundary gap in
  the current schema/gate and should be handled as a separate targeted change;
  it was not silently changed in this review aggregation.
- Prerequisite feedback is mixed but consistently asks for minimality and
  realistic entry assumptions.

No winner is declared. This round does not authorize TEXT-01 or a quality-gate
exception.
