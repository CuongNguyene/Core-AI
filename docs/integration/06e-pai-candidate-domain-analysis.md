# INTEGRATION-06E.0 PAI Candidate Domain Analysis

## Scope and decision

This document inspects the current PAI extraction domain and identifies the
boundary required before a future Candidate API implementation. It is a design
artifact only. It does not add a database table, endpoint, migration, LMS
adapter, or frontend behavior.

PAI currently owns document ingestion, extraction, evidence/provenance, and
review of extraction profiles. It does not yet own a first-class Candidate
aggregate. A document, extraction job, or extraction profile is therefore not a
candidate identifier.

## Current model

```text
StoredDocument
  id: UUID
  owner_actor_id / organization_id
  kind: cv | jd
  object_key / sha256 / retention / status

ExtractionJob
  id: workflow identifier
  document_id
  status: queued | running | succeeded | failed
  profile_id (when succeeded)

ExtractionProfile
  id: workflow output version
  job_id / document_id / document_kind
  version / supersedes_profile_id
  review_state
  normalized output
  optional CandidateProfile projection for CVs
  audit metadata

Evidence
  extracted claims carry source_locator, source_excerpt, confidence,
  evidence type/status, and evidence references. CandidateProfile entities
  carry context-preserving EvidenceItem objects. These are currently nested
  in profile/output representations rather than exposed by a Candidate API.
```

### Document ownership

`DocumentRecord` is a secured document-storage record. It identifies the
organization and actor that uploaded the object, its hash, storage key,
retention, content type, and clean/quarantine status. It is a source artifact,
not a person or candidate.

### Extraction ownership

`ExtractionJobRecord` is an asynchronous workflow record. Its ID exists to
track provider calls and job status. `ExtractionProfileRecord` stores versioned
output and review transitions (`PENDING_REVIEW`, `CORRECTED`, `ACCEPTED`,
`NEEDS_REVISION`, `REJECTED`). The current API exposes those technical
resources directly, but neither record is a business aggregate.

### Candidate intelligence and evidence

The CV compatibility output is `CandidateProfile` (`schema_version` 2.0),
with employment, project, research, education, publication, skill,
credential, activity, and finding projections. Its evidence items preserve
context, usage, excerpt, confidence, original evidence type, and optional
source locator. The accepted extraction output also preserves source locators
and evidence references. This is sufficient material for a future candidate
read model, but it is not currently keyed by a stable `candidate_id` or
`claim_id` contract.

## Missing concepts

### 1. Stable Candidate aggregate

There is no PAI-owned record that answers “which person/business candidate do
these documents and profiles belong to?” The first implementation must create a
stable opaque `candidate_id` independently of every document, job, and profile
ID.

### 2. Candidate-to-document relationship

Documents currently have owner and organization metadata, but no candidate
association. A future association must support a primary CV and additional
candidate documents without changing the document storage identity.

### 3. Candidate-level claim identity

The extraction schema has claim array positions and locators, but no stable
cross-version claim identity. A future candidate read model must define an
opaque `claim_id` whose provenance points to a profile version and source
locator. Array index, profile ID, and document ID must not be presented as
candidate IDs.

### 4. Aggregate review state

Profile review state exists, but Candidate Review needs a candidate-level
state that can summarize the current accepted profile, pending profile, or
revision/rejection state. The summary must retain the underlying profile
version and audit history without exposing workflow internals by default.

### 5. Evidence retrieval boundary

Source locators exist inside extraction outputs, but there is no Candidate API
that authorizes retrieval of claim evidence, resolves source document access,
and applies PAI privacy policy to excerpts. This must be a PAI-owned read
operation, not an LMS-side reconstruction from raw IDs.

## Lifecycle gaps

```text
Current technical lifecycle:

Document upload -> clean document -> extraction job -> profile version
                                      -> reviewer correction/accept/revision/reject

Required business lifecycle:

Candidate created
  -> candidate document attached
  -> extraction pending
  -> candidate pending review
  -> accepted | needs revision | rejected
  -> archived (future explicit action)
```

The business lifecycle must reference technical workflow records internally,
but must not derive its identity from them. A candidate can have multiple
documents and multiple superseding profile versions; only one profile version
is the current review subject at a time.

## Ownership boundary

PAI owns the Candidate aggregate, candidate intelligence, extraction jobs and
profiles, source evidence, provenance, review transitions, organization scope,
and authorization decisions.

The LMS owns user authentication, the review UI, presentation state, and
training delivery. The LMS may request candidate data through a future adapter,
but it must not infer candidate identity, reconstruct evidence, or decide PAI
authorization in the browser.

## Readiness conclusion

PAI has the source and extraction primitives needed for a Candidate aggregate,
but not the aggregate identity, candidate/document association, claim identity,
candidate-level read model, or evidence retrieval API. These are the blocking
items for `INTEGRATION-06E.1 PAI Candidate Domain Implementation`.
