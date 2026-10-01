# Frappe LMS Dockerization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a persistent, debuggable local Docker environment for the Frappe LMS Bench.

**Architecture:** A repository-built development image will run a persistent Frappe Bench volume. MariaDB and Redis remain separate services with healthchecks. The repository is bind-mounted into the bench's `apps/lms` path so application edits are live without rebuilding the image.

**Tech Stack:** Dockerfile, Docker Compose, Bash, Frappe Bench, MariaDB, Redis.

**Spec:** `docs/superpowers/specs/2026-09-30-frappe-dockerization.md`

## Global Constraints

- Keep the scope limited to Docker configuration, initialization, and operator documentation.
- Do not change application Python, Vue, DocType, migration, or dependency source files.
- Keep local development defaults clearly development-only.
- Make initialization safe to run repeatedly after container recreation.

## Review Focus

- A fresh named bench volume must initialize the site exactly once and survive container recreation.
- An existing site must not be recreated or reinstalled on every start.
- The live repository mount must be the app loaded by Bench, not a stale copied app.
- MariaDB/Redis startup ordering must be enforced by healthchecks.
- The documented reset command must be explicit about deleting persistent volumes.

---

### Task 1: Add the development image and idempotent Bench bootstrap

**Files:**
- Create: `docker/Dockerfile`
- Modify: `docker/init.sh`

**Interfaces:**
- Consumes: `BENCH_DIR`, `SITE_NAME`, `DB_ROOT_PASSWORD`, `ADMIN_PASSWORD`, and `/workspace` environment/mounts.
- Produces: a running Bench at `/home/frappe/frappe-bench` with the repository available as `apps/lms`.

- [ ] Write a shell syntax check that targets `docker/init.sh`.
- [ ] Run `bash -n docker/init.sh` and confirm the current script is syntactically valid before editing.
- [ ] Add a Dockerfile based on `frappe/bench:latest` that copies and marks the init script executable.
- [ ] Rewrite initialization with strict Bash mode, configurable paths/passwords, safe repeated setup, local app mounting, site existence detection, and final `bench start`.
- [ ] Run `bash -n docker/init.sh` and inspect the resulting diff.

### Task 2: Make Compose persistent and debug-friendly

**Files:**
- Modify: `docker/docker-compose.yml`
- Create: `docker/.dockerignore`

**Interfaces:**
- Consumes: the image and init contract from Task 1.
- Produces: `mariadb`, `redis`, and `frappe` services with persistent volumes, healthchecks, build configuration, and live source mounts.

- [ ] Add Compose build configuration, development environment defaults, healthchecks, dependency conditions, ports, and named volumes.
- [ ] Mount the repository into the Bench app path and keep a `/workspace` mount for shell/debug access.
- [ ] Add a narrow Docker build context ignore file for Git metadata, frontend dependencies, caches, and generated artifacts.
- [ ] Run `docker compose -f docker/docker-compose.yml config` and confirm the rendered configuration is valid.

### Task 3: Document operator workflows

**Files:**
- Create: `docker/README.md`

**Interfaces:**
- Consumes: service names, volume names, ports, and commands from Tasks 1–2.
- Produces: documented start, stop, restart, logs, shell, rebuild, reset, and verification workflows.

- [ ] Document commands from repository root using `docker compose -f docker/docker-compose.yml`.
- [ ] Explain that `stop/start` preserves state, while `down --volumes` resets it.
- [ ] Document default local credentials and the supported environment overrides.
- [ ] Verify every documented service and volume name against Compose.

### Task 4: Verify the Dockerization

**Files:**
- No new production files.

- [ ] Run YAML/Compose validation.
- [ ] Build the local image with `docker compose -f docker/docker-compose.yml build frappe`.
- [ ] Start MariaDB, Redis, and Frappe with `docker compose -f docker/docker-compose.yml up -d`.
- [ ] Verify service status, logs, and HTTP availability on port 8000.
- [ ] Stop and start the stack, then verify the site remains available.
- [ ] Run the repository test/quality checks that are practical without modifying application code.
- [ ] Run `git diff --check` and `git status --short`.
