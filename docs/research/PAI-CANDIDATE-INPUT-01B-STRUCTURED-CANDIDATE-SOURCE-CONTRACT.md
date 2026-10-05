# PAI-CANDIDATE-INPUT-01B — Structured Candidate Source Contract

Status: **Design proposal — upstream contract not frozen**
Scope: contract/design only. No production schema, API, persistence, adapter, migration, or runtime behavior is introduced by this document.

## 1. Executive decision

**CONTRACT_READY_WITH_OPEN_UPSTREAM_CLARIFICATIONS** for a conceptual source boundary; **not ready for production integration freeze**.

Core-AI can specify the minimum identity and source groups it is willing to receive without requiring an ATS to produce PAI semantics. A stable source candidate key and organization mapping are necessary for safe identity resolution, but the exact ATS/HRM fields and availability are unconfirmed. Snapshot identity, versioning, replay, ordering, and partial-update behavior are also open. These uncertainties are documented rather than guessed.

`source_candidate_ref` is a required *contract concept*, not a claim that Payload v2 already contains such a field. If ATS/HRM cannot supply a stable key, production ingestion is blocked pending an upstream identity decision; name, email, and phone are not fallback keys.

### Evidence labels

- **OBSERVED_FROM_REPOSITORY** — behavior or shape found in the current Core-AI source.
- **DESIGN_DECISION** — fixed boundary supplied by milestone 01A / this brief.
- **PROPOSED_CONTRACT** — recommended input shape and field semantics, not an upstream fact.
- **OPEN_CLARIFICATION** — decision that ATS/HRM must confirm before integration freeze.

## 2. Scope and authority boundary

**DESIGN_DECISION:** ATS/HRM is authoritative for source records and their source-reported values. Core-AI is authoritative for semantic interpretation, evidence policy, capability assessment, gaps, LearningNeeds, and recommendations.

This contract transports source facts, references, and source assertions. It does not assert that a record is true, verified, current, or sufficient for a capability decision. A source-confirmed fact is not a PAI-verified capability.

Out of scope: ATS/HRM connectivity, adapter implementation, CandidateProfile changes, evidence persistence, capability-analysis changes, Candidate identity persistence, Role/JD mapping, capability IDs/levels, learning gaps, LearningNeeds, recommendation logic, and creation of CV/Document records from structured data.

## 3. CandidateSourceEnvelope

**PROPOSED_CONTRACT — conceptual JSON example.** Field names/types require confirmation against the final upstream Payload v2. The example intentionally contains no Core-AI Candidate UUID, CV document, fake excerpt, canonical capability ID, or inferred level.

```json
{
  "schema_id": "pai.candidate-source",
  "schema_version": "v1",
  "organization_ref": "<source organization reference>",
  "identity": {
    "source_system": "<stable source-system code>",
    "source_candidate_ref": "<immutable source candidate reference>",
    "employee_ref": "<optional HR employee reference>"
  },
  "source_snapshot": {
    "source_snapshot_ref": "<optional source event/snapshot reference>",
    "source_version": "<optional source version>",
    "source_updated_at": "<optional RFC 3339 timestamp>",
    "observed_at": "<optional upstream observation timestamp>"
  },
  "career_history": [
    {
      "source_record_ref": "<optional stable record reference>",
      "organization_name": "Example Co.",
      "role_title": "Data Engineer",
      "start_date": "2023-01-01",
      "end_date": null,
      "responsibilities": "Developed Python data pipelines...",
      "technologies": [{"name": "Python"}],
      "source_updated_at": "<optional RFC 3339 timestamp>"
    }
  ],
  "education": [],
  "certifications": [],
  "languages": [],
  "tools": [],
  "projects": [],
  "interviews": [],
  "assessments": [],
  "auxiliary_signals": {
    "ats_ai_scanning": null
  }
}
```

