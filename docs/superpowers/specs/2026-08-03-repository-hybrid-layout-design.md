# Repository Hybrid Layout Design

## Goal

Organize the PAI Platform repository so backend application code, future
frontend work, and operational/CI implementation have explicit top-level
homes, without violating paths that Git hosts require.

## Target Layout

```text
backend/
  app/
  alembic/
  tests/
  pyproject.toml
  uv.lock
  alembic.ini
  .env.example

frontend/
  README.md

devops/
  compose/
    docker-compose.yml
  gitlab/
    pipeline.yml
  github/
    quality.sh

.gitlab-ci.yml
.github/workflows/ci.yml
.gitignore
.pre-commit-config.yaml
docs/
AGENTS.md
MEMORY.md
README.md
```

`frontend/README.md` is an explicit placeholder only. This change does not
select a frontend framework or add frontend runtime code.

## Responsibilities and Boundaries

`backend/` owns the Python modular monolith, database migrations, backend
tests, dependency metadata, and local backend environment example. Python
tooling is invoked from this directory, so module resolution remains rooted
at `backend/`.

`devops/compose/` owns local infrastructure composition. Compose invocations
use `docker compose -f devops/compose/docker-compose.yml ...`. The existing
uncommitted compose content is moved verbatim; this reorganization does not
change service configuration, ports, volumes, or secrets.

`devops/gitlab/pipeline.yml` owns GitLab pipeline jobs. Root
`.gitlab-ci.yml` remains a minimal GitLab-required entrypoint that includes
that file. Root `.github/workflows/ci.yml` remains the complete GitHub Actions
workflow because GitHub discovers workflows only under that exact directory.
It invokes `devops/github/quality.sh` for the backend quality commands, so
the operational command implementation remains in `devops/` without relying
on an unsupported workflow path.

Repository-level governance and discovery files remain at root: `docs/`,
`AGENTS.md`, `MEMORY.md`, `README.md`, `.gitignore`, and
`.pre-commit-config.yaml`. Git metadata (`.git/`) is not a movable project
artifact and remains managed by Git/worktree infrastructure.

## Tooling and Runtime Changes

The backend CI job changes its working directory to `backend/` before
syncing dependencies and running Ruff, mypy, pytest, and Alembic checks.
README commands will state their directory or use explicit `backend/` and
`devops/` paths so a fresh clone remains reproducible.

Alembic's script location and Python import path will be adjusted to resolve
within `backend/`. No migration contents, domain/module boundaries, API
behavior, database schema, or authorization policy changes are in scope.

## Compatibility and Failure Behavior

The root GitLab and GitHub entrypoints prevent silent loss of hosted CI
discovery. CI must fail if the delegated GitLab pipeline or quality script
cannot be loaded, or backend quality checks fail. Local developer commands
fail normally when run from an incorrect directory; documented commands
provide the supported paths.

`frontend/` has no build or CI job until an approved frontend implementation
exists. There is no empty directory dependency: its README is tracked.

## Verification

Verification after relocation covers:

- `uv sync --all-extras --locked` and backend lint/type/test commands from
  `backend/`;
- Alembic configuration and migration upgrade against the existing local
  development database workflow;
- Compose configuration validation through the new `devops/compose/` path;
- GitLab include syntax and GitHub wrapper/delegation structure by static
  inspection;
- a repository-wide search confirming no stale root-level backend paths in
  README, CI, or tooling configuration.

## Explicit Non-goals

- No frontend framework, UI, or API client.
- No CI provider migration; GitLab and the existing GitHub workflow remain
  compatible.
- No Docker image/build strategy or deployment environment changes.
- No modular-monolith architecture change and no ADR decision beyond the
  already approved repository organization.
