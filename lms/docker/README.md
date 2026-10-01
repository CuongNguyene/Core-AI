# Local Frappe LMS Docker environment

This Compose stack is for local development and debugging. It runs Frappe
Bench with MariaDB and Redis, keeps Bench/database state in named volumes, and
mounts the repository as the live `lms` app.

Run commands from the repository root:

```bash
docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f frappe
```

Open <http://localhost:8000>. The default local credentials are:

- Site: `lms.localhost`
- Administrator: `Administrator`
- Password: `admin`

Override development defaults without editing Compose:

```bash
DB_ROOT_PASSWORD='local-root-password' \
ADMIN_PASSWORD='local-admin-password' \
docker compose -f docker/docker-compose.yml up -d --build
```

The default Frappe branch is `version-15` to match this repository. Override
`FRAPPE_BRANCH` only when intentionally testing another compatible branch.

## Start, stop, and debug

```bash
# Stop containers but keep all volumes and site data.
docker compose -f docker/docker-compose.yml stop

# Start the existing containers again.
docker compose -f docker/docker-compose.yml start

# Restart only Frappe after changing configuration or Python code.
docker compose -f docker/docker-compose.yml restart frappe

# Open a shell in the running Bench container.
docker compose -f docker/docker-compose.yml exec frappe bash

# Run Bench commands inside the site.
docker compose -f docker/docker-compose.yml exec frappe \
  bash -lc 'cd /home/frappe/frappe-bench && bench --site lms.localhost migrate'
```

The repository is mounted at `/workspace` and is also exposed to Bench as
`/home/frappe/frappe-bench/apps/lms`. Python changes are therefore live. The
asset watcher is enabled by default for frontend development. To disable it:

```bash
ENABLE_ASSET_WATCH=0 docker compose -f docker/docker-compose.yml up -d
```

## Connect local Core-AI PAI

The Compose file mounts a sibling Core-AI checkout at `/workspace/core-ai`.
The default host path is `../../Core-AI` relative to this Compose file; use
`CORE_AI_PATH=/absolute/path/to/Core-AI` when the repositories are elsewhere.

Start PAI from the Core-AI checkout on the Docker host:

```bash
cd ../Core-AI/services/pai-backend
cp backend/.env.example backend/.env
cp devops/compose/.env.example devops/compose/.env
docker compose \
  --env-file devops/compose/.env \
  -f devops/compose/docker-compose.local.yml \
  up -d --build
```

Then install the bridge inside the Frappe container:

```bash
docker compose -f docker/docker-compose.yml exec -u frappe frappe bash -lc '
  cd /workspace/core-ai &&
  ./scripts/attach-lms.sh \
    --bench /home/frappe/frappe-bench \
    --site lms.localhost
'
```

For this Docker-to-host development setup, configure PAI Settings with
`http://host.docker.internal:18000`, enable `Allow Insecure Local PAI URL`,
and keep the site in developer mode. Do not use `127.0.0.1:18000` from inside
the Frappe container.

Dependencies and assets are initialized once per Bench volume. To force a
fresh asset build:

```bash
docker compose -f docker/docker-compose.yml exec frappe \
  rm -f /home/frappe/frappe-bench/.lms-assets-ready
docker compose -f docker/docker-compose.yml restart frappe
```

## Rebuild and reset

```bash
# Rebuild the local Frappe image after changing Dockerfile/init behavior.
docker compose -f docker/docker-compose.yml build frappe

# Recreate containers while preserving named volumes.
docker compose -f docker/docker-compose.yml up -d --force-recreate

# Destructive local reset: removes the Bench, MariaDB, and Redis volumes.
docker compose -f docker/docker-compose.yml down --volumes
```

`stop`, `start`, `restart`, `down`, and container recreation preserve state
unless `down --volumes` is used explicitly.
