# INTEGRATION-04A Migration Readiness Report

**Scan status:** COMPLETE  
**Migration readiness:** BLOCKED / NOT READY FOR CODE MIGRATION  
**Scope:** repository and architecture scan only; no runtime code, dependency, migration, or Docker changes.

## Findings

The LMS and PAI can coexist in a monorepo as independently deployable services. The current systems are not ready for a direct merge of source trees or databases. The largest blockers are migration ownership, route/storage collisions, service identity, and the need to preserve PAI privacy/evidence semantics at the integration boundary.

### What can move

- Source trees can be imported into distinct `apps/` roots with history preserved.
- Contract definitions and adapter tests can be shared in `packages/contracts`.
- Documentation, path-filtered CI, local orchestration templates, and repository tooling can be centralized.
- The LMS PAI adapter can remain an LMS-owned integration module calling versioned PAI APIs.

### What must remain independent initially

- Prisma and Alembic migration histories and database ownership.
- LMS course/progress/quiz/certificate records versus PAI evidence/competency/extraction records.
- LMS local uploads versus PAI secured object storage.
- Node and Python dependency/runtime environments.
- PAI model/provider routing and privacy gateway.

### Required prerequisites

1. Clean source snapshots and an explicit policy for the LMS worktree's unrelated deletions/untracked files.
2. Approved namespace, auth, correlation, idempotency, and versioning contracts.
3. Separate database/schema roles, migration locks, backup, and rollback rehearsal.
4. Storage retention/access review and a no-raw-document-at-LMS-provider boundary.
5. CI matrix that runs Node and Python checks independently plus contract tests.

## Risk rating

| Risk | Rating | Mitigation |
|---|---|---|
| Accidental cross-database migration | Critical | Separate runners, credentials, schemas, and CI jobs |
| Semantic collision (`Document`, `Assessment`, `LearningPath`) | High | Explicit namespaces and adapter DTOs |
| Privacy boundary bypass | Critical | Only PAI ModelGateway/PrivacyGateway handles raw CV/JD |
| Route collision | High | `/api/lms` and `/api/pai` at gateway; preserve internals |
| Unclean source import | High | Pin commits and stop on dirty-tree review |
| Shared Redis key/queue collision | Medium | Namespaced keys and queue contracts |

## Decision

`INTEGRATION-04A COMPLETE` means the scan and plan are complete. It does **not** authorize migration. Implementation readiness remains blocked until the prerequisites above are accepted.
