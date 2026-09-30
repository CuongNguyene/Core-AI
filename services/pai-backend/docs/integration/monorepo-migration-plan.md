# INTEGRATION-04A Monorepo Migration Plan

## Recommendation

Use a service-preserving monorepo migration. Import the LMS and PAI histories into distinct application roots, retain independent runtimes and databases, and introduce only versioned integration contracts. Do not rewrite NestJS to FastAPI or FastAPI to NestJS as part of repository consolidation.

## Phases

### Phase 0 — Freeze and scan (current)

Pin source commits, record dirty worktrees, inventory runtime/DB/API/CI surfaces, and approve ownership boundaries. This phase produces the INTEGRATION-04A artifacts; it makes no runtime changes.

### Phase 1 — Empty monorepo skeleton

Create `apps/lms-web`, `apps/lms-api`, `apps/pai-api`, `apps/pai-worker`, `packages/contracts`, `infra`, and `docs/integration`. Add repository-level conventions without moving production files yet.

### Phase 2 — Import services independently

Use `git subtree` or an equivalent history-preserving import into the four app roots. Keep `package-lock`/npm and `uv.lock`/uv boundaries. Add path-filtered CI and service-local commands. No database or migration execution is part of the import.

### Phase 3 — Contract adapter integration

Move the LMS PAI adapter into the LMS app and publish the existing Course Blueprint/Learning Result contracts under `packages/contracts`. Add contract-only tests, correlation/idempotency handling, and explicit PAI API namespace routing.

### Phase 4 — Unified local orchestration

Create one compose profile that starts both services plus their owned Postgres/Redis/object-storage dependencies. Use distinct networks/volumes or clearly namespaced services. Validate health checks and service-to-service auth only after a migration approval.

### Phase 5 — Deployment and cutover

Deploy services independently behind one gateway, run database backups and migration rehearsal per context, then enable adapter traffic gradually. A rollback must disable the adapter without rolling back either domain database.

## Git and history strategy

Prefer a new integration branch/repository import over copying files into the PAI worktree. Preserve each source commit lineage. Keep the current `integration/pai-lms-contract` branch for contract documentation; do not mix the future monorepo import with feature worktree changes. A subtree import is preferable to a squash when auditability matters; a clean export/import is acceptable only if history retention is documented.

## Exit criteria before implementation

- clean, pinned LMS and PAI source snapshots;
- approved API contract and ownership map;
- separate DB/migration plan and backup/rollback rehearsal;
- path-filtered CI for Node and Python;
- namespace and auth plan for `/api/lms` and `/api/pai`;
- storage/privacy review for raw document flow;
- no unresolved contract collision in the conflict matrix.
