# Codex Prompt — PAI Platform: RBAC + Scoped Delegation cho xác minh năng lực

Bạn đang làm việc trong repository PAI Platform.

## 1. Bắt buộc đọc trước khi code

Đọc đầy đủ:

- `AGENTS.md`
- `MEMORY.md`
- `docs/domain/three-layer-assessment.md`
- `docs/security/privacy-gateway.md`
- các ADR hiện có liên quan đến identity, authorization, assessment, competency decision và audit
- code hiện tại của các mô-đun:
  - identity/authorization
  - assessment
  - competency
  - audit
  - organization
  - database/repository

Không viết code trước khi báo cáo ngắn:

1. Hiện trạng authorization hiện có.
2. Những điểm chưa khớp với yêu cầu dưới đây.
3. Migration/API/ADR cần bổ sung.
4. Kế hoạch thay đổi theo các commit nhỏ.
5. Blocker nếu có.

## 2. Mục tiêu

Triển khai mô hình phân quyền MVP:

> RBAC + Scoped Delegation

Không xây ABAC tổng quát trong PR này.

Mô hình phải bảo đảm:

- Role cơ bản quản lý nhóm người dùng.
- Permission đặc biệt quản lý thẩm quyền xác minh năng lực.
- Delegation giới hạn theo tổ chức, phạm vi chuyên môn và thời hạn.
- Policy Service kiểm tra quyền tại application layer.
- Mọi hành động cấp quyền, chấm, xác minh, thu hồi và yêu cầu đánh giá lại đều có audit.
- Quản trị hệ thống không đồng nghĩa thẩm quyền chuyên môn.
- SME thông thường chỉ có thể đưa quyết định đến `ASSESSED`.
- Chỉ SME có delegation `competency.verify` còn hiệu lực mới được chuyển `ASSESSED/PENDING_VERIFICATION` sang `VERIFIED`.

Tên nghiệp vụ chính thức:

> SME được tổ chức ủy quyền xác minh năng lực

Không dùng tên role ghép `admin+sme`.

## 3. Vai trò cơ bản

Triển khai hoặc chuẩn hóa bốn role:

```text
ADMIN
SME
REVIEWER
LEARNER
```

### ADMIN

Được phép:

- quản lý người dùng;
- gán/thu hồi role theo policy;
- quản lý tổ chức;
- quản lý delegation nếu có quyền quản trị tương ứng;
- xem audit theo scope.

Không mặc định được:

- chấm assessment;
- đưa competency sang `ASSESSED`;
- chuyển competency sang `VERIFIED`;
- cấp chứng nhận năng lực.

### SME

Được phép trong đúng competency scope:

```text
assessment.view
assessment.review
assessment.score
competency.mark_assessed
competency.request_reassessment
```

Không mặc định có:

```text
competency.verify
```

### REVIEWER

Được phép:

```text
extraction.review
extraction.correct
extraction.accept
matching.review
matching.request_rerun
```

Không mặc định được chấm hoặc xác minh năng lực.

### LEARNER

Được phép:

- xem hồ sơ của mình;
- tham gia assessment;
- nộp bài;
- xem lộ trình học;
- xem kết quả được phép công bố;
- gửi yêu cầu review/appeal theo policy.

Không được tự chấm hoặc tự xác minh.

## 4. Permission đặc biệt

Thêm permission:

```text
competency.verify
```

Permission này không gắn mặc định với `ADMIN` hoặc `SME`.

Một người chỉ có quyền verify khi đồng thời:

```text
has_role(SME)
AND has_active_delegation(competency.verify)
AND delegation.organization_id == target.organization_id
AND competency nằm trong delegation scope
AND delegation đang trong thời gian hiệu lực
AND actor không phải subject
AND không vi phạm conflict-of-interest policy
AND decision đang ở trạng thái hợp lệ
```

## 5. Scoped Delegation

Tạo entity và persistence cho delegation.

### Trường tối thiểu

```text
id
user_id
permission
organization_id
competency_scope
valid_from
valid_until
status
granted_by
reason
created_at
activated_at
suspended_at
revoked_at
revoked_by
revocation_reason
version
```

### Trạng thái

```text
DRAFT
ACTIVE
SUSPENDED
EXPIRED
REVOKED
```

### Quy tắc

