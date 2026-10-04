# COURSE-REC-01A.3D-2 — CAPABILITY DEFINITION & PACK LIFECYCLE

## Status

COMPLETE — bounded in-memory domain authority and evidence implemented; regression/static verification is recorded below. No persistence, API, mappings, production taxonomy, LMS changes, commit, or push.

## 1. Repository

- Core-AI: `/Users/mac/Developers/work/LMS/Core-AI`
- Branch: `feat/deterministic-ai-course-planning-workspace`
- HEAD at preflight: `a078526ab7ea38327fdeece142aba325f3de3352`
- LMS: `/Users/mac/Developers/work/LMS/lms`, branch `feat/learning-operations-phase-1`, HEAD `129fde12a3856eb07a8690ab0ebac528b2f26e61`; clean and unchanged.
- Core-AI had unrelated/pre-existing dirty files and untracked COURSE-REC-01A/01B, 3D-1 and other evidence. They were preserved.

## 2. 3D-1 Dependency

Reused `CanonicalCapabilityRef` from `app.capability_governance.identity`; its strict syntax and version-independent identity remain unchanged. Definition identity is `canonical_ref`; labels and explanatory text are not identity.

## 3. Module Placement

Pure domain contracts live in `app.capability_governance`: existing `identity.py`, plus `definitions.py`, `packs.py`, `resolution.py`, `errors.py`, and package exports. No repository/service/API layer was introduced.

## 4. Capability Definition

`CapabilityDefinition` is immutable and includes canonical ref, nonblank label and definition, lifecycle status, optional replacement ref, and deprecation record. Empty releases and duplicate canonical refs are rejected.

## 5. Capability Pack

`CapabilityPackId` is a stable validated identifier, independent of namespace and release. A release has exactly one namespace and all included definitions must belong to it. Owner refs are opaque validated values; authorization is explicitly outside this contract.

## 6. Release Identity

`CapabilityPackReleaseRef` pins pack ID, exact version token, and SHA-256 checksum. Versions are bounded opaque exact strings, not SemVer ranges; latest/current selectors and ranges are not accepted.

## 7. Checksum

SHA-256 is computed over canonical compact sorted-key JSON for pack ID, namespace, version, definitions (sorted by canonical ref), and exact dependencies (sorted by pack/version/checksum). Lifecycle, owner, review, approval and deprecation metadata are excluded. Ordering-insensitivity and semantic-change sensitivity are tested.

## 8. Dependencies

Dependencies reference exact pack/version/checksum identities. Duplicate dependency identities, missing or mismatched refs, inactive dependencies for new binding, and dependency cycles fail closed. Historical resolution accepts exact deprecated dependencies.

## 9. Governance

Activation requires an approved semantic review with explicit collision-review evidence and an explicit approval record. Reviewer must differ from pack owner. The domain contract records decisions and references; it does not implement identity authentication or RBAC. Approver/reviewer separation is not additionally imposed.

## 10. Lifecycle

Pack releases and definitions support DRAFT, ACTIVE, DEPRECATED. Lifecycle helpers return new frozen values. Active content is immutable; deprecation is explicit and historical references are retained. Replacement refs are informational and never redirect resolution.

## 11. Activation Gate

Activation validates draft state, definition status, governance decisions, exact dependency closure, acyclicity, namespace authority, and active-ref collisions before returning an ACTIVE release. Any failed gate leaves the input value unchanged.

## 12. Namespace Authority

One stable pack identity owns exactly one namespace across its release history. A different pack identity cannot claim that namespace, including after the previous pack is deprecated. Ownership metadata may evolve under the same pack ID; identity is not transferred. Conflicting namespace or simultaneous active canonical refs are rejected.

## 13. Definition Pin

`CapabilityDefinitionPin` pairs a canonical ref with an exact pack release ref including checksum. Syntactic identity alone does not establish registry membership or active authority.

## 14. Active Resolution

