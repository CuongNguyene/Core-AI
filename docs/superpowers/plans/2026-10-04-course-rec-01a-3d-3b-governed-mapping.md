# COURSE-REC-01A.3D-3B Governed Mapping Resolution & Activation — Implementation Plan

> **For agentic workers:** Use the inline `superpowers:executing-plans` workflow task-by-task. No commits are permitted by the supplied task.

**Goal:** Integrate 3D-3A source mapping proposals/reviews with exact 3D-2 capability authority to activate immutable, source-fresh governed mappings and resolve them separately for current or historical use.

**Architecture:** Add source/evidence pins and explicit activation approval as 3D-3B-owned contracts. A pure activation function reuses 3D-3A proposal/review validation and 3D-2 exact authority resolution; separate pure resolvers enforce current-use versus historical semantics. No persistence, API, model call, or upstream changes.

**Tech Stack:** Python 3.13+, Pydantic v2, SHA-256 canonical JSON, pytest, Ruff, mypy.

**Spec:** `/Users/mac/.codex/attachments/54383d20-56dd-47e3-b6f4-a4aa9ccc77f6/Pasted text.txt`

## Global Constraints

- Reuse `CanonicalCapabilityRef`, `SourceSemanticRef`, `CapabilityDefinitionPin`, `resolve_for_new_binding`, `resolve_historical`, `CapabilityMappingProposal`, `CapabilityMappingReview`, `SemanticEvidence`, `MappingScope`, `MappingType`, `ProposalMethod`, `UnmappedSemantic`, and `validate_mapping_review_for_proposal`.
- No edits to 3D-1, 3D-2, 3D-3A, 01B, LMS, schemas/adapters, package initializer, persistence, API, migrations, network, or model calls.
- Only `EXACT` proposals can activate. `APPROVE` is necessary but not sufficient; activation approval and exact active target authority are also required.
- Pin source identity/version plus canonical evidence; pin exact target pack/version/checksum. Never follow replacement refs or auto-repin to a newer release.
- Mapping lifecycle is `ACTIVE → DEPRECATED`; no in-place mutation and no reactivation.
- No commit or push.

## Review Focus

- A caller supplies a different source version or evidence with the same source ID; current use must reject the stale pin.
- A target's canonical ref remains the same while its active pack release changes; current use must not silently accept the newer definition pin.
- Same source semantic identity/scope/source pin maps to different targets; activation must reject the conflict, while distinct facet identities within one aggregate remain representable.
- Mapping payload/fingerprint or approval pin is inconsistent; resolution/activation must fail closed without relying on object identity.
- A deprecated mapping/target is requested for new use; current resolution must reject it while exact historical resolution remains possible for non-draft authority.

---

## Planned Files

- Create `services/pai-backend/backend/app/capability_governance/mapping_errors.py` — stable 3D-3B-only mapping contract failures; do not edit 3D-2 `errors.py`.
- Create `.../mapping_activation.py` — `SourceSemanticPin`, its deterministic builder, review fingerprint, and `MappingActivationApproval`.
- Create `.../governed_mapping.py` — immutable governed mapping, fingerprint, activation gate, and deprecation transition.
- Create `.../mapping_resolution.py` — current-use and historical resolvers plus a domain-neutral resolved-binding value.
- Create `services/pai-backend/backend/tests/test_governed_mapping.py` — synthetic pack/proposal helpers and focused contract/integration tests.
- Create `docs/research/COURSE-REC-01A-3D-3B-GOVERNED-MAPPING-RESOLUTION-ACTIVATION.md` and `test/results/course-rec-01a-3d-3b/*.json` as listed in the task.
- Do not edit `app/capability_governance/__init__.py`; consumers import the focused submodules directly.

## Interfaces

