# INTEGRATION-06E PaiApiClient Future Boundary

## Status

Proposed client boundary for a later LMS adapter. No client code is added in
`INTEGRATION-06E.0`.

## Client composition

```text
PaiApiClient
  +-- CandidateClient
  +-- ExtractionClient
  +-- EvidenceClient
  +-- ReviewClient
```

The root client owns base URL, authentication/identity-bridge transport,
timeouts, correlation IDs, idempotency headers, API version, and safe error
decoding. Resource clients own endpoint paths and response contracts.

## CandidateClient

Proposed operations:

```text
list_candidates(filter, cursor, limit) -> CandidatePage
get_candidate(candidate_id) -> CandidateDetail
create_candidate(input) -> CandidateSummary
attach_document(candidate_id, upload) -> CandidateDocumentStatus
```

This client never exposes technical extraction IDs as candidate IDs and never
constructs candidate identity from a document response.

## ExtractionClient

Proposed operations:

```text
get_extraction_status(candidate_id) -> CandidateExtractionStatus
```

The candidate-facing client returns aggregate status and safe profile version
information. Direct technical workflow calls remain PAI-internal unless a
future contract explicitly delegates them.

## EvidenceClient

Proposed operations:

```text
get_claim_evidence(candidate_id, claim_id) -> EvidencePage
```

The client treats evidence as a PAI-authorized response. It does not read the
document store, resolve locators locally, or fall back to raw CV retrieval.

## ReviewClient

Proposed operations:

```text
accept(candidate_id, expected_profile_version, idempotency_key, reason)
request_revision(candidate_id, expected_profile_version, idempotency_key, reason)
reject(candidate_id, expected_profile_version, idempotency_key, reason)
```

All actions are versioned and idempotent. The client does not send an actor ID;
the server-side identity bridge supplies the authentication context.

## Shared client rules

1. Use `/api/v1` and an explicit contract version.
2. Forward a correlation ID for tracing and an idempotency key for commands.
3. Decode stable PAI error codes, not database/provider messages.
4. Preserve `401`, `403`, `404`, and `409` semantics for adapter decisions.
5. Do not retry review commands unless the idempotency key is reused.
6. Do not log raw CV/JD, excerpts, access tokens, or provider payloads.
7. Keep PAI resource references opaque to LMS business logic.

## Boundary with existing PAI APIs

Current `/documents`, `/extraction-jobs`, and `/extraction-profiles` endpoints
are technical PAI APIs. `PaiApiClient` must not simply rename those resources
to candidates. The future CandidateClient composes a PAI-owned aggregate read
model, while ExtractionClient/EvidenceClient expose only the safe views needed
by the review workflow.

## Test contract for future implementation

The client implementation should have contract tests for:

- candidate ID remaining stable when a document is replaced;
- no `document_id == candidate_id` or profile/job aliasing;
- organization/authorization errors preserved;
- evidence unavailable/unresolved states preserved;
- stale review version returns `409`;
- repeated idempotent review command does not create a second decision;
- raw content and secrets absent from logs.
