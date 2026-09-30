# Báo cáo rà soát toàn bộ hiện trạng PAI Backend trong BrainHub

**Thời điểm:** 25/09/2026  
**Nguồn rà soát chính:** `C:\Projects\BrainHub\ct_brain_hub\pai-backend`  
**Đối chiếu tích hợp:** `C:\Projects\BrainHub\ct_brain_hub\5. SOURCE\ndt-training-management-system-main` (LMS/TMS)  
**Phạm vi:** mã nguồn, migration, cấu hình dependency, tài liệu và contract tích
hợp có trong hai thư mục. Không xác nhận môi trường đang chạy, dữ liệu thực tế,
secret, database runtime hay production deployment.

## Kết luận ưu tiên

PAI Backend có phần lớn domain và API cần cho chuỗi CV/JD → evidence → review →
capability analysis `PREVIEW` → learning/course authoring. LMS đã có adapter,
route `/api/pai/*`, UI và test E2E cho nhiều luồng đó. Tuy nhiên, **chưa thể coi
luồng source/mapping là ổn định để triển khai** vì hai snapshot PAI đang phân
kỳ, migration của snapshot BrainHub chưa được merge, và một số ranh giới
identity/async vẫn chưa được xác nhận end-to-end.

Không nên mở rộng MVP, coi kết quả `PREVIEW` là quyết định năng lực, hoặc cho
completion LMS tự chuyển competency/credential trước khi các điểm chặn dưới đây
được xử lý và kiểm thử trên một revision thống nhất.

## 1. Bản đồ hệ thống và ownership

```text
Browser
  -> LMS UI (React/Vite)
  -> LMS API /api/pai/* (NestJS/Prisma)
  -> PaiApiClient (Bearer key + contract v1 + actor context/header)
  -> PAI API (FastAPI/SQLAlchemy/Alembic)
       -> PostgreSQL PAI, MinIO, extraction worker
       -> ModelGateway -> PrivacyGateway -> provider được policy cho phép
```

| Khu vực | Owner | Trạng thái rà soát |
| --- | --- | --- |
| Candidate, document evidence, extraction, competency semantics và capability analysis | PAI | Có mã nguồn, API và migration riêng. |
| Course/Lesson/Enrollment/Progress/Certificate delivery | LMS | Có NestJS/Prisma riêng; không được ghi đè ownership PAI. |
| Giao tiếp | LMS `PaiApiClient` | Có code và test contract, dùng envelope `v1`. |
| Database/migration | Tách biệt | Prisma của LMS và Alembic của PAI không được dùng chung hay chạy chung. |
| Raw CV/JD | PAI | LMS gửi upload đến PAI; LMS không được đưa raw document trực tiếp tới model provider. |

Kiến trúc đích là monorepo giữ nguyên service, runtime, database và migration
riêng; hiện không có bằng chứng rằng target topology/reverse proxy đã được
triển khai. Tài liệu runtime topology ghi rõ là scan-only.

## 2. Hiện trạng PAI trong snapshot BrainHub

### Nền tảng kỹ thuật

- FastAPI, Python 3.13+, Pydantic v2, SQLAlchemy async, PostgreSQL và Alembic.
- Modular monolith, gồm các package documents, extraction, evidence, candidate,
  matching, role registry/authoring, semantic policy, capability analysis,
  assessment, competency, learning, credential, course authoring/generation,
  integration, model gateway và privacy.
- Có 214 tệp test `test_*.py` trong snapshot này.
- Frontend trong `pai-backend/frontend/` vẫn là placeholder; UI PAI thực tế nằm
  ở LMS, không phải frontend placeholder này.
- PAI API được mount không có global prefix; boundary integration/candidate dùng
  `/api/v1/...`, còn technical API cũ như `/documents`, `/extraction-jobs`,
  `/extraction-profiles` và `/roles` vẫn tồn tại.

### Luồng nghiệp vụ đã có mã nguồn

| Luồng | PAI | LMS mapping | Đánh giá |
| --- | --- | --- | --- |
| CV candidate | Candidate aggregate, document attach, extraction job, profile/CV version, review và evidence read | `/api/pai/candidates`, upload → tạo candidate → upload document → attach → extraction job | Có code ở cả hai phía; chưa chứng minh E2E runtime. |
| JD/role | Document/extraction review, correction, role/JD registry và role-profile draft | `/api/pai/jd-reviews`, `/api/pai/roles` | Có code và contract mapping. |
| Capability gap | Exact target refs, evidence view, human-assisted reanalysis, portfolio `PREVIEW` | `/api/pai/candidates/:id/capability-analyses` và `/api/pai/capability-analyses/:id/*` | Có code; chỉ là hypothesis/provisional output. |
| Learning path | PAI integration API và LMS facade | `/api/pai/candidates/:id/learning-paths` | Có mapping; không được tự suy ra từ `PREVIEW` nếu policy chưa cho phép. |
| Course authoring/generation | PAI authoring, plan/revision/result APIs | LMS facade và materialization/publish services | Có code; độ bền dispatch phụ thuộc snapshot được triển khai. |
| Learning result | PAI integration endpoint/durable evaluation contract | `PaiLearningResultService` là optional sau khi LMS persist fact | Không được gọi từ `ProgressService`; completion không tự là competency. |
| Credential | Workflow PAI riêng | LMS certificate/PDF vẫn là delivery feature khác | Không được đồng nhất certificate LMS với credential competency PAI. |

