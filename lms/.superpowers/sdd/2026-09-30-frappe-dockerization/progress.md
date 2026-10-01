# SDD ledger — plan: docs/superpowers/plans/2026-09-30-frappe-dockerization.md

Pre-flight: Tasks 1 and 2 share the init-script environment and mount contract; Task 2 will consume the exact variables and paths produced by Task 1. Task 3 consumes Compose service and volume names. Task 4 verifies all prior tasks.

Ruling: Work in the existing `dev` checkout — the user explicitly requested implementation in the shared repository and the branch is not `main` or `master`; no additional worktree was created.

Task 1: complete — added `docker/Dockerfile`; replaced the bootstrap with strict, configurable, repeat-safe initialization; `bash -n docker/init.sh` passed.

Task 2: complete — Compose now builds the local image, persists Bench/MariaDB/Redis volumes, mounts the repository source, and waits for healthy dependencies; `.dockerignore` added; `docker compose -f docker/docker-compose.yml config` passed.

Task 3: complete — added `docker/README.md` covering start/stop/debug/rebuild/reset workflows and local credential overrides.

Task 4: complete — `bash -n`, `py_compile`, Compose validation, image build, clean Frappe v15 site bootstrap, LMS installation/assets, HTTP 200 and `frappe.ping` 200, stop/start persistence, live app mount, app list, and final Compose healthcheck all passed.

Ruling: Frappe v15's development server does not accept `--host`; Bench listens internally on port 8001 and the container exposes port 8000 through the scoped TCP proxy so the public local URL remains unchanged.
