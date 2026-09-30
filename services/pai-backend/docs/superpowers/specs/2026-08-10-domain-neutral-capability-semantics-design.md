# Domain-neutral Capability Semantics Design

## Goal

Refactor PREVIEW capability matching into a domain-neutral deterministic core
with pluggable, versioned domain knowledge packs. Prove the boundary with small
labelled fixtures for AI Engineer, Sales Executive, Accountant, and HR
Recruiter. This milestone is architecture validation, not a broad recall push.

## Preserved pipeline and boundaries

```text
accepted CV extraction claims / graph evidence
-> EvidenceIndex
-> semantic-preserving CandidateProfile
-> EvidenceSemantics
-> domain-pack normalization and hints
-> retrieval candidates
-> generic compatibility / eligibility / coverage
-> provisional assessment and verification queue
-> immutable PREVIEW portfolio
```

`EvidenceIndex` remains in-memory. Accepted extraction profiles and historical
portfolios are immutable. A missing match is `not_found_in_evidence` or
`insufficient`; it is never a confirmed employee deficiency. `PREVIEW` remains
the only analysis mode in scope: no VERIFIED, OFFICIAL, final decision, score,
learning objective, or learning path.

## Semantic contracts

| Contract | Required contents | Rule |
| --- | --- | --- |
| `RequirementSemantics` | requirement ID, concepts, behaviors, objects, constraints, evidence expectation, source refs, unresolved semantics | Derived only from approved requirement fields and pack hints. |
| `EvidenceSemantics` | evidence ref, concepts, behaviors, objects, context, participation, source kind, confidence, original evidence type, locator, provenance | Derived only from source-backed CandidateProfile/EvidenceIndex data and pack hints. |
| `SemanticConstraint` | generic dimension, operator, allowed values, source field/reference | Dimensions are context, participation, source kind, minimum strength, education, credential, and duration. |
| `RetrievalCandidate` | evidence semantics, matched semantic dimensions, relevance rationale, pack refs | Retrieval establishes relevance only. |
| `EvidenceCompatibility` | candidate ID, eligible flag, directness, ranking key, mismatch codes | Eligibility is decided only by the core. |

Unknown fields remain unknown. For example, “deployed dashboard” may map to
`behavior=deploy`, but cannot create `context=production`; “participated in
recruitment” cannot create `participation=own`.

## Generic compatibility

The core uses requirement-aware evidence expectation instead of a universal
source ordering.

| Requirement expectation | Direct evidence | Ineligible/weak examples |
| --- | --- | --- |
| demonstrated usage | work or project use, subject to constraints | mention only requires verification |
| education | study/degree evidence | work alone is not a degree |
| credential | credential evidence | practice alone is not a credential |
| owned outcome | source-backed ownership-compatible participation | participated/assisted evidence |
| explicit context | evidence with that same source-backed context | adjacent context, retained as mismatch |

`retrieved_candidate_count` and `eligible_candidate_count` are independent.
For an explicit production deployment requirement, project deployment evidence
may yield `retrieved=2`, `eligible=0`, and `context_mismatch`.

## Domain pack interface and selection

`DomainKnowledgePack` has immutable `pack_id`, `version`, and
`supported_domain`, plus `normalize_term`, `expand_aliases`,
`map_requirement_phrase`, and `map_evidence_phrase`. Its result is a
source-grounded `DomainSemanticHints` value; it does not assign a final status.

New role profile semantic-policy metadata selects an ordered set of pack
references and a semantic-core policy version. The selected reference is
immutable for an approved profile and copied into every new portfolio snapshot.
The registry must resolve every requested reference exactly.

Current `RoleCompetencyProfile` rows do not contain this metadata. Their only
compatibility path is an immutable `role_profile_semantic_policy_mappings`
record keyed by exact `role_profile_id` and `role_profile_version`. The mapping
contains ordered pack refs, core version, and
`selection_source=legacy_profile_version_mapping`. It must be created explicitly
by a migration/seed or approved admin workflow. If neither profile metadata nor
an exact mapping exists, analysis fails closed as `semantic_policy_not_configured`.
The service never infers a domain from JD/CV words, and it never rewrites a
historical role-profile row. New profile metadata produces
`selection_source=profile_metadata`; both sources are copied into portfolio
provenance.

The first pack is `it_ai@1`, containing only existing aliases/morphology:
Python/PyTorch/TensorFlow, NLP, Kafka/Spark, ML/DL, Computer/Data Science,
Docker/Kubernetes, MLOps/CI-CD, model design/training/evaluation, and deployment
terms. No ontology expansion is part of this work.

## API, persistence, and state machine

No capability-analysis request endpoint changes. Existing response fields stay
compatible, including `production_required`, `evidence_strength`,
`retrieved_candidate_count`, `eligible_candidate_count`, PREVIEW readiness and
verification queue. New optional response/snapshot metadata may expose:

```json
{
  "semantic_policy": {
    "core_version": "semantic-core-v1",
    "pack_refs": [{"pack_id": "it_ai", "version": "1"}],
    "selection_source": "role_profile_policy"
  }
}
```

This is additive and defaults to `null` for historical portfolios. Assessment
and gap payload JSON accepts additive fields; add a database migration only if
the metadata is indexed/queryable outside existing JSON payload/snapshot
storage. No historical row is rewritten.

Role profile and review lifecycle are unchanged:

```text
DRAFT -> IN_REVIEW -> NEEDS_REVISION | PROVISIONAL | ACTIVE
```

`PROVISIONAL` continues to create PREVIEW analysis only. This milestone neither
authorizes nor implements an ACTIVE/OFFICIAL path.

## Required regression fixtures

| Domain | Required invariant |
| --- | --- |
| AI Engineer | Python work ranks above mention; Kafka project use is distinct from mention; Docker mention remains weak; project deployment is retrieved but context-ineligible; MLOps remains a negative control. |
| Sales Executive | supported/assisted enterprise pitches are relevant but not ownership evidence; owned full sales cycle is ownership-compatible. |
| Accountant | Bachelor of Accounting is direct education evidence; studied IFRS does not become work financial-reporting practice. |
| HR Recruiter | screening participation is not ownership of recruitment; managed sourcing-to-offer is stronger; coursework is not work interview experience. |

Each fixture supplies a narrow, test-only pack or a test-only semantic-hint
adapter: it maps only that fixture's labelled phrases to typed concepts,
behaviors, contexts, or participation. These packs live under test fixtures,
are injected through the same pack protocol, and are never imported by the
core. They prove that the core has no knowledge of Sales, IFRS, or Recruitment;
only the fixture pack/manifest contains those labels.

Fixture manifests are engineering assertions only. They may calculate expected
positive retrieval, expected-negative precision, context preservation,
eligibility-boundary, and participation-boundary accuracy; none are persisted
as employee readiness or business scores.

## Non-goals

- Complete enterprise ontology, automatic ontology generation, vector database,
  LLM-based capability decisions, or model re-extraction.
- Mutation of accepted extraction profiles or historical portfolios.
- Raw 45-requirement recall optimization.
- Role-profile authoring/lifecycle changes, automatic enrichment, learning
  paths, OFFICIAL analysis, VERIFIED capability, or final decisions.
