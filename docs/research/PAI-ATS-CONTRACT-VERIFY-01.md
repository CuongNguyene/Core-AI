# PAI-ATS-CONTRACT-VERIFY-01 — CANDIDATE + ROLE CONTRACT

## Status

COMPLETE. This is a read-only contract discovery/freeze. No production code, LMS code, commit or push was performed.

## 1. Repository

Canonical repo: `/Users/mac/Developers/work/LMS/Core-AI`, confirmed by current Compose/runtime source, local environment and source layout. Branch: unavailable. HEAD: unavailable. The canonical directory has no `.git` metadata; the recovery clone is not treated as canonical. Pre-existing changes: no Git status can be read from canonical; the recovery clone retains prior HARDEN-01 changes and was not modified by this task.

## 2. Candidate Canonical Object

Object: `app.extraction.profile.CandidateProfile`, embedded in an accepted `ExtractionProfile`, plus `app.candidate.schemas.Candidate` and `CandidateProfileLink` for aggregate identity/governance. Persistence: `candidates`, `candidate_profiles`, `extraction_profiles.normalized_output`, `candidate_claims`, `candidate_evidence`. API schema: `Candidate`, `CandidateProfileHistoryEntry`, `ExtractionProfile`. Versioning: extraction/profile version plus candidate current profile pointer and governance version. Identity: internal `candidate_id: UUID`; display `candidate_code`; no current external ATS ID field.

## 3. Candidate Field Inventory

| Field | Type | Required | Nullable | Source/Derived | Canonical/Legacy | Notes |
|---|---|---:|---:|---|---|---|
| `candidate_id` | UUID | yes | no | Core internal | canonical | Stable internal candidate identity |
| `candidate_code` | string max 32 | model yes; create generated | no | Core generated | canonical | Display/reference code; current service generates `CAN-...` |
| `display_name` | string | no | yes | source | canonical | Candidate create API optional |
| `primary_email` | string | no | yes | source | canonical | PII; only send if integration policy allows |
| `primary_phone` | string | no | yes | source | canonical | PII; only send if integration policy allows |
| `organization_id` | UUID | yes | no | auth/tenant | canonical | Core ownership boundary, not free ATS input |
| `status` | active/archived | yes | no | Core governance | canonical | ATS should not own lifecycle |
| `review_state` | draft/extraction_pending/pending_review/accepted/needs_revision/rejected | yes | no | Core governance | canonical | Accepted profile required for analysis |
| `current_profile_id` | string | no | yes | Core pointer | canonical | Points to accepted/current profile |
| `current_profile_version` | int >=1 | no | yes | Core pointer | canonical | Pinned with profile ID |
| `CandidateProfile.skills` | list `SkillEntity` | no at schema | empty allowed | source/normalized | canonical | `entity` required; evidence needed for source-backed analysis |
| `employment_history` | list `ExperienceEntity` | no | empty allowed | source/normalized | canonical | name required; role/organization optional |
| `projects` | list `ProjectEntity` | no | empty allowed | source/normalized | canonical | name required |
| `research_work` | list `ResearchEntity` | no | empty allowed | source/normalized | canonical | name required |
| `education` | list `EducationEntity` | no | empty allowed | source/normalized | canonical | institution required; degree/field optional |
| `publications` | list `PublicationEntity` | no | empty allowed | source/normalized | canonical | title required; venue optional |
| `credentials` | list `CredentialEntity` | no | empty allowed | source/normalized | canonical | name required |
| `activities` | list `CapabilityActivity` | no | empty allowed | source/normalized | canonical | statement required |
| `findings` | list `ProfileFinding` | no | empty allowed | Core derived | canonical | code/severity/source claim ref |
| `EvidenceItem` | context, usage, excerpt, confidence, locator | no per entity | yes | source evidence | canonical | Supported capability requires locator |
| proficiency/current level | not present | — | — | — | LEGACY_DO_NOT_USE | Core explicitly avoids inferring proficiency |
| languages/years/last used | not present | — | — | — | LEGACY_DO_NOT_USE | No current canonical field |

## 4. CV Extraction → Candidate Mapping

