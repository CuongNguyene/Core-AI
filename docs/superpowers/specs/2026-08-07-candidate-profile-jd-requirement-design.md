# CandidateProfile Semantics and JD Requirement Compatibility Design

## Goal

Preserve accepted CV evidence semantics in `CandidateProfile` and introduce a
versioned JD requirement contract that feeds reviewer-controlled role-profile
authoring without changing extraction orchestration or approval lifecycle.

## Decisions

- CV legacy extraction remains readable. A deterministic profile builder maps
  evidence type to context and routes claims by evidence semantics, not legacy
  bucket name.
- `JDRequirementExtractionOutputV2` is the new JD contract. Requirements are
  atomic and carry modality, logical grouping, constraints, source provenance,
  and authoring findings without inventing absent semantics.
- Accepted legacy JD profiles remain eligible through a versioned compatibility
  adapter. Their drafts record `source_schema=legacy` and the source version.
- Legacy adaptation never infers modality, target level, observable behavior,
  evidence constraints, priority, or AND/OR semantics. Missing recoverable
  structure becomes an authoring finding; missing locator/provenance or unsafe
  atomization is `BLOCKING` and requires re-extraction or reviewer replacement.
- Every adapted draft starts `DRAFT`; only existing reviewer enrichment and
  quality gates can produce `PROVISIONAL` or `ACTIVE`.

## Boundaries

No parser, storage, job orchestration, locator, review workflow, Evidence Graph
persistence contract, capability-analysis decision semantics, or role approval
lifecycle is changed. Historical extraction payloads remain immutable and
readable.

## Test strategy

Use TDD. First add failing unit tests for context mapping, semantic routing,
multi-context deduplication, unknown placeholders, v2 schema/prompt, legacy
happy-path adaptation, lossy findings, and blocked approval. Then implement the
smallest deterministic mapper and adapter, followed by contract registration
and authoring integration. Run focused tests after each red-green cycle and the
full backend suite before completion.
