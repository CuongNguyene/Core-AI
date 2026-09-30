# CV/JD Extraction: luồng end-to-end và kỹ thuật

Tài liệu này mô tả implementation hiện tại của PAI Learning từ tài liệu CV/JD thô đến extraction profile được reviewer chấp nhận, sau đó đi tiếp sang
`CandidateProfile` hoặc `RoleProfileDraft`.

Tài liệu phân biệt rõ:

- path đang chạy mặc định trong worker;
- contract đã có nhưng chỉ dùng khi correction/authoring hoặc feature flag bật;
- các bước downstream không thuộc extraction, như capability analysis.

## 1. Bức tranh tổng thể

```text
PDF/DOCX CV hoặc JD
        │
        ▼
Upload API → safety check → object storage + metadata
        │
        ▼
Extraction Job (QUEUED)
        │
        ▼
Worker claim (RUNNING)
        │
        ├─ CV: chunk extraction mặc định
        │      hoặc evidence-graph extraction nếu bật feature flag
        │
        └─ JD: legacy chunk extraction mặc định
               (JD requirement v2 là contract authoring-ready)
        │
        ▼
ModelGateway → PrivacyGateway → provider adapter
        │
        ▼
Pydantic structured output + source excerpt
        │
        ▼
locator resolution → merge/dedupe → audit aggregation
        │
        ▼
ExtractionProfile (PENDING_REVIEW)
        │
        ├─ CV → CandidateProfile semantic-preserving
        │       → EvidenceIndex → matching/preview
        │
        └─ JD accepted → RoleProfileDraft DRAFT
                         → reviewer authoring/quality gate
                         → PROVISIONAL hoặc ACTIVE RoleCompetencyProfile
```

Extraction không tự tạo `VERIFIED` capability, không tự tạo final competency
decision và không tự coi JD là competency framework đã được phê duyệt.

## 2. Boundary dữ liệu và privacy

### 2.1 Upload và lưu trữ

`POST /documents` nhận multipart PDF/DOCX và `document_kind=cv|jd`.

`app.documents.api.upload_document` thực hiện:

1. đọc tối đa `document_max_bytes + 1` để phát hiện file vượt giới hạn;
2. kiểm tra content type và document safety;
3. tính SHA-256;
4. tạo object key theo document ID/actor;
5. lưu bytes vào S3-compatible object storage (MinIO ở local/dev);
6. lưu metadata vào PostgreSQL;
7. chuyển trạng thái `QUARANTINED → CLEAN`.

Raw document được giữ trong secured document storage. Không đưa raw CV/JD,
prompt hoặc raw model response vào `RoleCompetencyProfile`, portfolio hay audit
metadata.

### 2.2 Parse

`CompositeDocumentSource` lấy object theo document ID rồi gọi
`app.documents.parser.parse_document`:

- PDF: `pypdf.PdfReader`, nối text từng page;
- DOCX: `python-docx`, nối text từng paragraph;
- text rỗng hoặc format không hỗ trợ: fail extraction.

Output parser là text chuẩn hóa, chưa phải evidence. Fixture document (`fixture-*`)
là path deterministic dùng cho test; không đại diện cho upload production.

### 2.3 ModelGateway và PrivacyGateway

Worker không gọi Vilao, vLLM hoặc CTPAI trực tiếp. Request đi qua
`ModelGatewayService`:

```text
InferenceRequest
  → PrivacyService.inspect
  → RoutingPolicy.route
  → ProviderRegistry.resolve
  → provider.complete
  → safe audit metadata
```

CV/JD extraction dùng `DataClassification.RESTRICTED`. Vì vậy:

- restricted data chỉ được route local/organization-controlled;
- external provider không được nhận raw CV/JD;
- privacy inspection fail thì fail-closed, không retry/fallback sang external;
- client không được dùng prompt để vượt qua privacy boundary.

Provider identity được cấu hình tách biệt với endpoint:

| Biến | Ý nghĩa |
|---|---|
| `MODEL_PROVIDER` | provider ID, ví dụ `local-vllm` hoặc `vilao-external` |
| `MODEL_BASE_URL` | OpenAI-compatible `/v1` endpoint hoặc CTPAI gateway endpoint |
| `MODEL_API_KEY` | secret của provider |
| `MODEL_NAME` | model/deployment name |
| `MODEL_MAX_TOKENS` | trần output của provider gateway |
| `MODEL_TIMEOUT_SECONDS`, `MODEL_MAX_RETRIES` | timeout/retry |

`MODEL_MAX_TOKENS` không đồng nghĩa extraction request luôn dùng toàn bộ budget.
Worker truyền `cv_jd_extraction_max_tokens` cho từng request; default setting hiện
là `8192`. Provider có thể hỗ trợ budget lớn hơn, nhưng schema và worker vẫn cần
giữ output bounded.

Audit chỉ giữ provider, model, revision, prompt/schema version, policy version,
correlation ID, routing decision, latency, token usage và outcome. Không ghi raw
payload, raw prompt hay raw response.

## 3. Extraction Job và Worker

### 3.1 API tạo job

```http
POST /extraction-jobs
X-PAI-Actor-ID: <actor>
Content-Type: application/json

{"document_id":"<document-id>","document_kind":"cv"}
```

API xác minh document tồn tại/đủ điều kiện rồi tạo:

```text
QUEUED → RUNNING → SUCCEEDED
                 └→ FAILED
```

Job giữ `document_id`, `document_kind`, owner, correlation ID, status, error
category và profile ID. Request chỉ enqueue; extraction chạy trong worker
(`app.extraction.runner`), không chạy trong FastAPI request path.

### 3.2 Claim và failure isolation

Worker gọi `claim_next()` từng job. PostgreSQL repository dùng row lock với
`skip_locked`, giúp nhiều worker không claim cùng một job.

Lỗi được biến thành safe category, ví dụ:

- `fixture_document_not_found`;
- `chunk_<n>:provider_timeout`;
- `chunk_<n>:provider_response_invalid`;
- `chunk_<n>:invalid_structured_output:<category>`;
- `chunk_<n>:locator_resolution_failed`;
- `extraction_failed`.

Không đưa model response hoặc document text vào error category.

## 4. Chunking và structured extraction

### 4.1 Vì sao chunk

Chunk không chỉ để xử lý giới hạn context 8K. Nó còn giúp:

- giảm xác suất output JSON bị truncate;
- giới hạn số claim mỗi request;
- giữ excerpt gần với vùng nguồn;
- retry/failure ở mức chunk;
- merge/dedupe deterministically.

`split_document` hiện dùng:

- `max_chars=2000`;
- `overlap_chars=150`;
- ưu tiên cắt tại paragraph/newline;
- không để chunk vượt section boundary trong `split_sections`.

Đây là character window, không phải token window. Provider có context 128K
không làm chunking tự động biến mất: chunking vẫn là boundary về locator,
output budget và failure isolation. Việc bỏ chunk chỉ nên là một mode có test
riêng.

### 4.2 Contract output

Mọi output đều đi qua schema registry và Pydantic. Claim supported bắt buộc có:

- `value` hoặc statement;
- `evidence_type`;
- confidence;
- source excerpt;
- sau merge: source locator.

Claim `unknown`/`insufficient` không được có value hoặc excerpt bịa thêm.

Các schema chính:

| Path | Output |
|---|---|
| CV legacy chunk | `CVChunkExtractionOutput` (`skills`, `experience`, `education`) |
| JD legacy chunk | `JDChunkExtractionOutput` (`required_skills`, `responsibilities`, `qualifications`) |
| JD authoring-ready | `JDRequirementExtractionOutputV2` (`requirements[]`) |
| CV relation/graph | `EntityRelationOutput`, `SectionEvidenceOutput` |

Prompt xem document là untrusted data. Nội dung trong CV/JD không được coi là
system instruction.

### 4.3 Hai mode CV

**Standard chunk mode** là default:

```text
document → chunks → CVChunkExtractionOutput từng chunk → merge
```

**Evidence graph mode** chỉ chạy khi `evidence_graph_runtime_enabled=true` và
hiện chỉ áp dụng cho CV:

```text
full CV relation extraction
→ detect sections
→ section evidence extraction
→ relation graph merge
→ CandidateProfile
```