Extraction objects: `CVFullExtractionOutputV2` and legacy `CVExtractionOutput`. Mapping service: `project_v2_to_candidate_profile()` → `build_candidate_profile_from_output()`. Accepted profile: `ExtractionProfile(review_state=accepted, accepted_by, accepted_at)`. Fields preserved: supported values, evidence excerpts, locators, confidence, evidence type/context. Fields transformed: capabilities/tools/experience/education into canonical profile entities; names are normalized; entity IDs are derived. Fields not represented in `CandidateProfile`: CV summary, dates, company/location/year metadata, raw category/mapping status. Provenance remains in `EvidenceItem.source_excerpt/source_locator` and materialized `CandidateEvidence`.

ATS can bypass extraction only through a future adapter that produces an accepted canonical profile/source artifact. The current public flow does not expose direct CandidateProfile ingest.

## 5. Candidate Identity

ATS source ID: proposed `source_system + external_candidate_id`; no current PAI field. Core-AI internal ID: `Candidate.candidate_id` UUID. LMS learner ref: not a Candidate field and must remain a separate bridge identity if used. Display identity: `candidate_code` and `display_name`.

Recommended ATS identity contract: ATS owns an immutable external ID; the future adapter stores/maps it to the Core candidate UUID and organization. Do not use `candidate_code` as the ATS source key.

## 6. Candidate ATS Mapping

The complete mapping is in [candidate-ats-mapping.json](../../test/results/pai-ats-contract-verify-01/candidate-ats-mapping.json) and [candidate-ats-mapping.csv](../../test/results/pai-ats-contract-verify-01/candidate-ats-mapping.csv). P0 distinguishes API/domain requirements from quality-enhancing P1/P2 fields. `external_candidate_id`, `source_system` and `source_updated_at` are explicitly proposed integration metadata, not existing PAI fields.

## 7. Candidate Minimum P0 Payload

See [candidate-payload.example.json](../../test/results/pai-ats-contract-verify-01/candidate-payload.example.json). Proven P0 data is tenant context, candidate display/contact data where available, and an analyzable profile capability with source-backed evidence. The payload is marked PROPOSED because no current direct ATS endpoint accepts it.

## 8. Candidate P1/P2 Fields

| Priority | Field | Canonical support | Notes |
|---|---|---|---|
| P1 | employment history | `ExperienceEntity` | Current object lacks dates/tenure |
| P1 | projects | `ProjectEntity` | Name/evidence only |
| P1 | education | `EducationEntity` | Institution/degree/field only |
| P2 | credentials | `CredentialEntity` | Name/evidence only |
| P2 | activities | `CapabilityActivity` | Source-grounded statements |
| P2 | richer evidence | `EvidenceItem` | Improves analysis quality; not separate ATS scoring |
| P2 | source updated timestamp | proposed metadata | Needed for future sync, not current profile |

## 9. Role Canonical Objects

JD extraction object: `JDRequirementExtractionOutputV2` / accepted `ExtractionProfile`. RoleProfileDraft: reviewer-editable normalized requirements plus source lineage, quality gate and approval eligibility. RoleCompetencyProfile: versioned governed requirement profile with `RoleRequirement[]`, policy/rule versions and optional semantic policy. Role identity: `Role.id` UUID, organization-scoped `role_code`, `RoleJDVersion`, and profile `id@version`. Versioning: immutable JD versions and versioned competency profiles; Capability Analysis pins exact profile references.

## 10. JD → Role Mapping

Source → accepted JD extraction → `adapt_jd_profile()` → `RoleProfileDraft` → `evaluate_role_profile_draft()` → approval → `RoleCompetencyProfile`. Source facts include statements, evidence terms, source requirement refs, excerpts and locators. Normalization maps modality to classification, assigns IDs/policies/thresholds and preserves provenance. Quality gate checks source chain, IDs, evidence terms, dimensions and legacy uncertainty. Approved profile is the Core-owned output; ATS must not calculate it.

## 11. Role Field Inventory

