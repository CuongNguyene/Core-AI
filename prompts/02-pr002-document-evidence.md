Thực hiện PR-002: Document Metadata & Evidence Core.

Bắt buộc đọc `AGENTS.md`, `MEMORY.md`, `docs/domain/three-layer-assessment.md`.

Phạm vi:
- domain model Document;
- metadata file, checksum, MIME type, size, status;
- EvidenceItem persistence;
- API upload metadata và tạo upload workflow;
- validation PDF/DOCX;
- không tin filename/MIME từ client;
- abstraction malware scan;
- source locator;
- audit event;
- test authorization placeholder, validation và IDOR boundary.

Không:
- OCR production;
- LLM extraction;
- lưu file binary trong PostgreSQL;
- log nội dung file.

Tạo migration và OpenAPI contract.