- `SourceSemanticPin(source_ref: SourceSemanticRef, evidence_fingerprint: str)` and `build_source_semantic_pin(source_ref: SourceSemanticRef, evidence: tuple[SemanticEvidence, ...]) -> SourceSemanticPin`; reject empty evidence or evidence whose `source_ref` differs from the supplied source identity. The digest covers canonical source-ref JSON and canonical full evidence values.
- `fingerprint_mapping_review(review: CapabilityMappingReview) -> str`; canonical SHA-256 includes proposal ID/fingerprint, reviewer, decision, and rationale.
- `MappingActivationApproval(approval_ref, proposal_id, proposal_fingerprint, review_fingerprint, source_pin, target_definition_pin, approver_ref)`; reference/actor fields are nonblank and bounded to 256 chars, rationale is already bounded by 3D-3A. It is domain evidence of explicit approval, not authentication.
- `MappingGovernanceError(ValueError)` uses stable `code` values: `proposal_review_mismatch`, `mapping_review_rejected`, `mapping_review_uncertain`, `stale_source`, `activation_approval_required`, `activation_approval_mismatch`, `target_pin_mismatch`, `mapping_conflict`, `mapping_id_conflict`, `mapping_not_active`, `mapping_deprecated`, `mapping_fingerprint_mismatch`, and `source_pin_mismatch`. Native 3D-2 errors propagate unchanged.
- `activate_governed_mapping(*, mapping_id: str, proposal: CapabilityMappingProposal, review: CapabilityMappingReview, current_source_pin: SourceSemanticPin, activation_approval: MappingActivationApproval | None, active_release_context: tuple[CapabilityPackRelease, ...], existing_mappings: tuple[GovernedCapabilityMapping, ...] = ()) -> GovernedCapabilityMapping`.
- `deprecate_governed_mapping(mapping: GovernedCapabilityMapping, *, actor_ref: str, reason: str) -> GovernedCapabilityMapping`.
- `resolve_governed_mapping_for_use(mapping: GovernedCapabilityMapping, *, current_source_pin: SourceSemanticPin, active_release_context: tuple[CapabilityPackRelease, ...], mapping_context: tuple[GovernedCapabilityMapping, ...] = ()) -> GovernedCapabilityBinding`.
- `resolve_governed_mapping_historical(mapping: GovernedCapabilityMapping, *, historical_source_pin: SourceSemanticPin, release_context: tuple[CapabilityPackRelease, ...]) -> GovernedCapabilityBinding`.
- Mapping facet conflict key is `(source_ref, mapping_scope, evidence_fingerprint)`; only two ACTIVE EXACT mappings with that same key and different canonical targets conflict. This uses the actual 3D-3A source identity/scope/evidence contracts and does not compare free text fuzzily.
- `GovernedCapabilityMapping` stores a required `mapping_fingerprint` validated against stable mapping identity, source pin, proposal/review pins, exact mapping type/scope, target definition pin, and activation approval identity/approver. Lifecycle/deprecation metadata is excluded so deprecation retains the same authority payload fingerprint; factories recompute it and both resolvers revalidate it.
- Reviewer and activation approver are not required to be equal or different; 3D-3B records both and adds no separation rule absent an approved governance policy.
- `GovernedCapabilityBinding` reports the exact source ref, scope, mapping ID/fingerprint, exact target definition pin, and resolution mode; it is not a `RecommendationTarget`, learner verification, or course profile.
- All SHA-256 pins use the existing `sha256:<64 lowercase hex>` shape. Mapping/approval/actor IDs are bounded to 256 chars; deprecation reason is bounded to 1,000 chars, matching existing governance conventions.

## Task 1: Source and Review Pins; Activation Approval Contract

**Files:** create `mapping_errors.py`, `mapping_activation.py`; test `test_governed_mapping.py`.

- [ ] Add RED tests for source pin stability, source version/evidence sensitivity, source/evidence identity mismatch, deterministic review fingerprints, and bounded frozen explicit approval fields.
- [ ] Run the focused test and confirm failures are due to missing 3D-3B contracts.
- [ ] Implement SHA-256 over canonical compact sorted-key JSON. Serialize the already canonical 3D-3A evidence tuple; do not reproduce proposal fingerprint logic.
- [ ] Verify focused tests pass; check exact review fingerprint changes when reviewer, decision, proposal pin, or rationale changes.

## Task 2: Governed Mapping and Activation Gate

**Files:** create `governed_mapping.py`; extend `test_governed_mapping.py`.

- [ ] Add RED tests for review ID/fingerprint mismatch and changed proposal invalidating an old review; REJECT/UNCERTAIN; stale source; missing/mismatched approval pins; unknown/DRAFT/inactive/deprecated target, inactive dependency and checksum mismatch; target pin retention/no replacement redirect; AI_ASSISTED requiring the same gates; incomplete direct mapping construction; immutable mapping; deterministic fingerprint; mapping ID distinct from source/capability/proposal identity; reviewer/approver equality being unconstrained; and an active capability/review alone not yielding a governed mapping.
- [ ] Implement an immutable `GovernedCapabilityMapping` with ACTIVE/DEPRECATED status and explicit deprecation record. Store the exact `CapabilityDefinitionPin`, source pin, proposal/review pins, activation approval ref and approver.
- [ ] Implement activation in required order: 3D-3A review integrity → APPROVE decision → source pin match → `resolve_for_new_binding` → exact target-ref check → approval pin check → mapping identity/conflict checks → ACTIVE value/fingerprint.
- [ ] Reuse and propagate native 3D-2 authority errors (unknown namespace/capability, inactive pack/definition, dependency/checksum failures); do not inspect pack internals or choose replacements/latest.
- [ ] Verify focused RED/GREEN tests; ensure no new state is emitted on any failure.

