# System Context

```text
User/UI
  |
API Gateway/WAF
  |
FastAPI Modular Monolith
  |-- Identity/Authorization
  |-- Documents
  |-- Evidence
  |-- Evidence Graph / CandidateProfile
  |-- Competency / Preliminary Matching (rule engine)
  |-- Semantic Policy Registry / Domain Pack Resolver
  |-- Capability Gap Analysis (provisional current/future role tracks)
  |-- Assessment
  |-- Learning
  |-- Audit
  |
Job Queue / Worker
  |
AI Orchestration
  |
Model Gateway
  |-- Local vLLM
  |-- Privacy Gateway --> Approved External Providers
```

## Boundary

- Business module không biết provider cụ thể.
- External provider không nhận raw CV mặc định.
- Model endpoint nội bộ không public Internet.
- MCP là adapter cho agent/tooling, không phải core business path bắt buộc.
- Capability Gap Analysis chỉ nhận accepted CandidateProfile và role-profile IDs,
  giữ current/future gaps tách biệt, và không ghi sang learning hay competency.
- Semantic interpretation của role profile mới phải resolve exact
  `SemanticPolicy(policy_id, version)` và `DomainKnowledgePack(pack_id, version,
  checksum)`. Không latest lookup, domain guessing hoặc implicit IT fallback.
- Domain pack chỉ cung cấp hints/normalization; semantic core giữ quyền quyết định
  evidence eligibility, assessment status, gap và readiness.
- Current/future policy resolve độc lập và được snapshot theo target; thiếu policy
  hoặc pack active thì capability analysis fail closed.
- Một consumer learning trong tương lai chỉ có thể đọc portfolio snapshot đã được
  duyệt qua policy riêng; capability analysis không tạo learning path.
