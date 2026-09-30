# INTEGRATION-06E PAI Candidate Contract Readiness Gap Report

## Overall status

`INTEGRATION-06E.0` is **design-ready but implementation-blocked**. The PAI
extraction and evidence primitives are present, but the Candidate business
aggregate and candidate-facing contract do not yet exist. No LMS adapter or
frontend should be implemented against technical document/profile/job IDs.

## Critical gaps

### C1 — Missing Candidate aggregate

No stable PAI-owned `candidate_id`, organization-scoped aggregate, or
candidate/document association currently exists. Implementing the adapter
first would force a fake mapping and make identity impossible to correct later.

### C2 — Missing Candidate API

PAI exposes technical document and extraction endpoints, but not:

```text
GET /api/v1/candidates
GET /api/v1/candidates/{candidate_id}
GET /api/v1/candidates/{candidate_id}/extraction-status
```

### C3 — Missing evidence retrieval API

Claims have locators and evidence references inside extraction output, but PAI
does not yet expose an authorized candidate claim/evidence read endpoint:

```text
GET /api/v1/candidates/{candidate_id}/claims/{claim_id}/evidence
```

The LMS cannot safely implement this by reading raw documents or profiles.

## High gaps

### H1 — Candidate claim identity and read projection

The current output has array entries and profile versions but no stable
candidate claim identity. A future projection must preserve source profile
version, evidence references, context, and provenance.

### H2 — Aggregate review lifecycle

Profile transitions exist, but Candidate Review requires a candidate-level
summary, current review subject, version conflict behavior, and idempotent
accept/revision/reject commands.

### H3 — Production identity bridge wiring

PAI already has organization/role/delegation concepts and a development-only
actor header. The Candidate API still needs the production Identity Bridge
contract and server-side actor resolution. LMS JWT claims must not be mapped to
PAI authorization in the browser.

### H4 — Candidate/document ownership authorization

Document ownership is organization/actor scoped, but candidate association and
candidate-specific access checks are not modeled. This is required before
listing candidates or returning evidence.

## Medium gaps

### M1 — PaiApiClient extension

The future LMS adapter needs CandidateClient, ExtractionClient,
EvidenceClient, and ReviewClient groups with stable error/idempotency behavior.

### M2 — Retention and unavailable evidence behavior

The future contract must define how expired, deleted, or revoked source
documents affect evidence retrieval without rewriting historical claims.

### M3 — Candidate list/search read model

The current repositories are technical-resource repositories. A candidate list
needs organization-scoped pagination, status filters, and a stable aggregate
projection.

## Readiness matrix

| Capability | Current PAI primitive | Candidate boundary | Readiness |
|---|---|---|---|
| secured document upload | `DocumentRecord` + blob store | candidate document association | partial |
| extraction | jobs/profiles/review transitions | aggregate status projection | partial |
| candidate identity | none | stable PAI `candidate_id` | missing |
| claims | profile output/CandidateProfile | stable `claim_id` projection | partial |
| evidence | locators/evidence items | authorized retrieval endpoint | missing |
| review actions | profile commands | candidate commands/versioning | partial |
| authorization | Actor/org/role/delegation primitives | identity bridge + candidate policy | partial |
| LMS client | integration APIs for learning | candidate client groups | missing |

## Recommended implementation sequence

1. `INTEGRATION-06E.1`: implement Candidate aggregate and
   candidate-document/profile/claim provenance model in PAI.
2. Add organization-scoped Candidate read service and claim/evidence resolver.
3. Add production Identity Bridge context and candidate authorization policy.
4. Add Candidate API v1 plus contract/integration tests.
5. Add `PaiApiClient` resource groups against the implemented contract.
6. Implement LMS adapter only after PAI contract tests pass.

No migration, API, LMS, or frontend work belongs in `INTEGRATION-06E.0`.

## Verification of this design milestone

- Existing PAI extraction/document/profile/evidence code was inspected.
- Technical IDs were explicitly kept separate from candidate identity.
- No production code, schema, migration, Docker runtime, or LMS repository was
  changed for this design milestone.
- The next implementation decision is whether the Candidate aggregate model
  should be added directly or first split into write aggregate and read
  projection; that decision belongs to `06E.1`, not the LMS adapter.