Graph mode giữ relation/context như `used_in`, `worked_on`, `published`,
`studied`, `deployed`, `led`, `owned`. Prompt không được tự suy diễn production,
ownership, seniority hoặc leadership.

## 5. Source locator, merge và dedupe

Model chỉ trả excerpt; model không được tin cậy để tự trả offset.

`_resolve_candidate` tìm excerpt trong chunk theo ba lớp:

1. exact occurrence;
2. whitespace-normalized occurrence;
3. token-normalized occurrence.

Nếu excerpt không xuất hiện đúng một lần hoặc không map được về document gốc,
job fail với `locator_resolution_failed`.

Locator lưu:

```json
{
  "document_id": "...",
  "section": "experience",
  "start_offset": 123,
  "end_offset": 178
}
```

Merge dùng normalized value để gom cùng claim, nhưng vẫn giữ nhiều
`EvidenceReference` theo evidence type. Evidence mạnh hơn được chọn làm primary
theo confidence và priority; evidence khác loại không bị xóa.

Ví dụ Python có:

- explicit skill mention;
- project usage;
- work experience.

thì merge vẫn giữ các context này để downstream phân biệt mention với usage.

## 6. ExtractionProfile và reviewer workflow

Worker tạo `ExtractionProfile` với:

- profile/job/document IDs;
- `version=1`;
- `review_state=PENDING_REVIEW`;
- raw structured output đã được schema validate;
- CV `candidate_profile` compatibility projection nếu có;
- aggregated audit metadata.

Review API:

```text
PENDING_REVIEW
   ├─ POST /corrections          → CORRECTED (version tăng)
   ├─ POST /accept               → ACCEPTED
   ├─ POST /request-revision     → NEEDS_REVISION
   └─ POST /reject               → REJECTED
```

`expected_version` chống stale update. Accepted profile bắt buộc có reviewer và
acceptance timestamp. Profile cũ không bị mutate khi correction; profile mới
trỏ `supersedes_profile_id`.

Endpoint đọc profile:

```http
GET /extraction-jobs/<job-id>
GET /extraction-profiles/<profile-id>
```

Chỉ owner hoặc reviewer được đọc. Reviewer mới được correction/accept/reject.

## 7. CV: từ extraction output đến CandidateProfile

evidence_type
Giá trị	Ý nghĩa	Ví dụ
explicit_skill	Kỹ năng/công nghệ được liệt kê trực tiếp	Python, Docker, SQL
work_experience	Bằng chứng sử dụng trong công việc	“Developed Python automation scripts”
project_usage	Sử dụng trong dự án	“Built a sentiment analysis system using Kafka”
education	Bằng chứng từ học vấn hoặc coursework	BS in Data Science
publication	Bài báo, nghiên cứu, ấn phẩm	“Published research on NLP”
certification	Chứng chỉ hoặc credential	TOEIC, AWS Certified
unknown	Không xác định được loại evidence	Claim thiếu ngữ cảnh

evidence_status
Giá trị	Ý nghĩa	Quy tắc
supported	Claim có bằng chứng nguồn hợp lệ	Phải có value, source_excerpt, source_locator
insufficient	Có tín hiệu nhưng bằng chứng chưa đủ mạnh/chưa đủ ngữ cảnh	Không được tự điền value hoặc excerpt mới
unknown	Không xác định được claim hoặc loại bằng chứng	Không được chứa dữ liệu nguồn bịa thêm
### 7.1 Semantic projection

Compatibility builder `app.extraction.profile_builder` không còn flatten mọi
claim thành employment/mention. Mapping hiện tại:

| Evidence type | Context | Projection chính |
|---|---|---|
| `explicit_skill` | `mentioned` | skill evidence |
| `work_experience` | `used_in_employment` | employment hoặc skill evidence có context employment |
| `project_usage` | `used_in_project` | project/skill evidence |
| `education` | `studied` | education |
| `publication` | `used_in_research` | publication/research |
| `certification` | `credentialed` | credential |
| `unknown` | `unknown` | finding/không tạo evidence mạnh |

`projects`, `research_work`, `publications`, education và credentials không được
đổ chung vào `employment_history`.

