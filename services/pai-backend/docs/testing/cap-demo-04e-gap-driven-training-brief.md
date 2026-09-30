# CAP-DEMO-04E — Learning Need to GAP_DRIVEN Training Brief

## Architecture boundary

`GapDrivenTrainingBriefComposer` is a request-scoped application composition
boundary. It consumes canonical `LearningNeedProfile` items and returns a
`GapDrivenTrainingBriefProjectionResult`; it does not introduce a new
first-class plan artifact or persistence model.

The existing persisted `LearningPath` remains unchanged. It is a
post-instructional-generation artifact containing objectives, lessons, modules,
blueprints, and generated learning objects. CAP-DEMO-04E does not populate or
persist that model.

## Routing policy

Only an item satisfying both conditions enters the `TrainingBrief`:

```text
learning_eligibility = READY_FOR_LEARNING
resolution_type = learning
```

All other items become bounded `ResolutionAction` values and remain outside
instructional content scope:

- `EVIDENCE_MISSING` / `verification` → verification action
- `NEEDS_VERIFICATION` / `verification` → verification action
- `credential` → credential action
- `experience_exposure` → experience-exposure action
- `assessment`, `non_learning`, or `unresolved` → corresponding action

No active learning needs produces `training_brief = null` with reason
`no_learning_eligible_needs`. This avoids translating missing evidence or an
unresolved qualification into an invented course.

## Brief composition

The brief contains only source-grounded fields supported by the current
`TrainingBrief` contract. Desired outcomes are copied from existing target
behaviors. Duration, language, modality, timeline, objectives, modules,
lessons, prerequisites, and learner preferences are not inferred. No LLM or
course-generation call is made.

The result preserves candidate reference, exact role target reference,
capability-analysis reference/version, source learning-need references, source
gap references, and composition policy `gap_driven_training_brief@0.1`.

## Governance and future compatibility

`PREVIEW` input remains `PREVIEW` and emits a provisional warning. The composer
does not create an official assignment, enrollment, or course-authoring
request. The future integration boundary is:

```text
GapDrivenTrainingBriefProjectionResult.training_brief
→ CourseAuthoringRequestCreate(mode=GAP_DRIVEN)
→ instructional design
→ CurriculumPlan / generated LearningPath
```

That transport and generation flow is intentionally outside CAP-DEMO-04E.

## Runtime evidence

For `cap-demo-04b-20260911-runtime-2`, the source contains three
`not_found_in_evidence` assessments. The 04D projection yields three
`EVIDENCE_MISSING`/verification items, zero `READY_FOR_LEARNING` items, and
therefore no TrainingBrief and three verification actions. Re-composition is
deterministic and does not persist a duplicate artifact.

No migration is required.
