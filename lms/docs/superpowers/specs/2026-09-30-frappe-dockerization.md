# Frappe LMS Dockerization Specification

## Goal

Provide a reproducible local Frappe Bench environment for the LMS repository with persistent database/bench state, live source mounts for debugging, and predictable start/stop/build commands.

## Constraints

- Keep the scope limited to Docker configuration, initialization, and operator documentation.
- Use the existing Frappe Bench, MariaDB, Redis, and Frappe LMS application architecture.
- Do not change application Python, Vue, DocType, migration, or dependency source files.
- Keep local development defaults clearly development-only.
- Make initialization safe to run repeatedly after container recreation.
- Preserve the current source tree as the live LMS app inside the bench.

## Design

- Build a local image from `frappe/bench:latest` and copy the initialization script into it.
- Persist the bench directory, MariaDB data, and Redis data in named Docker volumes.
- Bind-mount the repository into the bench's `apps/lms` path so edits are visible without rebuilding the image.
- Configure MariaDB and Redis service healthchecks and make the bench wait for them.
- Initialize the bench and site only when missing; otherwise apply host configuration and start it.
- Document start, stop, logs, shell access, rebuild, reset, and verification commands.

## Acceptance Criteria

- `docker compose -f docker/docker-compose.yml config` succeeds.
- The bench service is built from a repository Dockerfile.
- Recreating the bench container does not recreate the bench/site/database state.
- The repository source is mounted as the `lms` app.
- `docker compose stop` and `start` provide the intended on/off workflow.
- Resetting state requires an explicit `down --volumes` command.
