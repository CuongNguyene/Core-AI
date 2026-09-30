# PR-008 Credential Policy & Issuance Design

## Goal

Tạo vertical slice credential policy, type-specific eligibility, human approval,
issuance, expiration/revocation, public verification và immutable audit mà không
biến course completion thành competency hoặc mở rộng sang LMS delivery.

## Scope and boundaries

Credential types và authoritative inputs:

| Type | Required authority in PR-008 runtime | Result without it |
| --- | --- | --- |
| `COMPLETION` | Registered `CourseCompletionAssertionProvider` | `NOT_EVALUABLE` / `AUTHORITATIVE_COMPLETION_ASSERTION_UNAVAILABLE` |
| `LEARNING_ACHIEVEMENT` | Registered `LearningOutcomeAssertionProvider` | `NOT_EVALUABLE` / `AUTHORITATIVE_LEARNING_OUTCOME_ASSERTION_UNAVAILABLE` |
| `COMPETENCY` | Verified competency plus decision/evidence/rubric references | Continue policy evaluation |

The unavailable completion/achievement providers are runtime production
adapters. Tests use deterministic fakes, never runtime fixtures or public APIs.

No endpoint accepts raw assertion, course completion boolean, assessment result,
competency level, rubric, evidence or actor role/organization. Actor context is
resolved by ADR-0010. Source reference is only a provider lookup key and must
resolve to the policy type, subject and organization.

## Domain model

- `CredentialPolicy`: stable `policy_id`, immutable version, credential type,
  lifecycle `DRAFT | ACTIVE | SUPERSEDED | RETIRED`, source/evidence rules,
  duplicate rule, validity period, evaluator/policy version and approval
  separation requirement. Runtime PR-008 only resolves active registered
  policies; policy authoring is not exposed.
- `EligibilityDecision`: evaluation ID, policy/version, subject/org, status
  `ELIGIBLE | INELIGIBLE | NOT_EVALUABLE | REQUIRES_REVIEW`, safe reason code,
  source references and evaluator version.
- `CredentialRequest`: immutable evaluation snapshot and lifecycle
  `PENDING_APPROVAL | APPROVED | REJECTED | ISSUED | EXPIRED | REVOKED`; it is
  created only when evaluation is `ELIGIBLE`. Other outcomes are audit-only
  evaluations and do not create an issuable request.
- `Credential`: issued immutable credential ID, request/policy snapshot,
  credential type, issuer organization, issued/validity dates and status. It
  never stores raw assessment/evidence, response body or learner PII.

## Authorization and state machine

`CredentialAuthorizationPolicy` is an application service. It resolves active
delegations by UUID actor, organization, permission, policy scope and time:

```text
ELIGIBLE evaluation
  → PENDING_APPROVAL --credential.approve--> APPROVED
                        └--credential.approve--> REJECTED
APPROVED --credential.issue--> ISSUED
ISSUED --valid_until reached, credential.revoke sweep--> EXPIRED
ISSUED --credential.revoke--> REVOKED
```

Invalid transitions, expired/suspended/revoked delegation, cross-organization
access, self-approval, self-issuance, stale expected version, duplicate active
credential and audit failure all fail closed. `APPROVED` never implies issued;
`REVIEWED`/completion never creates a competency credential.

The existing delegation data model generalizes its permission literal to the
four explicit values `competency.verify`, `credential.approve`,
`credential.issue`, `credential.revoke`. Credential scopes are policy IDs; no
new basic role is created. For a competency credential, default policy requires
requester, approver and issuer to be distinct. Completion/achievement policies
use their declared approval rule when authoritative providers exist in a future
slice.

## Evaluators

```python
class CredentialEligibilityEvaluator(Protocol):
    async def evaluate(
        self, request: CredentialEvaluationInput
    ) -> EligibilityDecision: ...

class CompletionCredentialEvaluator(CredentialEligibilityEvaluator): ...
class LearningAchievementCredentialEvaluator(CredentialEligibilityEvaluator): ...
class CompetencyCredentialEvaluator(CredentialEligibilityEvaluator): ...
```

The competency evaluator requires matching subject/org, `VERIFIED` status,
non-expired validity, a decision history with evidence/rubric/policy reference,
acceptable rubric version, valid verification delegation reference and no active
duplicate when policy forbids it. Conflict/missing reference yields
`REQUIRES_REVIEW` or `INELIGIBLE` according to policy, never an inferred pass.

## API

- `POST /credential-requests`: evaluates an exact active policy version.
  `ELIGIBLE` returns a `PENDING_APPROVAL` request; other outcomes return a safe
  evaluation response with no issue path.
- `GET /credential-requests/{request_id}`: requester or credential authority
  in the same organization reads safe snapshot/status.
- `POST /credential-requests/{request_id}/approve`: transition with
  `expected_version`, delegated approver and immutable audit.
- `POST /credential-requests/{request_id}/reject`: same authority/locking,
  safe reason code only.
- `POST /credential-requests/{request_id}/issue`: delegated issuer issues from
  exactly one approved request. It returns a credential snapshot.
- `POST /credentials/{credential_id}/revoke`: delegated revoker, expected
  version and safe reason code. `POST /credentials/{credential_id}/expire`
  may only persist `EXPIRED` after `valid_until` and uses the same revocation
  authority in the MVP sweep adapter.
- `GET /credentials/{credential_id}/verify`: public minimum verification;
  returns no learner identity or underlying evidence.

All errors follow ADR-0003. Routes must state 401/403/404/409/422/503 safe error
responses in OpenAPI. There is no policy-create API, credential self-issue API
or endpoint to create a completion/outcome assertion.

## Persistence and audit

SQLAlchemy is runtime persistence and in-memory adapters support unit tests.
Create `credential_policies`, `credential_requests`, `credentials` and
`credential_audit_events`. Store safe ID/version references as JSON only where
the schema varies by credential type; use columns/FKs for actor, organization,
policy/request/credential IDs, status, version and dates.

State transition, credential issuance (request + credential) and audit append
are one transaction. Audit insert failure rolls all of it back. Request and
credential records use optimistic locking / row lock. Audit is append-only and
contains action, reason code, actor/delegation IDs, policy/evaluator versions,
state/version and correlation ID, but never raw evidence, assessment content,
prompt, PII or source payload.

## Test strategy

- Schema/state tests reject unknown type, inline assertions, invalid date window
  and invalid lifecycle transition.
- Evaluator tests cover unavailable providers, test fake authoritative
  assertions, wrong course/outcome version, unrelated assessment, verified,
  assessed, expired, revoked evidence/rubric and conflicts.
- Authorization tests cover no delegation, scope/org/time mismatch, self
  approval/issuance, permitted action and UUID actor audit metadata.
- Repository tests prove policy/version constraints, no duplicate active
  credential, transaction rollback on audit failure and immutable audit.
- API tests cover request/evaluate, approval/rejection, issue/revoke/expire and
  public verification redaction.
- Golden harness covers all cases in the attached acceptance criteria plus a
  deterministic re-evaluation of identical input/policy.

## Explicit non-goals

- No LMS enrollment, delivery, progress, completion record or learning-outcome
  production owner.
- No competency certificate based solely on course completion or AI score.
- No automatic issuance when evaluation is non-eligible/not-evaluable/review.
- No password/OIDC/SSO, new basic role, microservice, external AI, credential
  QR/signing, external registry or renewal system.
