# Core AI

One development workspace for LMS and PAI. The runtimes stay isolated: Frappe owns LMS delivery and
the `pai_frappe` bridge; the FastAPI service owns AI workflows, its database, workers, and raw
document storage.

## Layout

- `apps/lms`: LMS Vue/Frappe application, imported from `feat/ai-skills`.
- `apps/pai_frappe`: Frappe bridge app for signed LMS-to-PAI calls.
- `services/pai-backend`: FastAPI API, workers, Alembic migrations, and PAI Docker services.
- `infra/frappe-init.sh`: bootstraps a development Frappe bench with both apps installed.

## Start locally

1. Copy the environment examples without committing the resulting files:

   ```bash
   cp .env.example .env
   cp services/pai-backend/devops/compose/.env.example services/pai-backend/devops/compose/.env
   cp services/pai-backend/backend/.env.example services/pai-backend/backend/.env
   ```

2. Replace every `replace-with-...` value. Generate an Ed25519 key pair for the signed actor
   context, place only the public key in the PAI backend environment, and store the private key in
   the `PAI Settings` DocType after Frappe starts.

3. Run:

   ```bash
   docker compose up --build
   ```

Frappe becomes available on `http://localhost:8000`; inside the Compose network, configure `PAI
Settings.service_url` as `http://backend:8000`. The first boot creates the site, installs `lms` and
`pai_frappe`, and may take several minutes.

## Safety boundaries

- Do not commit any `.env`, private signing key, integration API key, CV/JD, or object-store data.
- Frappe never calls model providers directly; all AI calls go through `pai-backend`.
- Run database migrations independently: Frappe migrations through Bench and PAI migrations through
  Alembic. Do not share either database or migration runner.