- Chỉ `ACTIVE` và còn hiệu lực thời gian mới dùng được.
- Người dùng không được tự cấp delegation cho mình.
- Người cấp delegation phải có permission quản trị phù hợp.
- Delegation bị thu hồi không xóa lịch sử verification cũ.
- Delegation hết hạn phải bị từ chối ngay cả khi token cũ còn role SME.
- Mọi transition dùng optimistic locking qua `expected_version`.
- Mọi state transition và audit phải cùng transaction.
- Không hard-delete delegation đã từng được sử dụng.

## 6. Policy Service

Tạo Policy Service tại application layer, không chỉ kiểm tra ở router/UI.

Interface tối thiểu:

```python
class CompetencyAuthorizationPolicy:
    async def can_mark_assessed(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        competency_id: str,
        assessment_decision_id: UUID,
    ) -> AuthorizationDecision:
        ...

    async def can_verify(
        self,
        *,
        actor_id: UUID,
        subject_id: UUID,
        organization_id: UUID,
        competency_id: str,
        assessment_decision_id: UUID,
    ) -> AuthorizationDecision:
        ...

    async def can_require_reassessment(...):
        ...

    async def can_revoke_verification(...):
        ...
```

`AuthorizationDecision` phải có:

```text
allowed
reason_code
policy_version
matched_role
delegation_id
scope_match
```

Không trả dữ liệu nhạy cảm trong lý do từ chối.

Policy Service phải được gọi từ application/domain service để không bị bypass bởi:

- REST API;
- worker;
- CLI;
- MCP tool;
- internal batch;
- test utility.

## 7. State machine năng lực

Chuẩn hóa state transition:

```text
UNKNOWN
→ DECLARED
→ ASSESSED
→ PENDING_VERIFICATION
→ VERIFIED
```

Nhánh review:

```text
PENDING_VERIFICATION
→ RETURNED_FOR_REVIEW
→ ASSESSED
```

Vòng đời sau xác minh:

```text
VERIFIED
→ REQUIRES_REASSESSMENT
→ EXPIRED
```

Thu hồi:

```text
VERIFIED
→ REVOKED
```

### Quyền transition

- SME:
  - chấm và đưa kết quả đến `ASSESSED`;
  - yêu cầu reassessment theo policy.
- SME được ủy quyền:
  - `ASSESSED` hoặc `PENDING_VERIFICATION` → `VERIFIED`;
  - `PENDING_VERIFICATION` → `RETURNED_FOR_REVIEW`;
  - yêu cầu reassessment;
  - revoke verification nếu policy cho phép.
- ADMIN:
  - không được bypass competency policy.
- LEARNER:
  - không được transition competency decision.

Không cho phép completion của course tự chuyển competency state.

## 8. Separation of Duties

MVP bắt buộc:

- không cho subject tự chấm hoặc tự verify;
- không cho người dùng tự cấp delegation;
- ADMIN không tự động có quyền verify.

Thiết kế policy để hỗ trợ tùy chọn `four-eyes principle`:

```text
assessor_id != verifier_id
```

Trong MVP có thể cấu hình:

- `LOW_RISK`: cho phép cùng SME chấm và verify nếu có delegation;
- `HIGH_RISK`: bắt buộc assessor và verifier khác nhau.

Không hard-code theo tên competency; dùng policy/risk classification.

## 9. API tối thiểu

### Delegation

```http
POST /delegations
GET /delegations/{delegation_id}
GET /users/{user_id}/delegations
POST /delegations/{delegation_id}/activate
POST /delegations/{delegation_id}/suspend
POST /delegations/{delegation_id}/revoke
```

Mỗi transition nhận:

```json
{
  "expected_version": 3,
  "reason": "..."
}
```

### Assessment/Competency

```http
POST /assessment-decisions/{decision_id}/mark-assessed
POST /assessment-decisions/{decision_id}/request-verification
POST /assessment-decisions/{decision_id}/verify
POST /assessment-decisions/{decision_id}/return-for-review
POST /competencies/{competency_record_id}/require-reassessment
POST /competencies/{competency_record_id}/revoke-verification
```

Không mở endpoint kiểu `set_status` tổng quát.

## 10. Persistence và transaction

Bắt buộc:

- SQLAlchemy repository thật, không chỉ in-memory;
- optimistic locking bằng version;
- acceptance/transition và audit cùng transaction;
- unique/index phù hợp cho active delegation lookup;
- không update immutable verification history;
- lưu delegation ID đã được dùng khi verify;
- lưu policy version và rubric version;
- lưu actor, subject, organization, competency, previous/new state;
- không lưu raw assessment content vào audit.

Đề xuất index:

