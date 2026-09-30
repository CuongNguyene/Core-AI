# INTEGRATION-00 — PAI Learning to NDT TMS migration plan

## Why this scan exists

PAI Learning contains evidence-based CV/JD extraction, competency analysis and instructional-design logic. The NDT Training Management System contains an actively developed NestJS/React LMS vertical slice. The goal is to identify what can be reused without silently changing the meaning of evidence, competency, assessment, learning path or credential data.

This document is an inventory and conflict map only. It does not authorize porting code.

## Methodology

The scan inspected both working trees with bounded `find`, `ls`, `sed` and `rg` searches, plus `git status --short`, branch and commit metadata, and `git diff --check`. No tests, dependency installation, Docker commands, database migrations, merges, rebases or source/target code changes were run. Existing dirty-worktree state was preserved.

## Repository summary

| | PAI source | NDT target |
|---|---|---|
| Path | `/Users/mac/Developers/work/PAI Learning/Pai-learning/.worktrees/pr-012-instructional-design-core` | `/Users/mac/Developers/work/CT_Brain_Hub/ct_brain_hub/5. SOURCE/ndt-training-management-system-main` |
| Commit | `c4af69b78fe7eb8f4ed0654f5007a17599886005` | `40104dfd9e01b915534422f1cf97c30bff0e3b26` |
| Backend | Python 3.13+, FastAPI, async SQLAlchemy | Node 20, TypeScript, NestJS 11, Prisma 5.22 |
| Database | PostgreSQL, Alembic | PostgreSQL, Prisma migrations |
| Frontend | placeholder | React 19/Vite 8 with Axios, MobX and TanStack Query |
| Queue/storage/model | worker abstraction, MinIO/S3 boundary, ModelGateway/PrivacyGateway | BullMQ/Redis, local uploads, no implemented LLM gateway found |

The target application directory is inside the parent Git root `/Users/mac/Developers/work/CT_Brain_Hub/ct_brain_hub`. That parent worktree currently reports deletions under the sibling `5. SOURCE/source_code/ndt-training-management-system-main`; this must be clarified before integration.

## Classification

### Portable core, with TypeScript adaptation

- Instructional-design contracts, schemas, dependency normalization, quality gates, workload semantics, prerequisite minimality and practice coverage.
- Domain-neutral capability semantic-core contracts and deterministic gap rules.
- Evidence schemas and evidence-preserving extraction normalization/graph logic.

These are not copyable as Python files into the target. They are candidates for versioned cross-language schemas, a standalone Python service, or a deliberate TypeScript reimplementation with golden fixtures.

### Integration-specific

- FastAPI routes and source response/error contracts.
- SQLAlchemy models/repositories and Alembic migrations.
- Organization-scoped authorization, document storage, extraction worker wiring, ModelGateway and PrivacyGateway provider configuration.
- Target controllers, Prisma models/migrations, JWT/CASL guards, BullMQ processors, local upload serving and existing frontend Axios contracts.

These need adapters and explicit ownership decisions; direct merging is unsafe.

### Research-only

- Smoke/experiment runners, blinded-review recovery/merge/analysis tools, fixtures, review submissions, experiment output folders, generated manifests, graphify output and raw traces.

Keep these in the source research workflow. They should not enter the target MVP runtime or production database.

## Semantic conflict matrix

The detailed matrix is in `backend/test/results/integration-00-repo-scan/conflict-matrix.md`. The five highest-risk conflicts are:

1. Source organization/tenant and trusted-actor semantics have no target equivalent.
2. Evidence, CV/JD, CandidateProfile, RoleProfile, Competency, capability-gap and policy domains are missing from target.
3. `Document` and `LearningPath` share names but not invariants, ownership or response shape.
4. Target quizzes/certificates must not be treated as source competency assessments/credentials.
5. Alembic and Prisma histories cannot be merged, and the target parent worktree has pre-existing sibling deletions.

## Recommended migration order

1. Freeze repository baselines and establish the authoritative target subtree.
2. Decide tenant/actor, evidence ownership, service boundary and credential separation.
3. Translate versioned contracts and golden fixtures.
4. Port deterministic validators and semantic rules.
5. Add target-native persistence for approved missing domains.
6. Integrate ModelGateway/PrivacyGateway and extraction worker through an explicit boundary.
7. Expose namespaced API adapters; do not collide with `/api/documents` or `/api/learning-paths`.
8. Project approved design outputs into target draft Course/Module/Lesson/Quiz content with provenance.
9. Add frontend contracts and end-to-end tests only after backend response/auth contracts stabilize.

Each step’s dependencies, validation and rollback approach are recorded in `backend/test/results/integration-00-repo-scan/migration-strategy.md`.

## Readiness

`BLOCKED_BY_SEMANTIC_UNKNOWN`

The repositories are accessible and inventoryable, but the target does not yet define enough domain semantics to safely plan a direct port. No code porting should begin until the required clarifications in `integration-readiness-report.json` are answered.
