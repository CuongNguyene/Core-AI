# Authorization MVP

PR-006 dùng development identity adapter với UUID header và minimal subject
persistence; đây không phải production IAM. Role/organization không lấy từ
request header. Adapter fail closed khi user disabled/unknown, organization
inactive, hoặc membership active không đúng một.

Verification cần role SME, delegation `competency.verify` active đúng scope/org/
time, separation-of-duties và competency state hợp lệ. ADMIN không bypass policy.
Policy application-layer và audit immutable là security boundary; UI/router không
thay thế được policy.

Credential actions dùng scoped delegation riêng: `credential.approve`,
`credential.issue` và `credential.revoke`. Không role nào tự động bypass các
scope này; request phải qua eligibility policy, optimistic version và approval
trước issue. Public verification chỉ trả trạng thái/validity và policy metadata,
không trả subject identity, evidence, assessment content hoặc audit payload.

Assessment template/rubric/task, submission, score proposal, SME review và
assessment decision được lưu qua SQLAlchemy repository. Competency record giữ
state hiện tại; mỗi transition tạo immutable decision history với evidence,
rubric/policy version, actor và delegation reference khi verify.

Transition dùng optimistic version check và row lock. State update, history và
audit event nằm trong cùng transaction; audit failure rollback toàn bộ state.
Audit metadata chỉ chứa identifiers, versions, state và reason code, không chứa
raw answer, prompt, artifact content hay evidence payload.

Development API nằm tại `/delegations`, `/assessment-*` và
`/competencies/{record_id}/...`; role/organization chỉ lấy từ
`X-PAI-Actor-ID` được resolve qua subject persistence.
