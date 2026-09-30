Bạn đang làm việc trong repository PAI Platform.

Bắt buộc:
1. Đọc `AGENTS.md`.
2. Đọc `MEMORY.md`.
3. Đọc toàn bộ `docs/product`, `docs/architecture`, `docs/domain`,
   `docs/security` và `docs/adr`.
4. Không viết mã trước khi báo cáo:
   - phạm vi hiểu được;
   - các giả định;
   - blocker;
   - kế hoạch pull request nhỏ;
   - các ADR còn thiếu.

Mục tiêu phiên này:
- kiểm tra scaffold hiện tại;
- đề xuất kế hoạch triển khai vertical slice:
  Upload CV/JD → Evidence Profile → Preliminary Match → Human Review;
- không xây full LMS;
- không triển khai external AI trước Privacy Gateway;
- không thay đổi kiến trúc modular monolith nếu chưa có ADR.

Đầu ra:
1. Architecture review ngắn.
2. Danh sách thiếu sót theo P0/P1/P2.
3. Kế hoạch PR.
4. Sau khi trình bày, chỉ bắt đầu PR-001 nếu không có blocker.
