# PAI production readiness

PAI Course Studio is a bridge from LMS to a separately deployed PAI FastAPI
service. It is not safe to enable merely because the Frappe app has been
installed. This runbook is the operational gate before enabling it for users.

## Architecture boundary

```text
Browser -> Frappe LMS / pai_frappe -> signed HTTPS request -> PAI FastAPI
                                                       -> PAI database/worker/model gateway
```

- The browser must never receive the PAI API key or Ed25519 private key.
- Frappe owns LMS authorization, identity mapping and the local audit record.
- PAI owns authoring artifacts and asynchronous generation.
- PAI must not publish an LMS Course directly. The Studio now surfaces durable
  generation progress, failed-lesson retry and created draft versions; a human
  review/materialization step remains required.
- Frappe stores only correlation/audit metadata for authoring: the full training
  brief, prompt and author notes remain in PAI. `PAI Request` stores a redacted
  summary, not the submitted content.

## Pre-enable checklist

Complete every item before ticking **Enable PAI Integration** in PAI Settings.

## Local development only

For local `lms.test`, PAI is published at `http://127.0.0.1:18000` so it does
not conflict with Bench on port `8000`. `PAI Settings > Allow Insecure Local
PAI URL` may be enabled only when Frappe `developer_mode` is enabled, and only
accepts `http://localhost`, `http://127.0.0.1`, or `http://[::1]`. It is not a
deployment option: any non-loopback URL and every production/staging site must
use HTTPS with a trusted certificate.

1. Deploy PAI FastAPI separately with Python 3.13 or later, a persistent PAI
   database, its worker/queue service and approved model gateway.
2. Serve PAI via an internal HTTPS URL. Limit inbound traffic to the LMS
   application network; do not expose the integration endpoints publicly.
3. Set a non-empty PAI integration API key and matching `PAI Settings` value.
   Store its value only in PAI environment/secret storage and the Frappe
   Password field.
4. Generate a dedicated Ed25519 key pair for this integration. Configure the
   public key and key ID in PAI; save only the matching private key in the
   Frappe Password field.
5. Create the PAI organization and map each permitted LMS author to an enabled
   `PAI User Identity` record. Do not map a shared User account.
6. Run the PAI database migrations through `20260929_50`, deploy the
   `course-generation-worker`, and set `DOCUMENT_SCANNER=clamav`. The durable
   dispatch table, cross-instance replay-nonce store and ClamAV inspector are
   implemented in PAI; development fallbacks must not be used in production.
7. Configure monitoring for PAI HTTP failures, queue depth/job age, model
   provider errors and scanner failures. Retain request IDs for correlation.
8. Test a non-production authoring request through all four Studio stages and
   confirm that no LMS Course is created or published automatically.

## Deployment consistency gate

Applying the database migration alone is insufficient: the running PAI API and
worker images must be built from the same source revision that contains
`20260929_50`. Deploy the `backend`, existing extraction `worker`, and
`course-generation-worker` services together from
`~/workspace/pai-backend/devops/backend/docker-compose.yml`, using the
deployment's existing secret environment and network.

Before enabling LMS integration, verify all of the following:

1. `alembic current` reports `20260929_50 (head)` against the deployed PAI
   database.
2. A `course-generation-worker` container is running and connected to the same
   `REDIS_QUEUE_URL` and PAI database as the API service.
3. The deployed API OpenAPI schema contains the Course Studio generation and
   retry routes.

Do not start a worker from a separate source tree against a production database
unless that source is the image being deployed; API/worker code and migration
schema must move as one release.

### Runtime audit — 29/09/2026

Đã kiểm tra read-only deployment PAI BrainHub hiện có:

- `/health/ready` trả `200` và OpenAPI có đủ route Course Studio gồm create/brief/plan/review,
  generate, generation progress/retry, result review/approve/ready-for-materialization.
- Database báo Alembic revision `20260929_50` (head).
- Nhưng container `ct-brain-hub-pai-worker` đang chạy `app.extraction.runner`; chưa có một
  `course-generation-worker` riêng. Đây là worker cho extraction, không phải worker xử lý durable
  course-generation dispatch.

Kết luận: không bật Studio cho workflow Generate trên deployment này cho tới khi API, extraction
worker và `course-generation-worker` được deploy cùng source revision. Không đưa API/model key
vào log, ticket hay tài liệu; nếu key từng xuất hiện trong terminal, cần rotate tại model provider.

## Controlled activation

1. Sau khi deploy version bridge có idempotency, chạy `bench --site <site> migrate` để đồng bộ
   field `PAI Request.idempotency_key` và cho phép trạng thái local `Creating` trước remote create.
2. In **PAI Settings**, fill service URL, timeout, organization UUID, signing
   key ID, integration API key and actor private key. Leave `enabled` unchecked.
3. Create an enabled `PAI User Identity` for a single test Instructor.
4. Open `/lms/pai-studio` as that Instructor. The readiness banner must clear.
5. Create one request and complete brief confirmation, planning, review and
   generation. Record the LMS request name, PAI request ID and `X-Request-ID`
   from service logs.
6. Verify a learner cannot see PAI Studio and a different Instructor cannot
   read the test Instructor's local PAI Request.
7. Enable the integration only after the test result and logs are approved.

`check_pai_runtime_health` là API chỉ dành cho System Manager/Moderator để kiểm tra
`/health/ready` qua server-side bridge. Kết quả chỉ trả về cờ `ready` và tạo một
`PAI Operational Event` redacted; không trả service URL, body phản hồi, key hay secret.
API này có thể chạy khi integration chưa bật để xác minh hạ tầng, nhưng chỉ được chạy từ
mạng nội bộ đã được giới hạn như checklist ở trên.

## Incident response

- **PAI unavailable or invalid signing configuration:** immediately uncheck
  `Enable PAI Integration`. Existing LMS courses remain unaffected.
- **Suspected credential exposure:** disable the integration, revoke the PAI
  API key and signing key, generate a new key pair, update PAI first and then
  update Frappe settings.
- **Suspected replay or unauthorized request:** retain request IDs and audit
  records, disable the affected PAI identity, and investigate PAI verifier and
  queue logs before re-enabling.
- **Generation failure:** keep the request as an auditable draft; do not copy
  an incomplete artifact into LMS manually.
- **Unexpected bridge response:** treat it as unavailable. The bridge rejects
  non-versioned/invalid PAI envelopes and does not expose upstream error bodies
  to the LMS browser; use `X-Request-ID` and PAI logs for diagnosis.

## Current implementation boundary

The LMS bridge validates roles and ownership, uses Frappe Password fields for
secrets, signs short-lived actor context and keeps a local `PAI Request` audit
record. It does not itself provide PAI's durable job worker, shared nonce store
or malware scanner. Those controls belong to the separately deployed PAI
service and must be implemented before production activation.
