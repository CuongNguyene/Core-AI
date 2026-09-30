# MVP Scope

## Mục tiêu

Chứng minh một vertical slice an toàn và có thể kiểm thử:

```text
Upload CV/JD
→ Parse
→ Extract Evidence
→ Human Review
→ Preliminary Match
→ Recommended Assessment
```

## In scope

- Quản lý metadata tài liệu.
- Upload PDF/DOCX.
- CV extraction có source locator.
- JD extraction và JD Quality Gate.
- Evidence Profile.
- Role Requirement Profile.
- Acceptance human review trước matching chính thức.
- Preliminary matching theo criterion, có allocation evidence, confidence gate,
  preliminary skill gap và assessment recommendation.
- Domain-neutral capability core với exact SemanticPolicy/DomainKnowledgePack
  resolution và target-specific PREVIEW portfolio snapshot.
- Human correction.
- Audit.
- Local vLLM provider.
- Privacy policy boundary.

## Out of scope ở vertical slice đầu tiên

- Tự động cấp chứng nhận năng lực.
- Sinh video.
- Webcam proctoring.
- Full LMS.
- Multi-tenant phức tạp.
- Fine-tuning trên dữ liệu thật.
- Tự động loại ứng viên.
- Overall match score là output quyết định duy nhất.
- Tự động chọn domain pack, latest semantic policy hoặc implicit `it_ai@1`.
- OFFICIAL capability decision, VERIFIED transition hoặc learning path từ PREVIEW.
- 10 agent độc lập.