### 7.2 EvidenceIndex

Capability analysis xây semantic evidence view từ accepted raw claims nếu có.
Điều này bảo vệ source-of-truth:

```text
accepted CV extraction claims
→ semantic-preserving CandidateProfile/EvidenceIndex
→ canonical capability normalization
→ retrieval candidates
→ context + strength ranking
→ eligibility
→ assessment
```

Production boundary là cứng:

- project deployment có thể retrieved nhưng không eligible cho production
  deployment requirement;
- Docker mention không đủ cho container operation experience;
- work experience không tự động là production nếu excerpt không nói production;
- thiếu evidence là `NOT_FOUND_IN_EVIDENCE`/`INSUFFICIENT`, không phải confirmed
  capability absence.

Đây là capability-analysis boundary, không phải extraction inference. Extraction
chỉ giữ claim/context/source; không kết luận candidate đã verified.

## 8. JD: legacy output và requirement v2

### 8.1 JD path mặc định hiện tại

Default worker vẫn chọn `JD_CHUNK_SCHEMA_ID` và tạo:

```json
{
  "required_skills": [],
  "responsibilities": [],
  "qualifications": []
}
```

Đây là `JDExtractionOutput` kiểu legacy. Nó phù hợp extraction profile ban đầu,
nhưng chưa đủ để coi là competency framework đã duyệt.

### 8.2 JD Requirement v2

`JDRequirementExtractionOutputV2` có `requirements[]` atomic, mỗi requirement
có thể chứa:

- `requirement_id`, statement, criterion dimension;
- modality (`must`, `preferred`, `responsibility`, `unspecified`);
- logical group;
- evidence terms/conflicting terms;
- priority, target level, observable behaviors;
- evidence constraints;
- confidence/status/source locator/source excerpt;
- provenance từng field.

Prompt v2 cấm suy diễn target level, priority, observable behavior, modality,
AND/OR và evidence constraints nếu JD không cung cấp. Field thiếu phải giữ null/
rỗng và provenance không được giả tạo.

V2 contract hiện được register trong prompt/schema registry và source adapter đã
hỗ trợ. Tuy nhiên default extraction worker chưa tự chuyển mọi JD sang v2; đây là
điểm cần hoàn thiện nếu muốn raw JD → v2 end-to-end không qua correction/reviewer.

### 8.3 Accepted JD → RoleProfileDraft

Chỉ `ExtractionProfile.review_state=ACCEPTED` mới được authoring adapter dùng.

```text
accepted JDExtractionProfile
   ↓
adapt_jd_profile
   ↓
RoleProfileDraft (DRAFT)
   ↓ reviewer author/validate
quality gate findings + approval eligibility
   ↓
PROVISIONAL hoặc ACTIVE RoleCompetencyProfile
```

Legacy adapter giữ:

- `required_skills[]` → skill candidates;
- `responsibilities[]` → experience/responsibility candidates;
- `qualifications[]` → education/experience/qualification candidates.

Null/unknown placeholder bị bỏ qua hoặc trở thành finding, không tạo requirement.
Không có JD field nào được coi là candidate evidence.

Legacy draft đánh dấu `source_schema=legacy_v1`, giữ source locator/reference và
tạo findings cho modality, target level, priority, observable behavior, evidence
constraints hoặc semantics không thể phục hồi. Không tự tạo `ACTIVE`.

## 9. API flow thực tế

### CV

```bash
curl -X POST http://localhost:8000/documents \
  -H 'X-PAI-Actor-ID: <actor>' \
  -F 'document_kind=cv' \
  -F 'file=@/absolute/path/candidate.pdf;type=application/pdf'

curl -X POST http://localhost:8000/extraction-jobs \
  -H 'X-PAI-Actor-ID: <actor>' \
  -H 'Content-Type: application/json' \
  -d '{"document_id":"<document-id>","document_kind":"cv"}'
```

Poll job đến `succeeded`, lấy `profile_id`, đọc profile, rồi reviewer accept:

```bash
curl -X POST http://localhost:8000/extraction-profiles/<profile-id>/accept \
  -H 'X-PAI-Actor-ID: <reviewer>' \
  -H 'Content-Type: application/json' \
  -d '{"expected_version":1}'
```