`resolve_for_new_binding` resolves only one ACTIVE release and ACTIVE definition, with an ACTIVE exact dependency closure. Unknown namespace, unknown capability, inactive pack/definition, ambiguous authority, dependency failure and namespace conflict are explicit errors. It never selects a latest release.

## 15. Historical Resolution

`resolve_historical` checks exact pack ID, version, checksum and canonical ref. ACTIVE and DEPRECATED definitions/releases are resolvable; DRAFT is not. It validates exact dependency history and never follows replacement refs.

## 16. Collision Handling

Duplicate canonical refs inside a release, duplicate active authorities, namespace reassignment, duplicate release identity, and dependency cycles fail closed. A collision-review reference is required at activation; semantic equivalence is not inferred heuristically.

## 17. Definition Evolution

Successive releases may retain a canonical ref while labels/documentation evolve. Such changes alter the release checksum but not identity. A material semantic meaning change cannot be mechanically proven and requires governance review. Old definitions remain available for exact historical resolution.

## 18. Legacy Compatibility

No changes were made to `professional_capability_core@0.1`, catalog schemas, recommendation engine, or legacy references. 3D-1 identity contracts and existing catalog/recommendation/semantic-policy tests pass in the scoped regression suite.

## 19. Parallel 3D-3A Boundary

No 3D-3A mapping/outcome contracts were present at preflight or created/edited here. No source-to-capability mappings, mapping evidence, mapping approvals, or coverage claims are implemented.

## 20. Tests

Focused 3D-2 plus related identity/catalog/recommendation/LearningNeed/semantic-policy regression: `219 passed`.

## 21. Negative Cases

Tests cover malformed/empty definitions, invalid lifecycle transitions and governance, rejected or missing approvals/reviews, owner-review conflict, non-exact refs, checksum mismatch, namespace conflicts/reassignment, duplicate capability/release/dependency, missing or inactive dependency, dependency cycle, unknown namespace/capability, inactive authority, draft historical resolution, and missing historical release.

## 22. Static Checks

- Ruff format check: PASS
- Ruff check: PASS
- mypy `app/capability_governance`: PASS, 6 source files
- Scoped regression: PASS, 219 tests
- `git diff --check`: PASS
- JSON evidence validation: PASS
- No network/model/live-service tests were applicable.

## 23. Files Changed

3D-2 code: `app/capability_governance/{__init__,definitions,errors,packs,resolution}.py`; tests: `test_capability_definitions.py`, `test_capability_pack_lifecycle.py`, `test_capability_resolution.py`. 3D-1 `identity.py` and its test were not modified. Documentation and evidence are listed in this report and adjacent results directory.

## 24. Architecture Conformance

Identity syntax, registered definition, active authority, semantic mapping, and learner outcome remain separate. This milestone implements only in-memory definition/pack authority and exact resolution. No persistence, HTTP, migration, UI, production taxonomy, or LMS changes.

## 25. Known Limitations

The caller supplies the in-memory release context; the module does not persist or authenticate it. Governance references/decisions are validated as contract data, not cryptographically verified or authorized. Semantic meaning drift cannot be automatically detected. Namespace ownership guarantees apply to the supplied authority context.

## 26. 3D-3B Readiness

3D-2 provides exact active/historical capability authority and pins for later integration. 3D-3A remains a separate parallel contract task; 3D-3B is not implemented here.

## 27. Final Decision

COMPLETE for the bounded 3D-2 domain-authority milestone. Success criteria are met for definitions, immutable release identity/checksum, namespace authority, governance activation, lifecycle, exact active and historical resolution, negative cases, backward-compatibility regression, and static checks.

## 28. Git Status

Core-AI remains on `feat/deterministic-ai-course-planning-workspace` at preflight HEAD `a078526ab7ea38327fdeece142aba325f3de3352`. Existing unrelated work was preserved; only the listed 3D-2 additions are part of this milestone. LMS remains clean and unchanged. No files were staged, committed, or pushed.