## 3. Guardrail nghiệp vụ và bảo mật đang được thiết kế

1. Tầng 1 chỉ extract/normalize evidence; tầng 2 chỉ mapping/hypothesis; tầng 3
   với assessment/rubric/SME mới có thể `ASSESSED` hoặc `VERIFIED`.
2. Capability analysis hiện là `PREVIEW`: không có OFFICIAL decision, verified
   transition, readiness verdict chung, learning objective/path tự động hay
   credential từ một kết quả matching.
3. Semantic policy phải resolve exact `policy_id + policy_version`; pack checksum
   và provenance current/future được snapshot riêng. Không latest lookup, domain
   guessing hay fallback `it_ai@1`.
4. Domain pack chỉ normalize/hint; semantic core giữ eligibility, assessment,
   gap và readiness.
5. AI đi qua `ModelGateway`; dữ liệu egress đi qua `PrivacyGateway`; raw CV/JD,
   prompt, token và secret không được log.
6. Production upload yêu cầu ClamAV fail-closed; restricted data xử lý local.

## 4. Luồng mapping/source cần đặc biệt lưu ý

### 4.1 Candidate CV → extraction → review

LMS `PaiApiClient.uploadCandidateCv()` đang thực hiện nhiều HTTP call tuần tự:

```text
create PAI candidate
-> POST PAI /documents (multipart CV)
-> attach document to candidate
-> POST PAI /extraction-jobs
-> LMS trả queued
```

Các bước này không phải một transaction xuyên service và không có outbox được
xác nhận trong rà soát. Nếu lỗi giữa các bước, có thể còn candidate/document
orphan hoặc trạng thái mapping dang dở. LMS list candidate lại gọi extraction
status cho từng item để bổ sung trạng thái, có nguy cơ N+1 request khi danh sách
lớn. Đây là các điểm ổn định vận hành cần xử lý bằng thiết kế idempotency/
compensation trước khi tăng tải.

### 4.2 Identity và authorization

- Candidate/technical API PAI trong snapshot BrainHub nhận `X-PAI-Actor-ID` qua
  development actor adapter. LMS `PaiApiClient` cũng gửi header này sau khi
  `IdentityBridge` map LMS user sang PAI actor UUID.
- Một integration identity-link API ký số tồn tại tại
  `/api/v1/integration/candidates/{id}/lms-user-link`, nhưng candidate flow nêu
  trên chưa sử dụng signed actor context này.
- Do đó mapping LMS user → PAI actor có code nhưng **chưa được xác minh như
  production identity boundary thống nhất**. Browser không được tự mang role,
  organization hoặc actor UUID để quyết định quyền PAI.

### 4.3 Capability và learning

LMS project response từ PAI sang view model, có cờ `provisional: true`, evidence
reference và requirement-level status. Đây là đúng boundary nếu UI không diễn
giải `NOT_FOUND_IN_EVIDENCE`, `INSUFFICIENT` hay `CONTEXT_MISMATCH` thành “ứng
viên không có năng lực”. Các Playwright E2E dùng `E2E_PAI_API_URL` và fixture
manifest/ID; chúng chứng minh route/contract fixture, không tự chứng minh PAI
runtime, policy/pack active hoặc data provenance production.

### 4.4 Learning result và course projection

LMS adapter chỉ gửi delivery facts có `submission_id` sau khi LMS đã persist.
Tài liệu khẳng định nó không nằm trong `ProgressService` transaction và PAI
không sẵn sàng thì không được rollback completion LMS. Điều này phù hợp boundary
nhưng cũng có nghĩa đồng bộ learning result chưa tự động nếu chưa có caller,
retry vận hành hoặc event/outbox được triển khai và kiểm thử thực tế.

Course projection chỉ materialize LMS draft với `sourceSystem`/
`sourceReference`; không persist evidence, competency, policy hay provenance PAI
vào Prisma. Đây là kiểm soát đúng, nhưng publish/assign cần xác minh với dữ liệu
thực để tránh coi course delivery là competency verification.

## 5. Phát hiện chặn ổn định: hai snapshot PAI bị phân kỳ

So sánh trực tiếp giữa PAI trong BrainHub và PAI tại
`/home/cuongnguyene/workspace/pai-backend` cho thấy không phải cùng revision.

