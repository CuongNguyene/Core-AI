# Document Ingestion and CTPAI Gateway Extraction Design

## Goal

Enable a development vertical slice that uploads a PDF/DOCX CV or JD, stores
the raw artifact in MinIO, extracts text asynchronously through the internal
CTPAI Gateway, validates the existing CV/JD schemas and persists only a
reviewable normalized profile with safe audit metadata.

## Boundaries

- Raw files are restricted data. They stay in MinIO and are not returned by
  extraction APIs, embedded in logs, audit, profile JSON or prompts persisted
  by the application.
- A document is not eligible for extraction until `CLEAN`; all unknown or
  unsafe states fail closed.
- `ExtractionWorker` remains the only caller of `ModelGateway` for extraction.
  Routers upload/enqueue/read only.
- `CTPAIGatewayProvider` implements the existing provider protocol with ID
  `local-vllm`. `PrivacyGateway` inspection and `RoutingPolicy` run unchanged
  before it is resolved.
- Long CV/JD documents are split by the worker into deterministic chunks.
  Chunk calls validate against the chunk extraction schemas and the merged
  profile validates against `CVExtractionOutput` or `JDExtractionOutput`.
  Invalid JSON/schema or locator failures mark the job failed with a safe
  chunk category.
- Extraction prompts use a trusted system instruction and explicit `<document>`
  delimiters. Instructions found in a raw document cannot alter output format,
  reveal secrets, call tools or alter extraction rules.
- A supported claim requires its value, stable source locator and a source
  excerpt capped at 500 characters. Unknown/insufficient claims cannot contain
  a value or source evidence.

## Data flow

```text
POST /documents (PDF/DOCX multipart)
  -> document metadata QUARANTINED + opaque MinIO object
  -> development safety inspection
  -> CLEAN or REJECTED
POST /extraction-jobs {document_id, document_kind}
  -> queued job
worker
  -> resolve CLEAN object -> parse normalized text
  -> split into deterministic chunks
  -> PrivacyGateway -> RoutingPolicy(local-vllm) -> CTPAI Gateway
  -> chunk output validation -> deterministic merge -> extraction profile
     PENDING_REVIEW + safe audit
```

## API

- `POST /documents`: authenticated development actor uploads one PDF/DOCX;
  response contains document metadata, not file content.
- Existing `POST /extraction-jobs` accepts either a valid fixture ID or a CLEAN
  stored document ID whose kind matches. It never accepts raw content.
- Existing job/profile/review endpoints retain ownership and reviewer guards.

## Failure behavior

- Oversized, unsupported, malformed, quarantined, rejected, expired or missing
  documents are rejected with a safe API/job error code.
- Object-store, parsing, privacy, gateway transport and output validation errors
  do not disclose raw content. Worker persists a safe failed status only.
- Gateway transport uses the configured 200-second timeout, a Gateway-validated
  8192 output-token ceiling and bounded retry;
  privacy/routing/schema failures do not retry via another provider.
- Job failure categories distinguish `provider_timeout`,
  `provider_response_invalid`, `invalid_structured_output:<category>` and
  `chunk_<ordinal>:<safe_category>`; they never contain raw prompt, document,
  model response or source excerpt.

## Test strategy

- Unit-test object key generation, content/signature validation, state gate and
  retention eligibility with an in-memory document/blob adapter.
- Contract-test CTPAI request mapping, bearer header, timeout, non-2xx, response
  shape and invalid structured JSON using `httpx.MockTransport`.
- Integration-test upload -> clean -> enqueue -> chunked worker -> persisted
  normalized CV and JD profiles using fake parser/model adapters; assert no
  raw bytes/text occur in metadata/audit.
- Keep fixture golden tests deterministic and add PDF/DOCX parser fixtures.