### JD

Upload và enqueue giống CV, chỉ thay `document_kind=jd`. Sau khi reviewer
accept profile:

```bash
curl -X POST http://localhost:8000/role-profile-drafts \
  -H 'X-PAI-Actor-ID: <reviewer>' \
  -H 'Content-Type: application/json' \
  -d '{"source_jd_profile_id":"<accepted-jd-profile-id>","correlation_id":"<opaque>"}'
```

Sau đó author requirements, validate và approve RoleProfile. Chi tiết request
semantic policy exact xem
[`docs/testing/jd-role-profile-authoring.md`](../testing/jd-role-profile-authoring.md).

## 10. Failure modes và cách đọc log

| Giai đoạn | Safe result | Ý nghĩa |
|---|---|---|
| upload | `document_format_rejected` | format/safety/size không đạt |
| source | `document_not_extractable` | metadata/object không đọc được |
| provider | `provider_timeout` | timeout; không chứa raw payload |
| provider | `provider_response_invalid` | HTTP/provider response không hợp lệ |
| output | `invalid_structured_output:*` | JSON/schema không pass sau repair |
| locator | `locator_resolution_failed` | excerpt không map duy nhất vào nguồn |
| profile | `PENDING_REVIEW` | extraction xong nhưng chưa được chấp nhận |
| review | `extraction_profile_version_conflict` | reviewer dùng version cũ |
| authoring | `role_profile_draft_source_not_accepted` | JD chưa accepted |

Không nên debug bằng cách in raw CV/JD hoặc raw model output. Hãy dùng job ID,
profile ID, correlation ID, chunk ordinal, schema version và locator metadata.

## 11. Test map

Các test chính:

- upload/parser/storage: `test_document_api.py`, `test_documents.py`,
  `test_document_source.py`;
- worker/chunk/merge/locator: `backend/tests/test_extraction_*.py`;
- ModelGateway/privacy: `backend/tests/test_model_gateway.py`,
  `test_privacy_routing.py`, `test_provider_selection.py`;
- semantic CV builder: `test_candidate_profile_builder.py`,
  `test_capability_evidence_index.py`;
- semantic retrieval: `test_capability_semantic_retrieval.py`,
  `test_semantic_core_*.py`, `test_semantic_cross_domain_fixtures.py`;
- JD adapter/authoring: `test_role_profile_authoring_*.py`;
- raw CV/JD harness: `docs/testing/cv-jd-capability-e2e.md`.

Invariant tối thiểu cần giữ:

1. supported claim luôn có source evidence và locator sau merge;
2. unknown/insufficient không tạo value/excerpt giả;
3. project/work/education/publication/credential giữ context riêng;
4. chỉ accepted extraction mới là input matching/authoring;
5. JD extraction không tự tạo ACTIVE role profile;
6. raw CV/JD không xuất hiện trong audit/profile/portfolio;
7. PREVIEW không tạo final competency decision hoặc VERIFIED status.

## 12. Đang chạy thật và phần còn thiếu

Đã có runtime end-to-end cho:

- upload → parse → queue → worker → structured extraction → locator/merge →
  `PENDING_REVIEW`;
- reviewer accept CV và dùng semantic-preserving evidence cho PREVIEW;
- accepted legacy JD → compatibility RoleProfileDraft;
- policy/role authoring boundary và exact semantic policy governance.

Chưa phải default raw-JD-to-approved-role E2E hoàn chỉnh:

- worker JD mặc định còn tạo legacy `required_skills/responsibilities/qualifications`;
- JD v2 contract có nhưng cần một extraction mode/route chính thức để worker
  sinh `JDRequirementExtractionOutputV2` từ đầu;
- authoring/reviewer vẫn phải bổ sung các field mà JD không cung cấp;
- OFFICIAL/VERIFIED/final competency decision và learning path nằm ngoài extraction.
Vì vậy khi test với tài liệu thật, cần ghi rõ đang test một trong hai mục:

```text
A. extraction + review profile
B. accepted profile → authoring/capability preview
```

Không gọi A là full CV–JD competency E2E nếu JD chưa đi qua v2 authoring và
review approval.
