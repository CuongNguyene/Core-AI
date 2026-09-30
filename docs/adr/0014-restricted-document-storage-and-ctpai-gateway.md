# ADR-0014: Restricted Document Storage and CTPAI Gateway Extraction

## Status

Accepted.

## Context

ADR-0006 limits PR-004 extraction to source-controlled fixtures because raw
CV/JD storage, retention and access control were undecided. The MVP product
scope requires PDF/DOCX upload and the organization has confirmed that the
CTPAI Gateway is organization-controlled infrastructure allowed to process
restricted CV/JD data.

## Decision

- Raw PDF/DOCX is stored only in the configured object-store bucket. PostgreSQL
  stores a random document ID, opaque object key, SHA-256, declared/detected
  content type, byte size, owner/organization, lifecycle state and retention
  deadline. Original filename, document text, prompt and raw model response are
  not persisted in application tables or audit metadata.
- MinIO is the development/integration object-store implementation. It remains
  non-production infrastructure under ADR-0002; production storage, encryption
  key management, backup and retention execution need a later infrastructure ADR.
- Uploaded documents enter `QUARANTINED`. A development-only safety inspector
  validates permitted PDF/DOCX signatures, configured size limit and a safe
  failure path before a document can become `CLEAN`. Any inspection error,
  unsupported format or rejected document fails closed. A production malware
  scanner replaces this adapter before production upload is enabled.
- Extraction workers resolve only `CLEAN`, non-expired documents through a
  document-source adapter. PDF/DOCX text is parsed in the worker, never in the
  HTTP request. Source locators refer to the normalized parsed text offsets.
- The CTPAI Gateway is an internal `local-vllm` ModelGateway provider. It maps
  trusted application messages to the gateway `prompt_system`/`prompt_user`
  contract, uses its bearer key from configuration, and returns provider text to
  existing structured-output validation. It never bypasses `PrivacyGateway` or
  routing; restricted extraction remains `local-vllm` only.
- Audit continues to persist only safe provider/model/template/schema/policy/
  correlation/latency/usage/outcome metadata. Extraction profiles remain
  `PENDING_REVIEW` and do not verify competency.

## Alternatives considered

- Store raw files or parsed text in PostgreSQL: rejected because it increases
  backup, access-control and PII exposure scope.
- Let API routers parse files and call the gateway: rejected because it blocks
  requests and bypasses the durable worker boundary.
- Treat the public-looking gateway URL as an external provider: rejected after
  organizational confirmation that it is controlled internal infrastructure;
  it remains routed as local and is not an external fallback.
- Enable upload without a quarantine/safety gate: rejected because malformed or
  uninspected documents must not reach parsers or model workers.

## Consequences

- The MVP gains a development-ready real-document vertical slice while keeping
  raw artifacts out of SQL/audit/logs.
- The storage adapter and CTPAI provider are replaceable boundaries; domain
  extraction continues to depend only on `DocumentSource` and `ModelGateway`.
- The current fixture source remains available for deterministic unit/golden
  tests.

## Migration

Add document metadata records and indexes for owner/organization/state/retention
lookup. Existing extraction jobs continue to reference document IDs; fixture
document IDs remain valid. No raw CV/JD is migrated into the database.
