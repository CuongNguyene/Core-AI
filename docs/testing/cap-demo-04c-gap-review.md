# CAP-DEMO-04C — Capability Gap Review Workspace

## Boundary

CAP-DEMO-04C is a read-only review projection over a persisted capability-gap
portfolio. It does not change scoring, portfolio persistence, verification
approval, canonical claims, or learning-path behavior.

The projection is built from the exact `current_role.target_id` and
`current_target_version` recorded in the portfolio. It does not resolve role
requirements from the latest role-profile version. If that version cannot be
resolved, or an assessment requirement cannot be resolved in it, projection
fails closed.

## Review information architecture

The reviewer unit is `RequirementAssessment`, not `TargetGap`. The read-only
workspace presents:

- a preview/governance banner;
- summary counts for total, matched, insufficient, verification, context
  mismatch, and not-found-in-evidence assessments;
- one selectable assessment item per persisted assessment;
- requirement metadata, decision explanation, candidate evidence, role
  provenance, and verification state;
- a verification queue linked back to the owning assessment.

`not_found_in_evidence` is intentionally worded as “No relevant evidence was
found”. It must also state that this does not prove the candidate lacks the
capability.

## Governance and privacy

The projection remains preview-only. `PreviewReadiness` is exposed as the
existing safe governance contract and the UI does not expose Learning Path or
other downstream mutation actions in this review state.

The learner-safe boundary remains authoritative. This projection does not add
answer keys, raw CV/JD text, prompts, provider responses, source references,
generation metadata, or official competency scores.

## Compatibility

The `review` field is additive and optional in the integration response, LMS
adapter, and frontend types. Historical portfolios without a usable review
projection continue to use the existing response shape. No database migration
or new endpoint is introduced.

## Long-term boundary

`gaps[]` remains available as a compatibility projection. Future learning-need
or learning-path work must consume the review/governance boundary explicitly;
CAP-DEMO-04C does not approve or materialize those downstream artifacts.
