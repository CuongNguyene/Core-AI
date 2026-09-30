# PR-006: Assessment & Competency Decision Core Design

## Goal

Triển khai tầng 3 của modular monolith: assessment template/rubric/task,
submission, scoring interface, SME review và competency decision audit được.
Quyền verification dùng RBAC + scoped delegation, không dùng role ghép hay
automatic competency verification.

## Boundaries

- `authorization` là minimal development subject store, không phải IAM
  production. UUID actor resolve từ header qua persistence; một active org/user.
- `assessment` sở hữu template, rubric version, task, submission, score proposal
  và SME review. Task types chỉ có placeholder `quiz`, `practical`, `case`.
- `competency` sở hữu immutable decision history và derived competency state.
- `audit` là append-only adapter; raw answer/PII/prompt/model output bị cấm.
- AI scoring chỉ là interface/mock; implementation model phải qua gateway/privacy
  và human review. Credential không được tạo.

## Data and lifecycle

`AssessmentTemplate` và `Rubric` immutable versioned, chứa competency ID, risk
classification, `validity_days`, `reassessment_lead_days`, task definitions và
rubric criteria. Fixture policy mặc định 365/30 days.

`AssessmentSubmission` tham chiếu template/rubric/task/evidence locator; owner
learner submit. `AssessmentDecision` giữ submission, rubric/policy version,
assessor, reviewer/verification references và evidence IDs. Completion không tạo
decision hay competency status.

`CompetencyRecord` giữ state hiện tại còn `CompetencyDecision` immutable lưu
previous/new state, evidence, rubric, policy, delegation (nếu verify), validity
và reassessment. Transition hợp lệ như ADR-0011; invalid/stale fail closed.

## Authorization

Development adapter tạo `ActorContext(UUID, one active organization, roles)` từ
database. Basic role permission dùng assignment active/time-valid. Delegation
`competency.verify` cần SME + active scope/org/time match; self-assessment,
self-delegation, self-verification và conflict policy đều deny. `HIGH_RISK`
enforce four-eyes; `LOW_RISK` allow same assessor/verifier khi delegation hợp lệ.

`CompetencyAuthorizationPolicy` được assessment/competency application service
gọi, nên REST/worker/CLI không bypass. Policy denial trả safe reason code và ghi
audit, không disclose sensitive scope details.

## API

Development-only API không nhận actor/role/org trong body. Minimum endpoints:

- Delegation: create/get/list-by-user/activate/suspend/revoke; transitions body
  `{expected_version, reason}`.
- Assessment: `POST/GET /assessment-templates`, `POST/GET
  /assessment-submissions`, `POST /assessment-decisions`. Scorer is internal;
  SME creates a decision from a submission/reference, not a client score.
- Decision: mark assessed, request verification, verify, return for review,
  require reassessment, revoke verification. Không có generic `set_status`.

Owner reads own submissions/results published by policy; SME/ADMIN access only
through roles/scopes. All errors use ADR-0003 envelope.

## Persistence and audit

SQLAlchemy runtime repositories own writes. Versioned transitions select/update
with expected version and append event inside one transaction; audit failure rolls
back state. Index active delegation `(user_id, permission, organization_id,
status)` and validity window; unique/index role/membership active lookup. Audit
contains IDs, versions, policy/rubric, prior/new state, reason code/correlation
and outcome only.

## Test matrix

- UUID identity: valid/unknown/disabled/missing/invalid/multiple membership/org
  inactive; no legacy string fallback or request role trust.
- Delegation: admin management, no self grant, lifecycle/stale/rollback/scope/
  org/time denial.
- Decision: SME assessed, delegated SME verify, all forbidden roles/self subject,
  invalid state, completion no state change, validity/reassessment, revoke.
- SoD: low-risk same actor allowed; high-risk requires different verifier.
- Audit: expected event metadata, delegation ID on verify, safe denial and no raw
  content; deterministic golden fixtures.

## Out of scope

ABAC engine, OPA/Cedar, IdP/SSO, password/MFA, multi-org selector, committee
approval, credential issuance, proctoring, automatic verification and production
AI scoring.
