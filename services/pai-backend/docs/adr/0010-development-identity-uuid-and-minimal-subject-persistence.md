# ADR-0010: Development Identity UUID và Minimal Subject Persistence

## Status

Accepted.

## Context

Các slice trước dùng actor ID string fixture và role từ HTTP header. Assessment
và competency decision cần subject, organization, role và delegation có thể audit
được; string fixture hoặc mapping ngầm không đáp ứng security boundary này.
Identity Provider, SSO và enterprise IAM vẫn chưa thuộc MVP.

## Decision

- Internal actor identity dùng UUID ổn định. `X-PAI-Actor-ID` chỉ là development
  authentication adapter và bắt buộc là UUID hợp lệ.
- Adapter resolve UUID qua persistence, từ chối thiếu/sai UUID, user không tồn
  tại/disabled, không có active membership, nhiều active membership, hoặc
  organization inactive. Không tự tạo user và không fallback từ actor string cũ.
- Persistence tối thiểu gồm `User`, `Organization`, `OrganizationMembership` và
  `UserRoleAssignment`, được fixture/seed cho development và integration test.
- Mỗi development user có chính xác một active organization membership. Không
  hỗ trợ `X-PAI-Organization-ID`; adapter không chọn membership đầu tiên hoặc
  suy luận organization từ role, delegation hay resource. Multi-organization
  context selection ngoài PR-006.
- `ActorContext` chứa actor UUID, organization UUID, role assignments active và
  `authentication_method="development_header"`. Client không được truyền role
  hoặc organization như nguồn authority.
- Đây không phải IAM production: không password, OAuth/OIDC, SSO, refresh token,
  MFA, directory sync hoặc tenant federation. IdP tương lai thay adapter nhưng
  giữ internal UUID.

## Alternatives considered

- Giữ actor string và hash/map sang UUID: loại bỏ vì mapping không được phê duyệt
  và làm yếu audit/security boundary.
- Role/organization trong request header: loại bỏ vì client có thể mạo nhận.
- Multi-org context header ngay: loại bỏ vì tăng ambiguity và attack surface.

## Consequences

- API development cũ phải chuyển fixture/header actor ID sang UUID.
- Các audit/ownership mới dùng UUID; dữ liệu development cũ có thể reset, không
  có implicit backfill từ string.
- Production deployment vẫn chặn cho tới ADR IdP/RBAC production riêng.

## Migration

Tạo subject-store tables và chuyển các actor field thuộc PR-006 sang UUID. Các
slice fixture trước không có dữ liệu production cần giữ; migration không hash,
parse hay suy luận UUID từ actor string.