| Field | Object | Type | Required | Source/Derived | Lifecycle | Notes |
|---|---|---|---:|---|---|---|
| `id` | Role | UUID | yes | Core | all | Internal stable role ID |
| `role_code` | Role | string | yes | Core/source | all | Unique per organization; current create service generates it |
| `title` | Role | string | yes | source | all | Current CreateRoleRequest required |
| `description` | Role | string | no | source | all | Nullable, max 2000 in registry API |
| `status` | Role | active/inactive/archived | yes | Core governance | role | Not equivalent to competency profile status |
| `role_jd_version_id` | RoleJDVersion | UUID | yes for lineage | Core | JD version | Immutable document-linked source version |
| `requirements` | RoleCompetencyProfile | list RoleRequirement | yes, min 1 | normalized/derived | provisional/active | Candidate-analysis input |
| `criterion_dimension` | RoleRequirement | enum or null | conditional | normalized | draft/profile | skill/experience/education/credential/qualification |
| `classification` | RoleRequirement | enum | yes | normalized | draft/profile | legal_mandatory/role_critical/trainable_mandatory/preferred/optional/unclassified |
| `evidence_terms` | RoleRequirement | string[] min 1 | yes | source/normalized | draft/profile | Candidate matching terms |
| `priority` | RoleRequirement | string or null | no | source/reviewer | draft/profile | Not a closed enum currently |
| `target_level` | RoleRequirement | string or null | no | explicit source/reviewer | draft/profile | No controlled enum; do not infer |
| `observable_behaviors` | RoleRequirement | string[] | no | source/reviewer | draft/profile | Quality/analysis aid |
| `evidence_constraints` | RoleRequirement | string[] | no | source/reviewer | draft/profile | Quality/analysis aid |
| `source_locator` | RoleRequirement | SourceLocator/NativePdfLocator/null | no at schema, required for approval chain | source | draft/profile | Provenance anchor |
| `source_requirement_ref` | RoleRequirement | string/null | no at schema, required for approval chain | source | draft/profile | Original requirement identity |
| `semantic_policy_ref` | RoleCompetencyProfile | policy ref/null | no schema, required for fresh analysis in current runtime | Core governance | approved/profile | Selects semantic policy/packs |

## 12. Required / Preferred / Priority Semantics

Required/must maps to `JDRequirementModality.MUST` and normally `RequirementClassification.ROLE_CRITICAL`. Preferred maps to `PREFERRED`. Responsibilities map to `RESPONSIBILITY` and must not have a candidate criterion dimension. Unspecified maps to `UNSPECIFIED` and then `UNCLASSIFIED`. Legacy extraction uses deterministic phrase heuristics; ambiguity remains reviewer-visible. `priority` is a nullable string and should be preserved only when explicit; ATS must not fabricate it.

## 13. Target Level Semantics

Canonical representation: nullable free-text `RoleRequirement.target_level`. Candidate `CandidateProfile` has no canonical proficiency/current-level field. Capability snapshots use provisional evidence/status/verification, not a proficiency scale. Source-provided levels may be preserved when explicit; Core/reviewer must derive or complete governed target semantics. ATS may omit levels and must never invent beginner/intermediate/advanced/expert values.

## 14. Role Identity / Registry Readiness

Stable role identity exists: YES. `role_code`: organization-scoped unique code, but current create API generates it. Profile version: `RoleCompetencyProfile.version` string. Pinned downstream: YES, exact `profile_id@version` is used by Capability Analysis. “Latest” is not the analysis authority. Role Registry exists: YES (`Role`, `RoleJD`, `RoleJDVersion`). Gap: no external ATS role ID/source-system fields and no direct structured ATS ingest endpoint.

## 15. Role Lifecycle

| State | Meaning | Created By | Allowed Downstream Use |
|---|---|---|---|
| `draft` | editable source/draft | Core authoring | not final capability authority |
| `in_review` | review in progress | Core workflow | governed review only |
| `needs_revision` | quality/reviewer revision required | Core workflow | no approval |
| `provisional` | preview-governed profile | approval workflow | Capability Analysis preview semantics |
| `active` | approved active competency profile | approval workflow | eligible official target when policy is configured |
| `validated` / `approved` | draft workflow/status values | Core authoring | transition semantics owned by Core |
| `retired` | RoleCompetencyProfile status | Core governance | not new analysis target |

Versioned profiles and JD versions are not mutated in place as the source of historical analyses. ATS should provide source data, not governance state.

