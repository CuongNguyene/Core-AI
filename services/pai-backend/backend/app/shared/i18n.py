"""Locale helpers for API-facing PAI messages.

The error ``code`` is the integration contract.  Only the human-readable
``message`` is localized, so LMS clients can keep relying on stable codes.
"""

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = frozenset({"en", "vi"})


VI_ERROR_MESSAGES = {
    "http_error": "Không thể hoàn tất yêu cầu.",
    "request_validation_failed": "Dữ liệu yêu cầu không hợp lệ.",
    "internal_server_error": "Đã xảy ra lỗi không mong muốn.",
    "service_not_ready": "Dịch vụ chưa sẵn sàng.",
    "integration_authentication_failed": "Xác thực tích hợp không thành công.",
    "integration_service_unavailable": "Dịch vụ tích hợp chưa sẵn sàng.",
    "actor_context_unavailable": "Không thể xác minh ngữ cảnh người dùng.",
    "ACTOR_CONTEXT_MISSING": "Thiếu ngữ cảnh người dùng.",
    "ACTOR_CONTEXT_EXPIRED": "Ngữ cảnh người dùng đã hết hạn.",
    "ACTOR_CONTEXT_REPLAYED": "Ngữ cảnh người dùng không hợp lệ.",
    "ACTOR_CONTEXT_SIGNATURE_INVALID": "Chữ ký ngữ cảnh người dùng không hợp lệ.",
    "ACTOR_CONTEXT_INVALID": "Ngữ cảnh người dùng không hợp lệ.",
    "ACTOR_NOT_FOUND": "Không tìm thấy người dùng.",
    "ORGANIZATION_NOT_ALLOWED": "Tổ chức không được phép truy cập.",
    "idempotency_key_required": "Cần cung cấp Idempotency-Key.",
    "capability_gap_unavailable": "Phân tích khoảng cách năng lực chưa sẵn sàng.",
    "capability_analysis_idempotency_conflict": "Yêu cầu phân tích này đã tồn tại với dữ liệu khác.",
    "capability_analysis_not_found": "Không tìm thấy kết quả phân tích.",
    "capability_gap_not_found": "Không tìm thấy khoảng cách năng lực.",
    "capability_gap_access_denied": "Không được phép truy cập phân tích khoảng cách năng lực.",
    "capability_gap_input_not_accepted": "Dữ liệu phân tích khoảng cách năng lực không được chấp nhận.",
    "capability_gap_integration_error": "Không thể hoàn tất phân tích khoảng cách năng lực.",
    "target_profile_not_usable": "Hồ sơ năng lực mục tiêu chưa thể sử dụng.",
    "semantic_policy_not_configured": "Chưa cấu hình chính sách ngữ nghĩa.",
    "semantic_policy_unavailable": "Quản trị chính sách ngữ nghĩa chưa sẵn sàng.",
    "semantic_policy_not_found": "Không tìm thấy phiên bản chính sách ngữ nghĩa.",
    "semantic_policy_binding_invalid": "Liên kết chính sách ngữ nghĩa không hợp lệ.",
    "role_profile_unavailable": "Quản trị hồ sơ vai trò chưa sẵn sàng.",
    "role_profile_not_found": "Không tìm thấy phiên bản hồ sơ vai trò.",
    "content_generation_unavailable": "Tạo nội dung chưa sẵn sàng.",
    "content_generation_not_found": "Không tìm thấy kết quả tạo nội dung.",
    "learning_path_unavailable": "Dịch vụ lộ trình học chưa sẵn sàng.",
    "invalid_learning_path_source": "Nguồn lộ trình học không thể chuyển đổi.",
    "learning_authoring_unavailable": "Soạn nội dung học chưa sẵn sàng.",
    "learning_authoring_access_denied": "Không được phép truy cập nội dung học.",
    "learning_authoring_reference_not_found": "Không tìm thấy dữ liệu tham chiếu nội dung học.",
    "learning_authoring_projection_error": "Không thể tạo nội dung học từ dữ liệu hiện có.",
    "course_authoring_unavailable": "Soạn khóa học chưa sẵn sàng.",
    "course_authoring_access_denied": "Không được phép truy cập yêu cầu soạn khóa học.",
    "course_authoring_request_not_found": "Không tìm thấy yêu cầu soạn khóa học.",
    "course_authoring_reference_not_found": "Không tìm thấy dữ liệu tham chiếu khóa học.",
    "course_authoring_reference_invalid": "Dữ liệu tham chiếu khóa học không hợp lệ.",
    "course_authoring_integration_error": "Không thể hoàn tất yêu cầu soạn khóa học.",
    "course_generation_unavailable": "Tạo khóa học chưa sẵn sàng.",
    "course_generation_already_in_progress": "Khóa học đang được tạo.",
    "course_generation_artifact_not_found": "Không tìm thấy kết quả tạo khóa học.",
    "course_generation_output_invalid": "Kết quả tạo khóa học không hợp lệ.",
    "course_generation_provider_failed": "Nhà cung cấp AI không thể tạo khóa học.",
    "course_generation_progress_unavailable": "Tiến trình tạo khóa học chưa sẵn sàng.",
    "course_generation_retry_unavailable": "Không thể thử lại việc tạo khóa học lúc này.",
    "curriculum_planning_unavailable": "Lập kế hoạch chương trình học chưa sẵn sàng.",
    "curriculum_plan_not_found": "Không tìm thấy kế hoạch chương trình học.",
    "curriculum_plan_invalid": "Kế hoạch chương trình học không hợp lệ.",
    "course_revision_unavailable": "Chỉnh sửa bản nháp khóa học chưa sẵn sàng.",
    "course_revision_not_found": "Không tìm thấy bản nháp khóa học.",
    "course_revision_access_denied": "Không được phép truy cập bản nháp khóa học.",
    "course_revision_conflict": "Bản nháp khóa học đã thay đổi. Hãy tải lại và thử lại.",
    "course_revision_invalid": "Bản nháp khóa học không hợp lệ.",
    "course_blueprint_not_found": "Không tìm thấy khung khóa học.",
    "competency_result_not_found": "Không tìm thấy kết quả năng lực.",
    "candidate_service_unavailable": "Dịch vụ ứng viên chưa sẵn sàng.",
    "assessment_repository_unavailable": "Dịch vụ đánh giá chưa sẵn sàng.",
    "assessment_template_not_found": "Không tìm thấy mẫu đánh giá.",
    "sme_role_required": "Yêu cầu vai trò chuyên gia.",
    "credential_service_unavailable": "Dịch vụ chứng chỉ chưa sẵn sàng.",
    "credential_not_found": "Không tìm thấy yêu cầu chứng chỉ.",
    "credential_access_denied": "Không được phép truy cập chứng chỉ.",
    "document_service_unavailable": "Dịch vụ tài liệu chưa sẵn sàng.",
    "document_storage_unavailable": "Kho lưu trữ tài liệu chưa sẵn sàng.",
    "document_scanner_unavailable": "Trình quét tài liệu chưa sẵn sàng.",
    "document_format_rejected": "Định dạng tài liệu hoặc kiểm tra an toàn không đạt.",
    "delegation_repository_unavailable": "Dịch vụ ủy quyền chưa sẵn sàng.",
    "delegation_write_unavailable": "Chưa thể cập nhật ủy quyền.",
    "delegation_not_found": "Không tìm thấy ủy quyền.",
    "delegation_access_denied": "Không được phép truy cập ủy quyền.",
    "admin_role_required": "Yêu cầu vai trò quản trị viên.",
    "self_delegation_forbidden": "Không thể tự ủy quyền cho chính mình.",
    "invalid_delegation_window": "Thời hạn ủy quyền không hợp lệ.",
    "delegation_transition_invalid": "Trạng thái ủy quyền không hợp lệ.",
    "competency_service_unavailable": "Dịch vụ năng lực chưa sẵn sàng.",
    "extraction_repository_unavailable": "Dịch vụ trích xuất chưa sẵn sàng.",
    "extraction_job_not_found": "Không tìm thấy tác vụ trích xuất.",
    "extraction_profile_not_found": "Không tìm thấy hồ sơ trích xuất.",
    "extraction_access_denied": "Không được phép truy cập dữ liệu trích xuất.",
    "invalid_correction_output": "Kết quả hiệu chỉnh không hợp lệ.",
    "development_identity_required": "Yêu cầu định danh môi trường phát triển.",
    "reviewer_role_required": "Yêu cầu vai trò người đánh giá.",
}


def resolve_locale(accept_language: str | None) -> str:
    """Resolve a supported locale from a standard Accept-Language header."""
    if not accept_language:
        return DEFAULT_LOCALE

    for item in accept_language.split(","):
        language = item.split(";", 1)[0].strip().lower().replace("_", "-")
        primary_language = language.split("-", 1)[0]
        if primary_language in SUPPORTED_LOCALES:
            return primary_language
    return DEFAULT_LOCALE


def localize_error_message(*, code: str, message: str, locale: str) -> str:
    if locale == "vi":
        return VI_ERROR_MESSAGES.get(code, message)
    return message
