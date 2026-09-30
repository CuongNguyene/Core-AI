Thực hiện PR-003: Model Gateway & Privacy Gateway.

Mục tiêu:
- triển khai interface đã scaffold;
- LocalVLLMProvider dùng OpenAI-compatible HTTP;
- provider registry;
- routing policy;
- timeout/retry có kiểm soát;
- PII inspection abstraction;
- deny external by default;
- audit metadata không chứa prompt thô;
- mock provider phục vụ test.

Không:
- hỗ trợ provider ngoài thật nếu chưa có approved provider ADR;
- ghi API key vào code;
- cho domain module gọi HTTP model trực tiếp.

Test:
- restricted data luôn local;
- external disabled thì không thể route ngoài;
- privacy failure phải fail closed;
- timeout và invalid structured output.