## Task 3: Mapping Identity, Conflict Gate, and Lifecycle

**Files:** `governed_mapping.py`; extend `test_governed_mapping.py`.

- [ ] Add RED tests for same mapping ID/different authority payload, stable repeat activation of an identical ACTIVE mapping, conflict for the same source semantic ref+scope+source pin mapped to different targets, no conflict for distinct source-semantic facet identities belonging to one aggregate, and no fuzzy conflict inference.
- [ ] Implement conflict checks only over the explicitly supplied mapping context; ignore non-ACTIVE entries and do not use semantic similarity.
- [ ] Add RED tests for ACTIVE→DEPRECATED and blocked DEPRECATED→ACTIVE. Deprecation requires nonblank actor/reason, returns a new frozen value, and leaves semantic mapping fingerprint unchanged.
- [ ] Verify focused tests pass, including no automatic conversion from `UnmappedSemantic`.

## Task 4: Current-Use and Historical Resolution

**Files:** create `mapping_resolution.py`; extend `test_governed_mapping.py`.

- [ ] Add RED tests for ACTIVE/source-fresh/exact-target requirements in current resolution; stale source ID/version/evidence; newer active target release without auto-repin; missing/checksum-mismatched/inactive-dependency targets; and ACTIVE/deprecated mapping historical resolution via exact 3D-2 pins, including DRAFT historical target rejection.
- [ ] Add a domain-neutral `GovernedCapabilityBinding` result that retains exact pins and distinguishes current from historical resolution.
- [ ] Current resolver calls `resolve_for_new_binding` for the stored canonical ref and requires the returned full pin to equal the mapping's stored pin. Historical resolver calls `resolve_historical` with the exact stored pin; draft authority must remain rejected by 3D-2.
- [ ] Validate stored mapping fingerprint and source pin before returning either result. Current resolution checks any supplied mapping context for conflicting active exact targets and never treats the historical result as eligible for new use.
- [ ] Verify focused tests pass; historical success must never be labeled eligible for new use.

## Task 5: Documentation, Evidence, and Regression Gate

**Files:** create the 3D-3B research report and `test/results/course-rec-01a-3d-3b/` artifacts.

- [ ] Add evidence for prerequisite contract reuse, source/review pins, approval, exact target authority/pin, governed mapping, lifecycle, current/historical resolution, stale source/target, conflicts, semantic boundaries, regression and static checks.
- [ ] Run focused 3D-3B tests and regression for 3D-1 identity, 3D-2 definitions/pack lifecycle/resolution, 3D-3A contracts, catalog fixtures/schemas/semantic enrichment, recommendation, LearningNeed, role source adapter, and semantic-core/policy contracts.
- [ ] Run changed-scope Ruff format/check and mypy; validate JSON, whitespace, `git diff --check`, and scoped secret scan.
- [ ] Confirm LMS HEAD/status unchanged, upstream 3D-1/2/3A and 01B files unchanged, no external calls, no files staged, and no commit/push.
- [ ] Write the required 27-section final report and evidence; report any failed or unrun gate explicitly.

## Self-Review Coverage

The 65-case acceptance matrix in the task is covered across Tasks 1–5: upstream type reuse; review integrity/decision; source staleness; exact active authority/dependency and pin; approval pins; deterministic mapping/lifecycle; current/historical behavior; target drift; conflicts/facets; AI/unmapped/semantic boundaries; and regression suites. Synthetic namespaces/packs only. No task edits upstream contracts or the 01B engine.

## Execution Constraints

- The current canonical checkout contains required 3D-1/2/3A implementation as pre-existing untracked files, so an isolated worktree created from HEAD would omit test/runtime dependencies. Plan to work in place after the plan is approved; preserve every unrelated dirty/untracked artifact.
- The user explicitly forbids commits and pushes; do not include commit steps despite the default planning template.
- No subagent tool is available in this session; if executed inline, perform a separate self-review and state that it is not an independent review.
