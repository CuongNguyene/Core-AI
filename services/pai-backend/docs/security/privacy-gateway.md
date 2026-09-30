# Privacy Gateway

## Mục tiêu

Ngăn dữ liệu cá nhân và dữ liệu hạn chế bị gửi ra ngoài ngoài chính sách.

## Luồng

```text
Business Request
→ Data Classification
→ PII Detection
→ Data Minimization
→ Pseudonymization
→ Policy Evaluation
→ Provider Routing
→ Output Inspection
→ Internal Re-identification if permitted
```

## Policy mặc định

- Restricted: local only.
- Sensitive: local by default.
- External use:
  - provider được duyệt;
  - mục đích hợp lệ;
  - dữ liệu đã tối thiểu hóa;
  - khử định danh thành công;
  - audit đầy đủ;
  - không có trường bị cấm.
- Không log raw content.
- Không dùng model provider trực tiếp từ domain module.