```text
(user_id, permission, organization_id, status)
(valid_from, valid_until)
```

Nếu competency scope dùng bảng liên kết, thêm index theo `competency_scope_id`.

## 11. Audit events

Tạo immutable audit event cho tối thiểu:

```text
ROLE_ASSIGNED
ROLE_REVOKED
DELEGATION_CREATED
DELEGATION_ACTIVATED
DELEGATION_SUSPENDED
DELEGATION_REVOKED
ASSESSMENT_MARKED_ASSESSED
COMPETENCY_VERIFICATION_REQUESTED
COMPETENCY_VERIFIED
COMPETENCY_RETURNED_FOR_REVIEW
COMPETENCY_REASSESSMENT_REQUIRED
COMPETENCY_VERIFICATION_REVOKED
AUTHORIZATION_DENIED
```

Audit metadata:

```text
actor_id
subject_id
organization_id
competency_id
assessment_id
delegation_id
rubric_version
policy_version
previous_state
new_state
reason_code
timestamp
correlation_id
outcome
```

Không ghi:

- raw assessment response;
- PII không cần thiết;
- prompt thô;
- access token;
- API key.

## 12. Test bắt buộc

### Happy path

- SME chấm đúng scope và chuyển sang `ASSESSED`.
- SME có active delegation đúng scope verify thành công.

### Authorization failure

- SME thường verify → 403.
- ADMIN verify → 403.
- REVIEWER verify → 403.
- LEARNER verify → 403.
- subject tự verify → 403.
- delegation sai organization → 403.
- delegation sai competency scope → 403.
- delegation hết hạn/suspended/revoked → 403.
- user tự cấp delegation → 403.
- stale expected_version → 409.

### State transition

- trạng thái không hợp lệ → 409.
- verify khi chưa `ASSESSED/PENDING_VERIFICATION` → từ chối.
- revoke khi chưa `VERIFIED` → từ chối.
- audit insert lỗi → toàn transaction rollback.

### Separation of duties

- high-risk policy yêu cầu assessor khác verifier.
- low-risk policy cho phép theo cấu hình.

### Audit

- event đúng type;
- không chứa raw sensitive content;
- có delegation ID khi verify;
- denial audit dùng reason code an toàn.

## 13. Acceptance criteria

```gherkin
Given actor có role SME
And assessment thuộc đúng scope
When actor mark assessed
Then decision chuyển sang ASSESSED
And rubric/evidence references được lưu
And audit event được tạo trong cùng transaction
```

```gherkin
Given actor có role SME
And không có active delegation competency.verify
When actor verify
Then trả 403
And state không đổi
And authorization denial được audit an toàn
```

```gherkin
Given actor có role SME
And có active delegation đúng organization và competency scope
And decision ở PENDING_VERIFICATION
And actor không phải subject
When actor verify với expected_version hợp lệ
Then state chuyển VERIFIED
And delegation_id, verifier_id, policy_version được lưu
And immutable audit event được tạo
```

```gherkin
Given delegation đã hết hạn
When actor verify
Then hệ thống từ chối
And không thay đổi competency record
```

```gherkin
Given audit persistence thất bại
When transition được thực hiện
Then state transition bị rollback
```

## 14. ADR và tài liệu

Nếu chưa có, tạo ADR mới:

```text
ADR: RBAC + Scoped Delegation for Competency Verification
```

ADR phải nêu:

- bối cảnh;
- quyết định;
- vì sao không dùng role `admin+sme`;
- vì sao chưa triển khai ABAC tổng quát;
- permission + scoped delegation;
- separation of duties;
- transaction/audit;
- phương án thay thế;
- hệ quả và giới hạn MVP.

Cập nhật:

- `MEMORY.md`
- `AGENTS.md`
- domain glossary
- OpenAPI
- database diagram/schema
- security/authorization documentation

## 15. Không làm trong PR này

- ABAC/policy engine tổng quát;
- OPA/Cedar integration;
- committee approval nhiều tầng;
- credential issuance đầy đủ;
- automatic competency verification;
- dynamic permission do LLM quyết định;
- role explosion theo từng chuyên môn;
- bypass policy cho super-admin.

## 16. Đầu ra cuối cùng của Codex

Sau khi hoàn tất, báo cáo:

1. File đã thêm/sửa.
2. Migration và rollback.
3. API contract.
4. Policy rules.
5. State transition.
6. Test đã chạy và kết quả.
7. Rủi ro còn lại.
8. Các mục cần triển khai sau MVP.