## 16. Role ATS Mapping

The complete mapping is in [role-ats-mapping.json](../../test/results/pai-ats-contract-verify-01/role-ats-mapping.json) and [role-ats-mapping.csv](../../test/results/pai-ats-contract-verify-01/role-ats-mapping.csv). P0 source fields terminate at a future adapter/source representation; RoleProfileDraft and RoleCompetencyProfile fields are Core-owned outputs.

## 17. Role Minimum P0 Payload

See [role-payload.example.json](../../test/results/pai-ats-contract-verify-01/role-payload.example.json). P0 is external role identity, tenant context, title, optional description and source-grounded requirements. This is a PROPOSED adapter payload, not a current public API payload.

## 18. Role P1/P2 Fields

| Priority | Field | Canonical support | Notes |
|---|---|---|---|
| P1 | explicit modality | `RoleRequirement.modality/classification` | Avoids ambiguous required/preferred mapping |
| P1 | evidence terms | `RoleRequirement.evidence_terms` | Candidate matching input |
| P1 | target level | nullable `target_level` | Only if explicit |
| P1 | observable behaviors | `observable_behaviors` | Better analysis quality |
| P1 | evidence constraints | `evidence_constraints` | Better evidence governance |
| P2 | job family/job level | no current canonical field | Proposed source metadata only |
| P2 | education/experience/language requirements | dimensions/terms only | No dedicated Role fields currently |
| P2 | source_updated_at | proposed sync metadata | Future upsert contract |

## 19. Provenance Contract

Candidate provenance: `EvidenceItem.source_excerpt`, `EvidenceItem.source_locator`, confidence/context/source_type, then `CandidateEvidence.provenance`. Role provenance: `source_requirement_ref`, `source_locator`, `source_excerpt`, `RoleRequirement.provenance`, source JD profile ID/version and source schema/version. ATS equivalent: `source_system`, external record ID, source field and source update time are proposed adapter metadata. Current gaps: structured ATS records do not naturally provide `SourceLocator`; a future adapter must map source fields to a Core-owned source artifact or extend the boundary. No production field was added here.

## 20. Capability Analysis Prerequisites

Candidate requirements: candidate exists in the actor organization, has a current profile ID/version, profile is accepted and not stale, and the profile contains analyzable source-backed capabilities. Role requirements: role exists in the organization, role/profile linkage resolves, target profile is version-pinned, requirements are non-empty, and semantic policy/packs are configured for fresh analysis. Version requirements: candidate profile version and exact role profile `id@version`. Lifecycle requirements: official active target uses official semantics; provisional target is preview-only. Minimum ATS source: stable external candidate/role IDs for adapter mapping, tenant context, candidate source evidence/capabilities, role title and source-grounded requirements.

## 21. Fields ATS Must NOT Produce

Candidate derived fields: candidate code, capability status, verification status, confidence, canonical capability IDs, evidence strength and Core review state. Role derived fields: RoleCompetencyProfile, policy/rule versions, quality findings, approval eligibility and active/provisional governance. ATS must not calculate Capability Analysis, gaps, Learning Needs, Learning Paths, recommendations, AI rationale or final proficiency claims.

## 22. Legacy / Deprecated Fields

| Field/Object | Status | Replacement | Reason |
|---|---|---|---|
| `CVExtractionOutput` legacy buckets | LEGACY compatibility | `CVFullExtractionOutputV2` → `CandidateProfile` | Kept for compatibility; less rich provenance |
| `source_schema=legacy_v1` | LEGACY | V2 JD requirement source | Quality gate emits uncertainty findings |
| legacy inferred classification | LEGACY/uncertain | explicit modality + reviewer/Core normalization | Must not be presented as ATS canonical truth |
| `X-PAI-Actor-ID` for integration | LEGACY | signed actor context | Not an ATS data field and not production integration auth |
| `CandidateCapabilityProfile` | NOT_CURRENT_OBJECT | `CandidateProfile` + provisional capability snapshot | No current separate class |
| free-text proficiency invented by ATS | LEGACY_DO_NOT_USE | nullable target_level + Core evidence semantics | Core prompts explicitly prohibit inferred proficiency |