The Core-AI integration transport may use the existing outer `IntegrationEnvelopeV1` convention (`schema_version: "v1"`, `data`). That wrapper is separate from the candidate source payload's own `schema_id`/`schema_version`; this document does not define a route or transport endpoint. **OBSERVED_FROM_REPOSITORY:** the existing integration wrapper and learner identity references use strict schemas and opaque string external IDs; internal organization and Candidate identities are UUIDs ([integration schemas](../../services/pai-backend/backend/app/integration/schemas.py#L8), [Candidate schema](../../services/pai-backend/backend/app/candidate/schemas.py#L24)).

## 4. Field dictionary

Classification applies to the proposed contract, not to unconfirmed upstream availability. “REQUIRED” means necessary to resolve and scope an incoming candidate envelope. It does not mean ATS v2 is confirmed to provide that field.

| Path | Type | Classification | Authority | Purpose | Notes / Open issue |
|---|---|---|---|---|---|
| `schema_id` | string | REQUIRED | Contract | Identify payload family | Proposed stable value `pai.candidate-source` |
| `schema_version` | string | REQUIRED | Contract | Version payload shape | Payload contract version, not candidate revision |
| `organization_ref` | opaque string | REQUIRED | ATS/HRM namespace | Resolve tenant/organization scope | Exact upstream ref and mapping to Core-AI organization UUID are open |
| `identity.source_system` | opaque string | REQUIRED | Source registry | Namespace source identity | Stable source-system code; do not use display name |
| `identity.source_candidate_ref` | opaque string | REQUIRED | ATS/HRM | Stable candidate identity and lineage | **OPEN_CLARIFICATION / production blocker:** confirm immutable key, uniqueness scope, and transfer to HRM |
| `identity.employee_ref` | opaque string or null | CONDITIONAL | HRM | Link candidate to employee when one exists | Not required for pre-hire candidates; not a Core-AI ID |
| `source_snapshot.source_snapshot_ref` | opaque string or null | CONDITIONAL | ATS/HRM | Identify/replay a specific source delivery | Needed for reliable delivery dedup if the source exposes it; availability open |
| `source_snapshot.source_version` | string/number or null | CONDITIONAL | ATS/HRM | Source ordering/version lineage | Meaning and monotonicity open; do not infer from `updated_at` |
| `source_snapshot.source_updated_at` | RFC 3339 timestamp or null | OPTIONAL | ATS/HRM | Source freshness context | Timestamp does not alone define ordering or replay semantics |
| `source_snapshot.observed_at` | RFC 3339 timestamp or null | OPTIONAL | ATS/HRM | Source observation time when available | Core-AI receipt time is operational metadata, not an ATS fact |
| `career_history[]` | array of records | OPTIONAL | ATS/HRM | Work history/current-state evidence source | Absence does not invalidate the envelope |
| `career_history[].source_record_ref` | opaque string or null | CONDITIONAL | ATS/HRM | Stable record lineage/dedup | Confirm availability and scope |
| career organization/title/dates | source strings/date/null | OPTIONAL | ATS/HRM | Preserve supplied career facts | No inferred capability, seniority, or level |
| career responsibilities/description | source text/null | OPTIONAL | ATS/HRM | Preserve narrative for later semantic processing | Do not rewrite into a fake CV |
| career technologies[] | array of raw names | OPTIONAL | ATS/HRM | Preserve explicitly captured tools | Raw labels only; not canonical capabilities |
| `education[]` | array of records | OPTIONAL | ATS/HRM | Preserve education records | No capability conclusion at contract level |
| `education[].source_record_ref` | opaque string or null | CONDITIONAL | ATS/HRM | Stable record lineage | Availability open |
| education institution/degree/field/dates/status | source values/null | OPTIONAL | ATS/HRM | Preserve source-reported education | Completion/status meanings require source semantics |
| `certifications[]` | array of records | OPTIONAL | ATS/HRM | Preserve credential records | No verification inference |
| `certifications[].source_record_ref` | opaque string or null | CONDITIONAL | ATS/HRM | Stable record lineage | Availability open |
| certification name/issuer/dates | source values/null | OPTIONAL | ATS/HRM | Preserve source facts | Expiry only when supplied |
| certification verification status | source value/null | CONDITIONAL | ATS/HRM | Preserve explicit verification assertion | Include only if source meaning is documented; not PAI verification |
| `languages[]` | array of records | OPTIONAL | ATS/HRM | Preserve language values independently | CandidateProfile has no dedicated language entity; adapter/domain decision deferred |
| language name/proficiency/scale | source values/null | OPTIONAL | ATS/HRM | Preserve raw language and source scale | Do not map to skill level |
| `tools[]` | array of `{name, ...}` | OPTIONAL | ATS/HRM | Preserve raw tools/technologies | No canonical mapping in this contract |
| `projects[]` | array of records | CONDITIONAL | ATS/HRM | Preserve projects if upstream has them | Missing project support does not invalidate envelope |
| `interviews[]` | array of records | OPTIONAL | ATS/HRM | Preserve interview source records | Exact upstream availability open |
| interview source ref/date/round/evaluator ref | source values/null | OPTIONAL | ATS/HRM | Provenance and context | Avoid forwarding interviewer names absent a justified need |
| interview recommendation/comment/overall score/scale | source values/null | OPTIONAL | ATS/HRM | Preserve generic feedback | Not automatically verified capability evidence |
| `interviews[].criteria[]` | array of source rubric records | CONDITIONAL | ATS/HRM | Preserve structured criteria if they exist | Criterion ID/name/score/scale/comment remain source semantics |
| `assessments[]` | array of records | OPTIONAL | ATS/HRM | Preserve assessment records | Overall-only is valid |
| assessment source ref/type/name/result/score/scale/report ref | source values/null | OPTIONAL | ATS/HRM | Preserve source result and lineage | A report reference is not report content or verified truth |
| `assessments[].dimensions[]` | array of source dimensions | CONDITIONAL | ATS/HRM | Preserve detail if upstream provides it | Dimension names/scores/scales remain source semantics |
| `auxiliary_signals.ats_ai_scanning` | object or null | AUXILIARY | ATS AI | Preserve optional recruitment-matching signal | Entire block may be absent; never capability truth |
| bank, salary, tax, insurance, national ID, passport, home address, vehicle, unrelated HR attributes | any | OUT_OF_SCOPE | — | Data minimization | Do not forward in this PAI contract |
| job/designation/Role/JD references | any | OUT_OF_SCOPE | — | Separate target-role contract | No Role Registry or JD mapping here |
| PAI capability ID/level, CandidateProfile, gap, LearningNeed, recommendation | any | OUT_OF_SCOPE | — | Core-AI semantic outputs | Must not be authored as ATS source fields |

