# DEPRECATED

Status: `DEPRECATED`

This document is preserved for historical reference. Do not implement from
this document. Use the canonical v1 contract set:

- `docs/domain/integration/01b-api-contract-design.md`
- `docs/domain/integration/01b-course-blueprint-contract.md`
- `docs/domain/integration/01b-learning-result-contract.md`
- `docs/domain/integration/01b-identity-contract.md`

Canonical version: `v1`

---

# Learning Result contract (`INTEGRATION-01B`)

Learning results describe participation and assessed course performance. They
are not source evidence and do not prove a competency decision.

## Shape

```json
{
  "result_id": "lr-...",
  "learner_id": "...",
  "course_id": "...",
  "source_blueprint_id": "...",
  "objective_results": [{
    "objective_id": "...",
    "status": "attempted|passed|not_passed|unresolved",
    "assessment_refs": ["..."],
    "score": 0.0,
    "recorded_at": "2026-01-01T00:00:00Z"
  }],
  "completion_status": "IN_PROGRESS|COMPLETED|FAILED|REVOKED",
  "provenance": {
    "attempt_ids": [],
    "grading_policy_id": "...",
    "grading_policy_version": "..."
  }
}
```

## Semantic boundaries

- `passed` means the LMS assessment policy accepted that attempt; it does not
  mean PAI capability status is `VERIFIED`.
- A quiz answer, attendance event, or course certificate is not a CV/JD claim,
  Evidence Graph item, or source credential assertion.
- Mapping a result back to a capability requires a separate PAI assessment
  decision workflow, explicit evidence policy, and reviewer/governance action.
- Revocation or correction of an LMS result must not mutate immutable source
  extraction profiles or accepted evidence.

## Read/write ownership

The LMS owns result lifecycle and learner visibility. PAI may consume a result
as an input candidate for a future assessment workflow, retaining the result
ID and policy provenance. No integration endpoint may silently convert a result
into a capability gap closure, official competency decision, or credential.
