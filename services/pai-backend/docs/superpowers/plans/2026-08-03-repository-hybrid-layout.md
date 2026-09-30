# Repository Hybrid Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the repository into backend, frontend, and devops ownership folders while preserving hosted CI discovery and current backend behavior.

**Architecture:** Move Python application assets and tooling into `backend/`, create a tracked frontend placeholder, and move Compose plus GitLab CI implementation into `devops/`. Keep only host-required CI discovery files at root; GitHub invokes a script stored in `devops/` and GitLab includes its pipeline from `devops/`.

**Tech Stack:** Python 3.12, uv, FastAPI, Alembic, Docker Compose, GitLab CI, GitHub Actions.

## Global Constraints

- Preserve the modular monolith and all domain/API/persistence behavior.
- Do not introduce a frontend framework, deployment target, Docker image, or credentials.
- `.git/`, `.gitignore`, `.pre-commit-config.yaml`, `docs/`, `AGENTS.md`, `MEMORY.md`, and root README remain repository-level artifacts.
- `.gitlab-ci.yml` and `.github/workflows/ci.yml` remain at host-required paths.
- Preserve the uncommitted local Compose modification while ensuring it is not included in this reorganization commit.
- Use `backend/` as the working directory for Python tooling after relocation.

---

### Task 1: Move backend ownership and make local tooling path-correct

**Files:**
- Move: `app/` → `backend/app/`
- Move: `alembic/` → `backend/alembic/`
- Move: `tests/` → `backend/tests/`
- Move: `pyproject.toml`, `uv.lock`, `alembic.ini`, `.env.example` → `backend/`
- Modify: `backend/pyproject.toml`, `backend/alembic.ini`

**Consumes:** Existing Python package paths, Alembic migrations, and locked uv dependencies.

**Produces:** A self-contained `backend/` working directory where imports resolve as `app.*`, tests discover from `tests/`, and Alembic finds its migration directory.

- [ ] **Step 1: Capture the expected backend tool behavior before moving files**

Run:

```bash
uv run --extra dev ruff check .
uv run --extra dev mypy app
uv run --extra dev pytest -q
```

Expected: all current quality checks pass from the original root layout.

- [ ] **Step 2: Relocate backend-owned files with Git-aware moves**

Run:

```bash
mkdir -p backend
git mv app alembic tests pyproject.toml uv.lock alembic.ini .env.example backend/
```

Expected: Git reports renames and no application source is left at root.

- [ ] **Step 3: Make backend tooling self-contained**

In `backend/pyproject.toml`, retain `pythonpath = ["."]` and
`testpaths = ["tests"]`. In `backend/alembic.ini`, retain
`script_location = alembic` and `prepend_sys_path = .`. These relative values
must be interpreted from `backend/`.

- [ ] **Step 4: Verify the relocated backend**

Run from `backend/`:

```bash
uv sync --all-extras --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run pytest -q
```

Expected: all quality checks pass without root-level Python files.

- [ ] **Step 5: Commit backend relocation**

```bash
git add backend
git commit -m "refactor: move backend into dedicated directory"
```

### Task 2: Create frontend placeholder and relocate operational implementation

**Files:**
- Create: `frontend/README.md`
- Create: `devops/compose/docker-compose.yml`
- Create: `devops/github/quality.sh`
- Create: `devops/gitlab/pipeline.yml`
- Create: `.gitlab-ci.yml`
- Modify: `.github/workflows/ci.yml`
- Remove: root `docker-compose.yml`

**Consumes:** The relocated `backend/` commands and the current local Compose service definition.

**Produces:** A tracked frontend boundary, an operational Compose path, GitLab pipeline include, and GitHub CI that invokes implementation held in `devops/`.

- [ ] **Step 1: Preserve the local Compose diff before staging the relocation**

Inspect the exact uncommitted `docker-compose.yml` diff. Add
`devops/compose/docker-compose.yml` with the committed baseline content, stage
the root deletion and new baseline file, then apply the inspected local diff
to the new file *after staging*. Do not stage the modified new file again.

Expected: the reorganization commit records the file move only, and the local
Compose port/configuration adjustment remains an unstaged change at its new
path.

- [ ] **Step 2: Add the intentionally empty frontend boundary**

Create `frontend/README.md` stating that no framework or runtime exists yet,
and that frontend design must receive its own approved ADR/spec before code is
introduced.

- [ ] **Step 3: Add host-compatible CI delegation**

Create `devops/github/quality.sh` with `set -eu`, `cd backend`, and these
commands:

```bash
uv sync --all-extras --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run pytest -q
```

Update `.github/workflows/ci.yml` to retain checkout and uv setup, then invoke
`./devops/github/quality.sh`. Create `.gitlab-ci.yml` containing only an
include of `devops/gitlab/pipeline.yml`. Create that pipeline with a `quality`
job using `image: ghcr.io/astral-sh/uv:python3.12-dhi`, changing into
`backend/`, and running the same locked quality commands.

- [ ] **Step 4: Validate operational paths and CI syntax by inspection**

Run:

```bash
docker compose -f devops/compose/docker-compose.yml config
rg -n 'app/|tests/|alembic/|pyproject.toml|uv run' .github .gitlab-ci.yml devops
```

Expected: Compose resolves successfully; CI paths point to `backend/` or are
intentionally repository-relative.

- [ ] **Step 5: Commit operational layout without the preserved Compose diff**

```bash
git add frontend devops .github/workflows/ci.yml .gitlab-ci.yml
git commit -m "build: organize devops and ci configuration"
```

### Task 3: Update repository documentation and verify end-to-end commands

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `MEMORY.md`
- Modify: relevant files under `docs/` only when they contain now-stale root commands

**Consumes:** The final backend, frontend, and devops paths.

**Produces:** Reproducible setup, quality, migration, and Compose instructions without stale root-layout references.

- [ ] **Step 1: Locate stale root-layout references**

Run:

```bash
rg -n --glob '!backend/.venv/**' 'uv run|uv sync|alembic|docker compose|docker-compose.yml|app\.main|mypy app|pytest' README.md AGENTS.md MEMORY.md docs
```

Expected: a finite list of commands/documentation paths to update.

- [ ] **Step 2: Update documented commands**

Document:

```bash
cd backend && uv sync --all-extras --locked
cd backend && uv run alembic upgrade head
cd backend && uv run uvicorn app.main:app --reload
docker compose -f devops/compose/docker-compose.yml up -d
```

Keep architecture/domain/security decisions unchanged; only update repository
path ownership and operational commands.

- [ ] **Step 3: Run final verification from the new paths**

Run:

```bash
cd backend && uv run ruff format --check .
cd backend && uv run ruff check .
cd backend && uv run mypy app
cd backend && uv run pytest -q
cd backend && uv run alembic current
docker compose -f devops/compose/docker-compose.yml config
git diff --check
```

Expected: backend quality checks and Alembic command pass, Compose resolves,
and there is no whitespace error. The only allowed remaining worktree change
is the preserved unstaged Compose adjustment in its new location.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md AGENTS.md MEMORY.md docs
git commit -m "docs: document hybrid repository layout"
```
