# ADR-0003: Error contract và request correlation cho API

## Status

Accepted.

## Context

MVP sẽ nhận CV/JD không đáng tin cậy và có dữ liệu nhạy cảm. API cần một error
contract ổn định để UI và audit có thể đối chiếu request mà không trả lại hay
ghi log raw request payload.

## Decision

- Mọi lỗi application trả về envelope:

  ```json
  {
    "error": {
      "code": "machine_readable_code",
      "message": "Safe user-facing message.",
      "correlation_id": "uuid"
    }
  }
  ```

- Middleware dùng `X-Request-ID` khi giá trị là UUID hợp lệ; nếu không, tạo UUID
  mới. Response luôn trả lại `X-Request-ID`.
- Request validation không echo input lỗi; lỗi nội bộ dùng thông điệp chung.
- Structured log chỉ ghi metadata vận hành an toàn (event, level, timestamp,
  method, path và correlation ID). Các key nhạy cảm bị redaction.
- Endpoint mới phải khai báo error response trong OpenAPI và có test cho success
  path cùng failure path.

## Alternatives considered

- Trả `detail` mặc định của FastAPI: loại bỏ vì validation detail có thể chứa
  giá trị từ CV/JD.
- Bắt buộc client cung cấp request ID: loại bỏ vì làm hỏng client đơn giản và
  không tạo trace cho request thiếu header.
- Log toàn bộ request để debug: loại bỏ vì vi phạm privacy boundary.

## Consequences

- Client có một contract lỗi nhất quán và có thể gửi correlation ID khi báo lỗi.
- Debug payload chi tiết phải thực hiện qua audit an toàn ở các PR sau, không
  phải log application.
- Response validation chi tiết không được cung cấp mặc định; các endpoint có thể
  thêm error code công khai khi yêu cầu nghiệp vụ đã rõ.

## Migration

Không có API public cũ cần chuyển đổi. Endpoint `/health` tương thích ngược;
PR-001 bổ sung `/health/live` và `/health/ready`.