An envelope with no interviews, assessments, or AI scanning is valid. An envelope may also have empty optional career/education groups; that means it can be accepted as source data but may be **not yet analyzable/recommendation-ready** downstream. Contract validity and analysis eligibility are separate.

## 5. Identity and lineage

```text
ATS Candidate --source_candidate_ref--> HRM Employee --employee_ref--> Core-AI Candidate
```

This is a conceptual lineage, not a statement that ATS currently sends both references or that HRM preserves them. `source_candidate_ref`, `employee_ref`, and `organization_ref` are external opaque references. Core-AI owns its Candidate UUID. Never use email, name, or phone as canonical join keys.

**OBSERVED_FROM_REPOSITORY:** Candidate has internal `candidate_id: UUID` and `organization_id: UUID`; current LMS identity bridge stores an external `source_system` + opaque `source_subject_ref` scoped by organization UUID ([CandidateIdentityLink](../../services/pai-backend/backend/app/integration/identity_bridge.py#L33), [lookup scope](../../services/pai-backend/backend/app/integration/identity_bridge.py#L97)). That pattern supports opaque external references, but the existing bridge is for LMS user identity and does not establish an ATS candidate contract.

`organization_ref` is required conceptually so source identity is tenant-scoped. How the upstream organization reference maps to Core-AI's internal organization UUID is an integration/identity decision, not a UUID-format assumption in this payload.

## 6. Source provenance contract

Structured-source provenance must be distinguishable from document provenance.

| Provenance item | Contract treatment |
|---|---|
| source system + organization scope + source candidate reference | Inherited envelope identity; required for attribution and tenant-safe lineage |
| source snapshot/event reference | Preserve when available; needed for reliable delivery-level replay identity; upstream support open |
| source version and source updated timestamp | Preserve as source assertions; do not assume monotonicity or use timestamp alone to reject older data |
| record reference | Preserve per record when upstream supplies a stable ID; do not invent a durable ID from array index |
| field path | Adapter should be able to point to the exact source field, e.g. `career_history[0].responsibilities`; array index is only stable within that snapshot |
| source value | Preserve the source value or a minimally normalized representation plus raw source value where later interpretation could change meaning |
| report/source URI | Preserve as a reference only when supplied and useful; do not fetch or embed report contents under this contract |

Current document provenance is `document_id + section + offsets + excerpt`; `SourceLocator` requires document and offsets ([SourceLocator](../../services/pai-backend/backend/app/extraction/locators.py#L4)). This contract does not reuse those fields to misrepresent ATS records. The future evidence-model design must support source-record/field references without requiring a CV document or document excerpt.

## 7. Career, education, credential, language, tool, and project semantics

- **Career:** preserve organization, title, dates/duration as supplied, responsibilities, explicitly captured technologies, and record/source timestamps. A responsibility narrative is source text, not a PAI behavior/capability conclusion.
- **Education:** preserve institution, degree, field, dates, and completion/status with source semantics. It may later support requirement-specific evidence; it is not a capability claim by itself.
- **Credentials:** preserve name, issuer, dates, expiry, reference, and any documented source verification assertion. Do not silently promote “source says verified” into PAI-verified capability.
- **Languages:** preserve independently even though current CandidateProfile has no dedicated language entity. Mapping to a future profile shape is deferred.
- **Tools/technologies:** preserve raw names (e.g. `PyTorch`). Do not assign canonical PAI capability IDs here.
- **Projects:** include only when available upstream. Preserve descriptions and explicitly captured technologies; semantic extraction, if later justified, is a separate Core-AI step.

For each category, source values remain source values. Deterministic normalization may later standardize formatting; semantic interpretation and evidence eligibility are outside this contract.

## 8. Interview contract

The contract supports a generic interview record with optional round, round title, interviewer reference, timestamp, recommendation, overall score and scale, comment, and report reference. Interviewer display name is not required; minimize personal data.

`criteria[]` is **CONDITIONAL**. If upstream has rubric results, preserve source criterion reference/name, score, scale bounds, comment, and source/evaluator references as supplied. Criterion labels do not become PAI capability IDs. A score, recommendation, or evaluator opinion does not automatically produce a verified capability.

**OPEN_CLARIFICATION:** determine whether ATS stores only overall feedback or structured rubric rows. Do not require fabricated criteria.

## 9. Assessment contract

An assessment record may preserve source reference, assessment type/name, overall result/score/scale, timestamp, and report reference. Overall-only results are valid.

`dimensions[]` is **CONDITIONAL**. When present upstream, retain source dimension reference/name, score, scale, and source context. Dimension scores do not become capability levels. Evidence eligibility, trust, and verification policy are future Core-AI decisions.

**OPEN_CLARIFICATION:** determine whether source assessments include detailed dimensions (e.g. Python/ML/Problem Solving) or only overall result/pass-fail/report.

## 10. ATS AI Scanning contract

`auxiliary_signals.ats_ai_scanning` is **AUXILIARY** and optional. Proposed source shape may retain `job_id`, `job_name`, `score`, `reason`, `keywords_found`, and `keywords_missing` without changing their source semantics.

- `score` = recruitment matching signal, not capability level or employee readiness.
- `keywords_found` = ATS AI matching signal, not supported/verified capability.
- `keywords_missing` = ATS AI did not match a term, not a confirmed capability gap.
- `reason` = AI-generated explanation, not ground truth.

Course Recommendation input preparation must work with this whole block absent. The block must not directly populate CandidateProfile claims, evidence statuses, current capability levels, gaps, or LearningNeeds.

## 11. Update and replay semantics

### Known requirements

- Core-AI needs a stable, organization-scoped source candidate identity before associating an envelope with its internal Candidate UUID.
- Provenance must distinguish candidate identity from delivery/snapshot identity.
- A replay must not silently create duplicate candidate identities or duplicate source records once an ingestion contract is implemented.
- Source timestamps are provenance, not an ordering rule unless ATS guarantees their semantics.

### Open upstream decisions

| Situation | Current contract position |
|---|---|
| Same payload replay | Deduplication behavior **OPEN**; source snapshot/event identifier availability and idempotency key contract need confirmation |
| Same candidate, newer snapshot | **OPEN** whether full snapshot, partial update, append, or replacement |
| Older/out-of-order snapshot | **OPEN**; no safe stale-write rule until a monotonic source version/order contract exists |
| Missing records in later payload | **OPEN** whether absence means deletion, unchanged, or not supplied |
| Stable record IDs | **OPEN** per record type; no durable array-index identity |
| `source_updated_at` only | Insufficient alone to establish exact replay or ordering semantics |

Do not implement upsert, replace, append, deletion, or stale-update behavior in 01B.

## 12. Data minimization

Do not forward bank/account data, salary/compensation, tax, insurance, national ID/passport, home address, vehicle data, or unrelated HR onboarding fields. Exclude job/designation/department/grade from this contract unless a separately approved, justified learning use is defined; in particular, no designation-to-Role mapping is implied. Prefer opaque references to names and do not include full report contents when a source reference is sufficient.

## 13. Mapping to future Core-AI ingestion

```text
CandidateSourceEnvelope
        ↓
CandidateSourceAdapter                    [future]
        ↓
source-grounded structured evidence       [future evidence-model support]
        ↓
semantic enrichment only when justified  [future thin ModelGateway adapter]
        ↓
existing CandidateProfile domain
        ↓
capability analysis                       [after CV coupling is addressed]
        ↓
Capability Gap → LearningNeed → Course Recommendation
```

No conversion to a fake CV/Document/ExtractionProfile occurs. CandidateProfile remains the reused profile domain. This contract does not claim the current capability-analysis entrypoint already accepts structured source evidence.

## 14. Open ATS/HRM clarifications

1. What immutable ATS candidate identifier exists, what is its uniqueness scope, and can HRM preserve/transmit it?
2. Are interview records generic feedback only, or are structured rubric/competency results available? What are their exact fields/scales/evaluator semantics?
3. Are technical/AI assessments overall-only, or are detailed dimensions available? What score/result scales and report references exist?
4. Which career, education, credential, interview, assessment, and project records have stable source IDs?
5. Is Payload v2 a full snapshot or partial update? What are version, replay, ordering, deletion, and duplicate semantics?
6. What exact Payload v2 field names/types and null/omission rules will upstream finalize?
7. What source organization reference is stable, and how is it mapped to the Core-AI organization scope?
8. Is `employee_ref` available only after hiring, and what is its namespace/stability?

Until clarified, do not represent these proposed field names as an observed ATS contract.

## 15. Core-AI follow-up decisions (defer to 01C)

- Persist external candidate identity without overloading Core-AI Candidate UUID.
- Add a structured source locator/provenance representation alongside document locators.
- Define a source-neutral current CandidateProfile/current-state reference.
- Define acceptance/review semantics for structured-source snapshots.
- Decouple capability-analysis input from accepted CV `ExtractionProfile` while preserving existing CV behavior and evidence policy.
- Decide how language and assessment records map into the existing CandidateProfile and evidence domains.

These are follow-up design areas, not implementation commitments made by this contract.

## 16. Contract readiness matrix

| Area | Status | Blocking 01C? | Owner / needed clarification |
|---|---|---:|---|
| Organization scope | Concept required; upstream ref unresolved | Yes for integration | ATS/HRM + Core-AI identity mapping |
| Candidate identity | Required stable-key concept; actual field unconfirmed | Yes | ATS confirms immutable unique ID and HRM propagation |
| Career | Optional structured records defined conceptually | No, subject to exact payload | ATS confirms fields/record IDs |
| Education | Optional structure defined | No | ATS confirms fields/status semantics |
| Credentials | Optional structure defined | No | ATS confirms IDs and verification-status meaning |
| Languages/tools | Preservable source groups; downstream mapping deferred | No | ATS confirms availability/field scales |
| Projects | Conditional | No | ATS confirms whether project records exist |
| Interview generic | Optional | No | ATS confirms available feedback fields |
| Interview rubric criteria | Conditional | No unless the product requires rubric evidence | ATS confirms structured rubric availability and scales |
| Assessment overall | Optional | No | ATS confirms result/scale/reference fields |
| Assessment dimensions | Conditional | No unless the product requires dimensions | ATS confirms availability and semantics |
| Record provenance | Minimum source/field lineage defined; stable IDs open | Partial | ATS confirms per-record IDs and timestamps |
| Snapshot/update | Requirements documented; behavior open | Yes for safe repeat updates | ATS/HRM specifies full/partial, ordering, replay, deletion |
| ATS AI scanning | Auxiliary and non-authoritative | No | ATS confirms optional shape; Core-AI excludes from capability truth |
| Role/JD | Explicitly excluded | No | Separate target-role contract owner |

## 17. Proposed next milestone

**PAI-CANDIDATE-INPUT-01C — Structured Evidence Model Extension & Candidate Source Ingestion Foundations**

Before implementation is finalized, resolve the identity and snapshot/update blockers with ATS/HRM. 01C can then define additive structured provenance, external identity linkage, a source adapter, and a source-neutral accepted current-state path. It must preserve the existing CV/JD document pipeline and must not introduce a second CandidateProfile domain.

## 18. Scenario validation

These are design-level checks against the proposed contract, not executed API/schema tests.

| Scenario | Result | Reason |
|---|---|---|
| A — minimal structured candidate; no interview/assessment/AI scan | PASS | Those groups are optional; stable source identity and organization scope remain required concepts |
| B — career, education, credentials, generic interview, overall assessment | PASS | Generic records do not require criteria or dimensions |
| C — structured interview criteria and assessment dimensions | PASS | Both arrays are conditional and retain source names/scales/provenance |
| D — AI scanning present | PASS | Stored only as auxiliary signal; forbidden from capability truth |
| E — AI scanning absent | PASS | No required dependency on that block |
| F — no raw CV/document/offsets/document excerpt | PASS | Contract has no document fields and explicitly permits structured-source lineage |
| G — incomplete upstream clarification | PASS WITH OPEN ITEMS | Contract stays conceptually valid; identity blocks safe production association, and update semantics block safe repeated snapshot handling |

## 19. Repository evidence and hygiene

**OBSERVED_FROM_REPOSITORY:** the current integration convention uses `IntegrationEnvelopeV1`; external learner identity uses opaque string references, while Candidate/organization IDs are internal UUIDs ([integration schema](../../services/pai-backend/backend/app/integration/schemas.py#L8), [identity bridge](../../services/pai-backend/backend/app/integration/identity_bridge.py#L33)). Existing CandidateProfile/evidence is document-oriented ([CandidateEvidence](../../services/pai-backend/backend/app/candidate/schemas.py#L96), [SourceLocator](../../services/pai-backend/backend/app/extraction/locators.py#L4)).

No dedicated JSON Schema/YAML contract-artifact convention was found in the repository file scan, so this deliverable uses an architecture/research document with a conceptual JSON example only. No production Pydantic schema is added. Runtime behavior is **NOT VERIFIED AT RUNTIME**.
