# Backend module document

`backend/` owns the FastAPI modular monolith, SQLAlchemy models/repositories,
Alembic migrations, worker implementation, API schemas and backend tests.

- Run `uv`, Alembic, Ruff, mypy and pytest from this directory.
- Domain modules do not call model-provider HTTP directly; use ModelGateway then
  PrivacyGateway.
- CV/JD/raw documents remain untrusted and must not appear in logs, audit or
  cache values.
- Extraction worker logic chunks long CV/JD text deterministically, sends each
  chunk through the chunk-specific prompt/schema contract and merges only
  source-backed results into the final reviewable profile.
- Extraction mode selection is pure and length-based: documents up to 12,000
  characters use full-document mode; larger documents use section-based mode.
- Section-aware chunking keeps each `ExtractionChunk` inside one detected
  document section while preserving absolute offsets and overlap semantics.
- Full-document CV/JD contracts use dedicated versioned schemas with explicit
  evidence type and source excerpt requirements.
- Section contracts receive only `section_type` and `section_text`; section
  prompts forbid cross-section inference and distinguish technology mentions
  from experience claims.
- Merge groups normalized claims while retaining distinct evidence types and
  replacing duplicate evidence with the stronger confidence record.
- Evidence Graph extraction keeps full-document relation context separate from
  section-grounded evidence. Candidate profiles model employment, projects,
  research, education, publications and skills as distinct entity collections;
  the same technology may therefore retain multiple usage contexts instead of
  being flattened into a keyword.
- Evidence Graph entities use stable normalized identifiers and retain every
  source excerpt, confidence, usage and source type. They are descriptive
  extraction output only and never imply verified competency or a hiring
  decision.
- Full-document relation contracts use `EntityRelation` with an allowlisted
  relation vocabulary (`used_in`, `worked_on`, `published`, `studied`,
  `deployed`, `led`). Section evidence contracts are bounded to the supplied
  section and explicitly distinguish mentions, project implementation and
  employment deployment; they must not infer production use, ownership,
  seniority or leadership.
- `merge_relation_evidence` is the deterministic boundary for combining full
  and section relation claims. Duplicate evidence is collapsed only when its
  context and exact excerpt match; the higher-confidence claim wins.
- `EvidenceExtractionOutput` groups canonical entities with all source-backed
  evidence. `merge_evidence_outputs` preserves original and canonical values,
  retains distinct contexts and orders evidence by context strength.
- CV relation, CV evidence and JD requirement prompts are versioned separately;
  they return JSON-only, source-backed output and explicitly prohibit document
  instructions from changing extraction behavior.
- Set `EVIDENCE_GRAPH_RUNTIME_ENABLED=true` to run the worker's full-document
  relation extraction plus section evidence extraction path. The default is
  false during migration; when enabled, source excerpts are located exactly,
  mapped through `map_relation_to_evidence_context`, merged and persisted as a
  CandidateProfile. The legacy chunk adapter remains the explicit fallback.
- Entity normalization is isolated to comparison keys; original claim text,
  excerpts, source locators and audit metadata are preserved verbatim.
- Exact source-excerpt lookup and fail-closed locator validation remain
  mandatory after normalization.
- Hybrid acceptance tests cover small/full routing, large/section routing,
  section ownership, unsupported claims and audit redaction.
- New endpoints require Pydantic request/response schemas, application-layer
  authorization, safe error contract and tests.
- Update this document when backend module ownership, runtime dependencies,
  migration procedure or service boundary changes.
