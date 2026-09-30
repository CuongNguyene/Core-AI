# ADR-0017: Chunked Restricted-Document Extraction and Output Budgets

## Status

Accepted.

## Context

The CTPAI Gateway accepts harmless probes with `max_tokens` values up to 8192,
but rejects `16384` with HTTP 500. Its documented 16,384-token capacity must
therefore be treated as a total context constraint, not as a supported output
budget for every request. Sending an entire parsed CV or JD plus a JSON schema
in one request also makes failure depend on document size and model reasoning.

Raw CV/JD remains restricted, must stay in MinIO and must only cross the
existing `ExtractionWorker -> ModelGateway -> PrivacyGateway -> local-vllm`
boundary. The platform must preserve source-backed evidence and must not turn
chunk-level model output into a competency decision.

## Decision

- The CTPAI Gateway provider has a validated maximum output ceiling of 8192.
  `max_tokens=16384` is rejected and is not configured.
- Each inference request carries a trusted, use-case-specific output budget.
  CV/JD chunk extraction starts with 2048; it is distinct from the provider
  ceiling and may only be raised after a contract test proves that outcome.
- The extraction worker splits parsed normalized text into deterministic,
  sequential chunks of at most 2000 characters with a 150-character overlap.
  It prefers paragraph/line boundaries when available and otherwise splits at
  a character boundary. Chunks retain document-relative start/end offsets.
- Each chunk is independently rendered inside the existing untrusted
  `<document>` prompt boundary and validated against an internal chunk-output
  schema. A supported chunk claim has a bounded source excerpt but no
  model-supplied locator.
- The application must locate that excerpt exactly once inside the chunk before
  creating the existing document-relative `SourceLocator`. Ambiguous or absent
  excerpts fail the chunk closed. A deterministic merge normalizes values and
  removes duplicate/overlapping claims. It does not call an LLM, infer missing
  evidence, choose a competency level or create verified competency.
- A chunk failure fails the entire job closed. The safe job category identifies
  the chunk ordinal and failure class but never contains document text, prompt,
  model response, source excerpt or API credentials.
- Audit metadata retains provider/model/template/schema/policy/correlation and
  aggregate safe metrics. It does not persist chunks or raw content.

## Alternatives considered

- Raise one global `max_tokens` to 8192 for every operation: rejected because
  the smallest valid output budget is safer, lower latency and independent of
  the provider ceiling.
- Send the whole document with a reduced output budget: rejected because large
  documents still create variable context pressure and weak source localization.
- Use an LLM to merge chunk results: rejected because it adds an inference step
  and can hallucinate or double-count evidence.
- Parallelize chunks: deferred. Sequential processing keeps gateway load,
  ordering, retry and audit behavior deterministic for the MVP.

## Consequences

- Extraction jobs gain deterministic chunking and a small trusted output-budget
  policy without changing public upload/job/profile APIs.
- Existing `SourceLocator` remains document-relative, so matching and review do
  not consume a new raw-text representation.
- Long documents take multiple bounded model calls and may fail safely at a
  specific chunk; retry/reconciliation remains owned by the durable job worker.

## Migration

No database migration is required. Existing profiles remain immutable. New
extraction attempts record a new prompt/schema contract version and safe chunk
aggregate metadata.