## 23. Sync / Upsert Semantics

Current behavior: Candidate/Role APIs use Core-generated UUIDs and current profile pointers; extraction/profile versions and role JD/profile versions are persisted; no external source ID, source timestamp or stale-event contract exists. Proposed ATS behavior: idempotent upsert by `(source_system, external_id, organization)`; resend of same source version is a no-op; older `source_updated_at` is rejected/ignored; newer source data creates a new Core source/profile version and never mutates an accepted historical artifact. Idempotency keys should be required on future write APIs. These are PROPOSED recommendations, not current behavior.

## 24. Contract Gaps

| Gap | Classification | Impact | Needed Later? |
|---|---|---|---:|
| External candidate identity | IDENTITY_GAP | adapter cannot persist source key in current Candidate | yes |
| External role identity | IDENTITY_GAP | adapter cannot persist source role key in current Role | yes |
| Structured candidate ingest | NEW_API_REQUIRED | current path assumes document/extraction/profile link | yes |
| Structured role ingest | ADAPTER_REQUIRED | current draft creation requires accepted JD ExtractionProfile | yes |
| ATS evidence locator mapping | PROVENANCE_GAP | source-backed capability requires locator | yes |
| Target level enum | SCHEMA_GAP | current value is nullable free text | optional |
| Sync/version timestamps | VERSIONING_GAP | stale events/upserts unspecified | yes |
| Role Registry | NO_GAP | current Role/RoleJDVersion exists | no |

## 25. Recommended Integration Boundary

Candidate: `ATS Candidate + source evidence → ATS/Core-AI source adapter → Candidate aggregate + accepted CandidateProfile → Core capability analysis`. Role: `ATS Job/JD + requirements → source adapter/source artifact → accepted JD/profile or RoleProfileDraft → Core quality gate/approval → RoleCompetencyProfile`. ATS should stop before Core normalization, governance and derived learning outputs.

## 26. ATS Team Handoff

### Candidate P0

`external_candidate_id`, `source_system`, `organization_ref`, optional `display_name/email/phone`, and at least one source-grounded capability/profile item with evidence. The external ID/source metadata are PROPOSED because current Core-AI has no direct field/API for them.

### Role P0

`external_role_id`, `source_system`, `organization_ref`, `role_title`, optional `job_description`, and source-grounded requirements with `source_requirement_ref`, statement/evidence terms and explicit modality when available. Do not send RoleCompetencyProfile or governance decisions.

## 27. Evidence Files

Created under `test/results/pai-ats-contract-verify-01/`: candidate-model-inventory.json, candidate-source-to-profile-trace.json, role-model-inventory.json, jd-to-role-trace.json, candidate-ats-mapping.json, role-ats-mapping.json, candidate-payload.example.json, role-payload.example.json, contract-gaps.json, summary.json, candidate-ats-mapping.csv and role-ats-mapping.csv. Graphify code graph was generated at `graphify-out/graph.json` as analysis evidence.

## 28. Change Classification

DOC: `docs/research/PAI-ATS-CONTRACT-VERIFY-01.md`. EVIDENCE: `test/results/pai-ats-contract-verify-01/*`. PRODUCT_CODE: NONE. MIGRATION: NONE. LMS: NONE.

## 29. Final Decision

Is Candidate ATS mapping ready to hand off? YES, with explicit adapter/API gaps.

Is Role ATS mapping ready to hand off? YES, with explicit source-adapter/API gaps.

Does ATS need to calculate capability levels? NO; ONLY_IF_SOURCE_HAS_EXPLICIT_LEVEL, and even then ATS must not invent levels.

Does ATS need to calculate RoleCompetencyProfile? NO.

Does ATS need to calculate gaps/learning needs? NO.

Is a new adapter/API needed? YES for direct structured candidate/role source ingestion and external identity persistence.

Is Role Registry work needed? NO for the current registry; adapter integration work is needed later.

## 30. Git Status

Core-AI: canonical source has no `.git` metadata, so branch/HEAD/status/diff cannot be truthfully reported there. Recovery clone was not modified. LMS: UNCHANGED.

STOP. No ATS integration, Role Registry, Learning Path, Recommendation, Curriculum, commit or push was performed.
