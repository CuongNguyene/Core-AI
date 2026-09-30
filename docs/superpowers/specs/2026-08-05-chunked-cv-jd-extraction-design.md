# Chunked CV/JD Extraction Design

## Goal

Make real PDF/DOCX extraction resilient to the CTPAI Gateway context limit
without bypassing ModelGateway or PrivacyGateway.

## Confirmed provider contract

Safe live probes establish that the current Gateway accepts an otherwise
identical harmless request at output budgets 2048, 4096 and 8192, but rejects
16384. This design treats 8192 as a provider ceiling. It does not assume that
the published 16,384-token value is an output-token limit.

## Flow

```text
CLEAN document in MinIO
  -> worker parses normalized text
  -> deterministic chunks (<= 2000 chars, 150-char overlap)
  -> each chunk: ModelGateway -> PrivacyGateway -> local-vllm
  -> schema-valid candidate claims with source excerpts
  -> deterministic normalize/deduplicate/relocate merge
  -> one PENDING_REVIEW extraction profile
```

The router remains upload/enqueue/read only. The worker remains the only
extraction caller of ModelGateway.

## Chunk contract

A chunk has an ordinal, document-relative `start_offset`/`end_offset` and text.
Boundaries preferentially use newline/paragraph boundaries. The overlap is
used only to preserve context. Chunk model output must not invent an offset: a
supported candidate carries a bounded source excerpt and the application
requires that excerpt to occur exactly once in the chunk. The application then
constructs and validates the final document-relative locator.

Chunk extraction receives `max_tokens=2048`. The provider's configurable
ceiling is 8192; only trusted application code may choose an operation budget.
The model receives a schema and the existing explicit untrusted-document
boundary. It cannot change system rules, call tools or promote evidence into
verified competency.

## Merge and failure rules

- Supported chunk claims must validate with value, confidence and bounded source
  excerpt. An absent or ambiguous excerpt fails the chunk before merge.
- Equal normalized values with overlapping locators are one claim; the earliest
  document-relative locator wins deterministically.
- Different evidence is retained as separate claims; no cross-chunk confidence
  aggregation or competency inference occurs.
- Any chunk transport, privacy, structured-output or locator failure marks the
  parent job failed closed with `chunk_<ordinal>:<safe_category>`.
- Profile creation happens only when all chunks validate and merge.

## Testing

- Unit-test deterministic boundary selection, overlap, final short chunk and
  document-relative locator conversion.
- Unit-test deduplication, non-overlapping retained evidence and invalid locator
  rejection.
- Contract-test request-specific output budgets and the 8192 ceiling.
- Integration-test multi-chunk fake CV/JD extraction and safe first-failure
  behavior; assert audit/profile never exposes raw document/chunk/prompt/output.
- Repeat the live CTPAI test with the supplied CV/JD only after unit/integration
  tests pass, recording safe job/profile status rather than raw response.

## Non-goals

- No parallel chunk execution, chunk persistence, public chunk API or LLM-based
  merge.
- No new external provider, direct domain HTTP call, competency decision or
  automatic profile acceptance.
