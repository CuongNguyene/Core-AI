# ADR-0012: Learning Path Ownership, Input Eligibility, Content Provenance và Audit

## Status

Accepted.

## Context

PR-007 bổ sung learning path và course blueprint sau khi hệ thống đã có
verified competency, target role profile và preliminary matching. Learning
content là domain mới; nếu nhận dữ liệu chưa được duyệt hoặc cho completion cập
nhật competency, boundary ba tầng sẽ bị phá vỡ.

Các quyết định về production content repository, publishing workflow, LMS
progress và content generation provider chưa được chốt. MVP chỉ cần blueprint
và metadata có thể truy xuất, không cần lưu nội dung bài học hoàn chỉnh.

## Decision

- Learning Path chỉ được tạo từ bốn nhóm input đã snapshot bằng ID và version:
  - `CompetencyRecord` của cùng subject/organization ở trạng thái `VERIFIED`,
    chưa hết hạn và có decision history;
  - `RoleCompetencyProfile` ở trạng thái `ACTIVE`, dùng làm target competency
    profile;
  - preliminary gaps thuộc một `PreliminaryMatch` ở trạng thái `REVIEWED`, có
    approval record rõ ràng, tham chiếu bằng `preliminary_match_id` và
    confidence không thấp hơn threshold của requirement;
  - mục tiêu phát triển và deadline do người dùng cung cấp.
- Không đọc CV/JD thô, extraction payload chưa accepted, match chưa reviewed,
  competency `ASSESSED` hoặc dữ liệu không có version làm input chính thức.
  Input bị thiếu, stale, superseded, hết hạn hoặc khác organization phải fail
  closed.
- Trong development MVP, actor chỉ được tạo learning path cho chính subject
  của mình. Không nhận role/organization từ request body/header; actor và
  organization lấy từ ADR-0010. SME/ADMIN không có implicit quyền authoring;
  scoped authoring delegation là future ADR.
- Learning Path, Course Blueprint, Module, Lesson và Learning Object Metadata
  đều immutable theo version. Sửa đổi tạo version mới và đánh dấu version cũ
  `SUPERSEDED`; không update tại chỗ.
- Prerequisite graph là directed acyclic graph. Node/edge phải cùng blueprint
  version; cycle, self-edge, unknown node hoặc duplicate edge bị từ chối.
- Learning Object chỉ lưu metadata, competency link, target level, assessment
  template/rubric reference và provenance reference. PR-007 không lưu hoặc
  xuất bản nội dung sinh tự do, không nhận nguồn chưa xác thực và không cấp
  credential.
- `ContentBlueprintGenerator` là internal protocol. Provider fake/mock được
  dùng trong test và fixture; provider thật tương lai phải đi qua worker,
  ModelGateway và PrivacyGateway. Generator chỉ nhận approved IDs, normalized
  objectives, gap summaries và metadata; không nhận raw CV/JD hoặc prompt từ
  client.
- Tạo learning path không tạo competency decision. Completion, lesson progress
  hoặc learning object consumption không được gọi competency transition.
- Mọi path/blueprint snapshot lưu `actor_id`, `organization_id`, source IDs và
  versions, generator/model/template/policy version nếu có, correlation ID và
  safe outcome. Audit không chứa raw document, prompt, generated body, answer,
  PII hay evidence payload.
- Lifecycle MVP của learning path là `DRAFT`, `ACTIVE`, `SUPERSEDED`, `FAILED`.
  `ACTIVE` chỉ có nghĩa blueprint đã qua input/graph validation; không có nghĩa
  người học đạt competency. Credential issuance và completion tracking nằm
  ngoài PR-007.

## Alternatives considered

- Cho phép dùng `COMPLETED` preliminary match trực tiếp: loại bỏ vì kết quả
  chưa qua human approval và có thể chứa gap confidence thấp.
- Cho learner truyền inline competency/gap JSON: loại bỏ vì bypass version,
  provenance và review state.
- Sinh toàn bộ nội dung bài học bằng LLM trong PR-007: loại bỏ vì chưa có
  approved content source/provider, privacy policy và publishing controls.
- Cho ADMIN bypass input/authoring policy: loại bỏ vì ADR-0011 đã quy định ADMIN
  không có implicit chuyên môn; authoring scope cần policy riêng.
- Lưu mutable path duy nhất: loại bỏ vì làm mất khả năng tái hiện plan khi
  competency, target profile hoặc rubric thay đổi.

## Consequences

- PR-007 cần một review/approval contract cho preliminary gaps nếu PR-005 chưa
  có. Có thể triển khai contract tối thiểu trong cùng vertical slice, nhưng
  không được tự động coi `COMPLETED` là approved.
- Learning module có thể test deterministic mà không cần model thật hoặc nguồn
  content ngoài. Provider thật, object storage, publishing và learner progress
  cần ADR/PR sau.
- Mỗi plan có thể tái hiện từ input snapshot và version; stale input bị chặn
  thay vì âm thầm tạo plan sai nguồn.
- API public chỉ trả metadata và references an toàn; UI/LMS delivery không thuộc
  boundary PR-007.

## Migration

PR-007 thêm các bảng versioned cho learning paths, objectives, blueprints,
modules, lessons, learning object metadata, prerequisite edges, competency
links, gap approvals và learning audit events. Không migrate hoặc sao chép raw
CV/JD, prompt, model output body hay credential data.