| Hạng mục | Snapshot BrainHub | Snapshot đối chiếu | Tác động |
| --- | --- | --- | --- |
| Test file | 214 | 216 | Không thể dùng kết quả test của bản này để kết luận bản kia. |
| Dependency | Không có `arq` trong `pyproject.toml` | Có `arq>=0.26,<1` | Course generation/worker không cùng runtime contract. |
| Alembic terminal | `20260916_46` và `20260917_42` là hai nhánh cuối tĩnh | `20260925_49` là một head sau merge | Database/migration deployment không thể giả định tương thích. |
| Replay protection | Chưa có migration `20260925_47` | Có durable actor-context nonce store | Snapshot BrainHub thiếu bản merge/ràng buộc mới nhất. |
| Course dispatch | Chưa có migrations `20260925_48` và `20260925_49` | Có durable dispatch/dispatch scope | Snapshot BrainHub vẫn có dấu hiệu in-process `asyncio.create_task` ở course generation, không bảo đảm restart/multi-instance. |
| Mã nguồn | Khác ở documents safety, integration actor context/capability/course APIs, main/config, course generation và curriculum | Có file/logic mới hơn | Adapter LMS phải pin một API version/revision cụ thể, không map theo folder copy. |

Không chạy được `alembic heads`, Ruff, mypy hay pytest cho snapshot BrainHub vì
`backend/.venv` không tồn tại. Không tự cài dependency hay apply migration trong
một lượt rà soát. Vì vậy trạng thái quality/runtime của snapshot này là **chưa
được xác minh**, không phải pass.

## 6. Mức sẵn sàng theo hạng mục

| Hạng mục | Mức | Lý do |
| --- | --- | --- |
| Domain/Persistence PAI | Có nền tảng | Nhiều module, contract và migration đã có. |
| Candidate/JD/capability API | Có code, cần runtime proof | PAI và LMS đều có facade/client; chưa có xác nhận môi trường chung. |
| Semantic governance | Có guardrail | Exact policy/pack và PREVIEW boundary được ADR/quy tắc yêu cầu; dữ liệu active runtime chưa xác minh. |
| LMS–PAI identity | Chưa ổn định production | Development actor header và signed identity context đang đồng thời tồn tại. |
| Async course generation | Không đồng nhất snapshot | Bản BrainHub thiếu ARQ/migration durable dispatch mới. |
| Database migration | Chặn release | Hai terminal branch ở snapshot BrainHub phải được merge/chọn baseline. |
| Test/quality gate | Chưa xác minh | Không có virtualenv/toolchain sẵn sàng trong snapshot BrainHub. |
| Full E2E | Chưa chứng minh | E2E phụ thuộc PAI URL, fixture manifest, actor mapping, DB/migration và services chạy thật. |

## 7. Thứ tự khuyến nghị để ổn định source flow

1. **Chọn một canonical PAI revision.** Không dùng đồng thời folder
   `ct_brain_hub/pai-backend` và workspace copy làm nguồn deploy/contract.
2. **Đồng bộ bằng Git/history thay vì copy thủ công.** Pin commit SHA cho LMS và
   PAI; ghi compatibility matrix gồm PAI API version, Alembic head, contract
   `v1`, migration prerequisite và required environment variables.
3. **Giải quyết migration trước runtime.** Merge/rebase snapshot BrainHub để có
   một Alembic head, rehearsal `upgrade head` trên database rỗng/bản sao và kế
   hoạch backup/rollback forward-only.
4. **Chuẩn hóa authentication boundary.** Quyết định một server-to-server actor
   context production, loại bỏ dependency production vào development header và
   thêm test authorization cho candidate, capability, learning và course paths.
5. **Làm bền luồng candidate upload.** Thiết kế idempotency cho toàn bộ sequence,
   cleanup/compensation khi bước sau lỗi và aggregate extraction status tránh N+1.
6. **Đồng bộ async runtime.** Chỉ bật course generation sau khi dependency,
   durable dispatch, worker, Redis/ARQ và reconciliation cùng revision; không
   chạy inference inline hoặc dựa vào task trong process.
7. **Chạy quality/E2E trên stack ghim phiên bản.** Ruff, format, mypy, pytest,
   Alembic head/current và một E2E thật: LMS identity → candidate CV → accepted
   profile → exact active policy/pack → PREVIEW → evidence review. Không đưa
   `VERIFIED`, credential hay auto learning path vào tiêu chí pass của luồng này.

## 8. Giới hạn và giả định

- Báo cáo coi `ct_brain_hub/pai-backend` là snapshot cần triển khai/tích hợp vì
  đây là thư mục người yêu cầu chỉ định. Chưa xác định được commit SHA canonical
  vì trạng thái Git không được dùng làm căn cứ trong lượt rà soát này.
- Không có bằng chứng database nào đã apply migration, semantic policy/pack nào
  đang `ACTIVE`, hay service PAI/LMS/Redis/MinIO/ClamAV nào đang healthy.
- Không đề xuất sửa trực tiếp API, schema hay kiến trúc trong báo cáo này; các
  thay đổi đó cần ADR, migration và test theo quy tắc repository.

## Kết luận cuối

PAI Backend và LMS integration đã có khối lượng implementation đáng kể, nhưng
điểm nghẽn hiện tại là **source-of-truth và deployment compatibility**, không
phải thiếu thêm UI hay thêm mapping endpoint. Ổn định revision, migration,
identity boundary và durable worker trước; sau đó mới dùng E2E để xác nhận các
mapping đang có. Trong trạng thái hiện tại, capability output phải tiếp tục được
trình bày là evidence-based `PREVIEW`, không phải kết luận năng lực hay quyết
định học/chứng nhận tự động.
