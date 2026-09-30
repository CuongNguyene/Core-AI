# CAP-DEMO-04F — GAP_DRIVEN Course Authoring Integration

## Boundary

CAP-DEMO-04F connects the output of `GapDrivenTrainingBriefComposer` to the
existing `CourseAuthoringService`. It does not create a direct capability-gap
course generator or a second instructional-design pipeline.

```text
CapabilityGapProfile
  -> LearningNeedProfile
  -> GapDrivenTrainingBriefProjectionResult
  -> GapDrivenCourseAuthoringAdapter
  -> CourseAuthoringRequest(mode=GAP_DRIVEN)
  -> existing CourseAuthoringService
```

Only `READY_FOR_LEARNING` needs with `resolution_type=learning` are present in
the `TrainingBrief` and `learning_need_refs` sent to course authoring. The
parallel `ResolutionAction` values (verification, credential,
experience-exposure, evidence-missing, and unresolved) remain outside the
course scope.

## Request mapping

`GapDrivenCourseAuthoringAdapter` maps the already-composed `TrainingBrief`
without an LLM or a second source lookup. The existing request fields are
used as follows:

- `mode=GAP_DRIVEN`;
- `training_brief` is preserved as the instructional authority;
- `learning_need_refs` contains only included learning needs;
- `objective_refs` uses the existing `objective-<learning-need-ref>` learning
  authoring projection so downstream GAP_DRIVEN planning receives canonical
  objective context without creating or persisting synthetic objectives;
- `title` is the composed brief goal because the request contract requires a
  title;
- learner references are optional and remain empty when this is a preview
  authoring request.

The existing `constraints` JSON field carries safe source metadata because the
current request contract has no separate provenance field. It contains policy,
usage mode, candidate/role/analysis references, and included source need
references. It never contains CV/JD text, prompts, provider responses, or
provider-private metadata.

## Preview governance

`source_usage_mode=preview` is retained in request constraints and
`official_training_assignment=false` is explicit. Creating a course-authoring
request does not enroll a learner, create an official capability decision, or
start provider generation. Generation remains an explicit existing
`/generate` action and follows the normal course-authoring pipeline.

## No eligible needs

When the composer returns `training_brief=None`, the integration returns
`no_learning_eligible_needs` and does not call `CourseAuthoringService`.
Consequently, no request, provider call, enrollment, or placeholder training
brief is created.

## Idempotency and persistence boundary

The current `CourseAuthoringRequest` contract has no idempotency-key field or
unique source identity. This milestone therefore reuses the existing service
and persistence behavior without inventing a parallel idempotency subsystem or
changing the database. The adapter mapping is deterministic; any future
request-level idempotency must use the course-authoring service's canonical
contract when that contract gains the required identity field.

## Non-goals

- no `LearningPath` schema or persistence change;
- no curriculum or lesson generation change;
- no automatic provider call;
- no enrollment or mandatory assignment;
- no conversion of resolution actions into instructional scope;
- no migration or new API endpoint.
