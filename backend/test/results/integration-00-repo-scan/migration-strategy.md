# Recommended migration strategy

The target is not ready for a direct code merge. Use a contract-first, adapter-led sequence and keep PAI capability/evidence semantics authoritative until the target has explicit equivalents.

1. **Freeze baselines and ownership**
   - Files/modules: source commit `c4af69b...`; target commit `40104df...`; target Git root and sibling deletion state.
   - Dependencies: product owner decision on authoritative target subtree, tenant scope and service boundary.
   - Risk: blocking because the target parent worktree has pre-existing deletions.
   - Validation: `git status --short` in both repositories.
   - Rollback: no code change; discard only the scan artifacts if requested.

2. **Port language-neutral contracts as a versioned schema package**
   - Files/modules: instructional-design contracts/schemas, evidence schemas, capability semantic-core contracts.
   - Dependencies: Pydantic-to-TypeScript mapping, enum policy, strictness and versioning decision.
   - Risk: high; target has no evidence/capability equivalents.
   - Validation: cross-language JSON fixtures for accepted/rejected payloads.
   - Rollback: keep source schemas authoritative and remove only the target adapter package.

3. **Port deterministic validators and normalization**
   - Files/modules: `dependency_normalizer.py`, `quality_gate.py`, `workload.py`, `prerequisite_minimality.py`, `practice_coverage.py`, capability rules.
   - Dependencies: contract package and golden fixtures.
   - Risk: high; preserving `UNKNOWN`, evidence gaps, objective ownership and no-fallback policy is essential.
   - Validation: translated golden tests and property tests in the target language.
   - Rollback: feature-flag target implementation and route calls to source service.

4. **Add source-domain persistence only after target semantics are approved**
   - Files/modules: Organization/Membership, Evidence, CV/JD extraction, RoleProfile, Competency, GapPortfolio, SemanticPolicy and audit records.
   - Dependencies: target Prisma schema ownership, tenant model, retention, policy and audit decisions.
   - Risk: blocking; do not reuse User/Document/Certificate by name alone.
   - Validation: Prisma schema validation, migration review, repository integration tests against a disposable database.
   - Rollback: forward-only compensating migration or isolated schema namespace; never edit applied history.

5. **Integrate model gateway and extraction worker**
   - Files/modules: source ModelGateway/PrivacyGateway and extraction worker, target jobs/BullMQ only if the contract is explicit.
   - Dependencies: provider, privacy, retry, structured-output and data-retention decisions.
   - Risk: blocking for untrusted CV/JD input and external model routing.
   - Validation: mocked provider contract, privacy-denial test, retry/timeout test and no-sensitive-log test.
   - Rollback: run Python extraction service independently behind an internal API.

6. **Expose API adapters**
   - Files/modules: target controllers/DTOs for extraction, role profile, capability analysis and generated learning plans.
   - Dependencies: auth/tenant adapter and source response provenance.
   - Risk: high; avoid collisions with `/api/documents` and `/api/learning-paths`.
   - Validation: OpenAPI diff, auth matrix, response fixture compatibility and explicit namespace tests.
   - Rollback: disable adapter routes without touching target LMS routes.

7. **Project approved design into target LMS content**
   - Files/modules: target Course/Module/Lesson/Quiz DTOs plus a provenance link to source design output.
   - Dependencies: approved objective/evidence/alignment extension or external design record.
   - Risk: high; projection must not imply competency verification.
   - Validation: create/read/update draft flow and assertion that course completion does not change competency state.
   - Rollback: delete only unpublised projection records or disable projection job.

8. **Add FE contract and E2E flow**
   - Files/modules: `frontend/src/types/api.ts`, Axios services, routes and target e2e tests.
   - Dependencies: stable `/api` adapter paths and response envelopes.
   - Risk: medium/high.
   - Validation: Playwright or Supertest-backed flow from upload/review through approved learning-plan projection.
   - Rollback: hide new routes/menu entries and preserve existing LMS flows.
