# PR-001 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thiết lập nền tảng FastAPI có health probe, error contract an toàn,
database boundary async, migration tooling và quality gate cho các PR MVP sau.

**Architecture:** Giữ modular monolith. `shared` cung cấp settings, logging,
correlation, error handling và database abstraction; router health chỉ điều
phối readiness, không chứa logic database. Không có domain module gọi model hay
external provider.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy async, Alembic,
structlog, pytest, Ruff, mypy và pre-commit.

## Global Constraints

- Không thêm CV/JD extraction, LLM, authentication production hoặc microservice.
- Không log raw request payload, PII, secret, token, CV/JD hoặc prompt.
- PostgreSQL/Redis/MinIO chỉ là local development boundary theo ADR-0002.
- Error response tuân theo ADR-0003 và mọi request có correlation ID.

---

### Task 1: Foundation decisions and documentation

**Files:**
- Create: `docs/adr/0002-development-infrastructure-boundary.md`
- Create: `docs/adr/0003-api-errors-and-correlation.md`
- Modify: `README.md`

- [x] **Step 1: Document the decisions**

Write ADR-0002 to state that Docker Compose services are development-only and
ADR-0003 to define the safe error envelope and UUID correlation behavior.

- [x] **Step 2: Update runbook**

Document local setup, migration, quality commands, health probes and the fact
that no production infrastructure decision is implied.

### Task 2: Safe runtime boundary and health probes

**Files:**
- Create: `app/shared/database.py`
- Create: `app/shared/errors.py`
- Create: `app/shared/logging.py`
- Create: `app/shared/schemas.py`
- Modify: `app/main.py`
- Modify: `app/shared/config.py`
- Modify: `app/shared/health.py`
- Test: `tests/test_health.py`
- Test: `tests/test_errors.py`
- Test: `tests/test_logging.py`

- [x] **Step 1: Write failing tests**

Cover live health, ready health with available/unavailable database, safe
validation error envelope, generated/forwarded correlation IDs and redaction of
secret-keyed logging fields.

- [x] **Step 2: Verify RED**

Run `uv run pytest tests/test_health.py tests/test_errors.py tests/test_logging.py -q`.
Expected: tests fail because the new endpoints and shared modules do not exist.

- [x] **Step 3: Implement the minimal boundary**

Create lazy async database session ownership with `SELECT 1` readiness check;
install correlation middleware and global error handlers; configure structlog
JSON output with redaction; expose `/health`, `/health/live`, `/health/ready`.

- [x] **Step 4: Verify GREEN**

Run `uv run pytest tests/test_health.py tests/test_errors.py tests/test_logging.py -q`.
Expected: all tests pass without a database server.

### Task 3: Migration and repository quality gates

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `.pre-commit-config.yaml`
- Create: `.gitignore`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Test: `tests/test_migration_config.py`

- [x] **Step 1: Write failing migration configuration test**

Assert that Alembic loads `alembic.ini` and points to the `alembic` script
directory.

- [x] **Step 2: Verify RED**

Run `uv run pytest tests/test_migration_config.py -q`.
Expected: fail because `alembic.ini` does not exist.

- [x] **Step 3: Implement tooling**

Add async Alembic environment using `Base.metadata`, dev dependency
`pre-commit`, ignore local secret/cache files, pre-commit Ruff hooks and CI
commands for format, lint, type check and tests.

- [x] **Step 4: Verify GREEN**

Run `uv run pytest tests/test_migration_config.py -q`, `uv run ruff format
--check .`, `uv run ruff check .`, `uv run mypy app` and `uv run pytest -q`.

- [x] **Step 5: Commit locally**

Run `git add` for PR-001 files and `git commit -m "feat: establish project foundation"`.
