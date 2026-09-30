# INTEGRATION-01B — Learning Result Contract

## LearningResultEvent v1

LMS is the fact owner and event producer. PAI is the consumer/evaluator. The event can be delivered through an MVP REST intake and later through a broker without changing its schema.

```json
{
  "event_name": "learning.result.completed.v1",
  "event_id": "evt_01J...",
  "schema_version": "v1",
  "occurred_at": "2026-08-17T09:30:00Z",
  "correlation_id": "01J...",
  "idempotency_key": "lms:attempt:lms-attempt-uuid:1",
  "actor": {
    "external_user_id": "lms-user-uuid",
    "source_system": "lms",
    "organization_ref": "org:pending-authority"
  },
  "course": {
    "course_instance_id": "lms-course-uuid",
    "source_blueprint_id": "bp_123",
    "source_blueprint_version": "1.0.0"
  },
  "activity": {
    "activity_instance_id": "lms-quiz-uuid",
    "activity_type": "QUIZ",
    "source_assessment_id": "asmt_01",
    "source_assessment_version": "1.0.0"
  },
  "completion": {
    "enrollment_status": "COMPLETED",
    "progress_percent": 100,
    "completed_at": "2026-08-17T09:29:00Z"
  },
  "assessment_outcome": {
    "attempt_id": "lms-attempt-uuid",
    "score": 82.5,
    "passed": true,
    "attempted_at": "2026-08-17T09:28:00Z"
  }
}
```

Required: event identity/version/time, actor reference, LMS course instance, milestone status, and correlation/idempotency controls. Activity and assessment outcome are required only when the event describes an activity/attempt. Raw answers, question keys, LMS JWTs, and learner PII beyond the reference contract do not cross by default.

## PAI processing rules

- PAI accepts only the first valid event for an idempotency key; replay returns an idempotent receipt.
- PAI rejects an unknown contract version, untrusted source, tenant mismatch, invalid projection reference, or malformed outcome without exposing internal state.
- A delivery result can become a PAI evidence input only under explicit policy and source-assessment alignment.
- It cannot create, verify, revoke, or expire a PAI competency by itself.

## CompetencyResult v1

```json
{
  "result_id": "comp-result_01",
  "schema_version": "v1",
  "learner": {
    "external_user_id": "lms-user-uuid",
    "source_system": "lms",
    "organization_ref": "org:pending-authority"
  },
  "competency_ref": "competency:rt-image-interpretation",
  "evaluation_status": "EVALUATION_PENDING",
  "evidence_references": {
    "type": "opaque_reference",
    "display_only": true,
    "persist_allowed": false,
    "owner": "PAI",
    "values": ["evidence:derived:evt_01J..."]
  },
  "source_learning_result_event_id": "evt_01J...",
  "evaluated_at": "2026-08-17T09:31:00Z"
}
```

Allowed `evaluation_status` values are `NOT_EVALUATED`, `EVALUATION_PENDING`, `INSUFFICIENT_EVIDENCE`, `REQUIRES_REVIEW`, and `EVALUATED`. `VERIFIED` is intentionally excluded: it is a PAI competency-record state reached only by governed assessment/decision workflow.

## Evidence-reference boundary

LMS may receive an evaluation status, competency-result status, and an opaque
display-only evidence reference only when an authorized UI/workflow needs it.
The `evidence_references` field is PAI-owned metadata: it is not an LMS
entity, foreign key, cache record, or replication payload.

LMS MUST NOT persist raw evidence, evidence documents, evidence IDs as
LMS-owned entities, source locators, provenance chains, extraction metadata,
CV/JD content, or PAI policy references. LMS MUST NOT create a foreign key to
PAI evidence storage or dereference an opaque value to retrieve raw evidence.
PAI remains the source of truth for evidence lifecycle, provenance, source
locators, and validation policy.
