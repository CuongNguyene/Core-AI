# ID-02 Smoke-2 blinded human review guide

This review covers six generated instructional-design artifacts from Smoke-2.
The packets are intentionally condition-blind. Use only the packet assigned to
you and do not open the private mapping, raw results, manifests, or failure
analysis while scoring.

## Review order

1. Open `reviewer-packets/review-NNN.json`.
2. Read the brief, objectives, assessments, prerequisites, course outline, and
   lessons once without scoring.
3. Record machine-validity and traceability observations separately from the
   pedagogical judgement.
4. Score each rubric dimension from 1 to 5 and write a short evidence-based
   rationale. Do not infer whether the packet came from one-shot or structured.
5. Decide whether the proposed prerequisites are acceptable, record edit effort,
   and answer the special question.
6. Save the completed response as `reviewer-submissions/review-NNN.json`.

The special question is mandatory:

> Ignoring machine traceability or schema issues, is this instructional design
> pedagogically reasonable?

This question must be answered independently of any orphan IDs, missing
references, quality-gate findings, or other technical defects.

## Technical / traceability review

Record observations only; do not turn them into a pedagogical score. Useful
categories are:

- `id_reference_drift`: an ID is rewritten, replaced, or points to an unknown
  entity;
- `orphan_lesson` / `orphan_module`: a generated entity has no valid supplied
  objective/module reference;
- `assessment_scope_creep`: an assessment introduces a capability not contained
  in the supplied objectives;
- `prerequisite_provenance`: a model-proposed prerequisite is presented as
  confirmed rather than candidate;
- `schema_or_shape`: required fields, enum values, or object shape are invalid;
- `other`.

For each issue record the entity/field, a short description, severity
(`info`, `warning`, `error`, or `blocking`), and whether the validator appears
correct (`true`, `false`, or `null`). Do not repair the artifact in the review
response.

## Pedagogical rubric

Use 1 = poor, 2 = weak, 3 = acceptable, 4 = good, 5 = strong.

| Dimension | Review question |
|---|---|
| `objective_measurability` | Can learner performance be observed and judged from the objective and criteria? |
| `objective_assessment_alignment` | Does the assessment actually measure the stated objectives? |
| `evidence_validity` | Would the proposed evidence support a defensible judgement of learning? |
| `cognitive_alignment` | Do objective, activity, and assessment use an appropriate cognitive level? |
| `prerequisite_quality` | Are prerequisites relevant, minimal, and appropriately qualified? |
| `sequence_coherence` | Does the progression make sense for the desired performances? |
| `instruction_assessment_alignment` | Do instructional activities prepare learners for the assessment? |
| `under_teaching` | How severe is under-teaching (missing explanation, practice, or support)? Use 1 = no issue and 5 = severe under-teaching. |
| `over_teaching` | How severe is over-teaching (unnecessary breadth, depth, or content)? Use 1 = no issue and 5 = severe over-teaching. |
| `overall_edit_effort` | How much design editing would be needed before a human could approve it? Use 1 = trivial and 5 = rewrite-level effort. |

Do not average these into a composite score. The rubric is descriptive and
supports calibration; it does not declare a winner.

## Prerequisite acceptance

Choose one:

- `accept`: all proposed prerequisites are acceptable as written;
- `accept_with_revisions`: the set is useful but one or more items need wording,
  ordering, or status changes;
- `reject`: the prerequisites are materially irrelevant, unsafe, or unusable;
- `uncertain`: the packet does not provide enough information to decide.

Model-proposed prerequisites are candidates, never confirmed facts. Record
which prerequisite IDs were accepted or rejected and why.

## Edit effort

Choose the overall level from `none`, `minor`, `moderate`, `major`, or
`rewrite_required`. Count changed objectives, assessments, prerequisites,
modules, and lessons when possible. Counts are reviewer estimates, not a
diff against a hidden reference.

Keep technical and pedagogical notes separate. A packet may be pedagogically
reasonable while technically invalid, or technically traceable while needing
substantial instructional redesign.

