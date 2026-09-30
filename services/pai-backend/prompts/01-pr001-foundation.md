Thực hiện PR-001: Project Foundation.

Đọc `AGENTS.md` và `MEMORY.md` trước.

Phạm vi:
- hoàn thiện cấu hình FastAPI;
- cấu hình structured logging nhưng không log dữ liệu nhạy cảm;
- thêm error response contract;
- thêm database session async;
- thiết lập Alembic;
- thêm CI cho Ruff, mypy, pytest;
- thêm pre-commit;
- thêm `/health/live` và `/health/ready`;
- bổ sung test.

Không làm:
- CV extraction;
- gọi LLM;
- authentication production;
- microservices.

Yêu cầu:
- giải thích các quyết định;
- cập nhật README;
- tạo ADR nếu thay đổi lựa chọn nền tảng;
- chạy toàn bộ kiểm thử;
- báo cáo file đã thay đổi và các rủi ro còn lại.
