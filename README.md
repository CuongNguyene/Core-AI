# Core AI

`Core-AI` is the independently deployable PAI service. It deliberately does **not** contain a
copy of LMS. LMS remains in its own repository and connects to PAI through the versioned, signed
API exposed by this repository.

## Layout

- `services/pai-backend`: FastAPI API, asynchronous workers, Alembic migrations and Docker stack.

## Local development with an existing LMS checkout

The bridge to PAI lives in the LMS repository (`lms/lms/pai/`), not here. Core-AI no longer ships a
Frappe app.

1. Start PAI. The commands and required local secrets are documented in
   [`services/pai-backend/docs/local-development.md`](services/pai-backend/docs/local-development.md):

   ```bash
   cd services/pai-backend
   cp backend/.env.example backend/.env
   cp devops/compose/.env.example devops/compose/.env
   docker compose --env-file devops/compose/.env \
     -f devops/compose/docker-compose.local.yml up -d --build
   ```

2. In the LMS Desk, complete **PAI Settings**: for local development set the service URL to
   `http://127.0.0.1:18000`, enable **Allow Insecure Local PAI URL**, then add the organisation,
   integration key and Ed25519 signing key that match `backend/.env`. Create a **PAI User Identity**
   for each LMS user who will use PAI.

The PAI readiness endpoint is `http://127.0.0.1:18000/health/ready`.

## Production boundary

Build and deploy LMS and PAI as separate versioned images. Deploy configuration must pin the LMS
image and the `pai-backend` image independently, provide secrets through the deployment platform,
and configure LMS with the PAI HTTPS endpoint. Do not deploy by cloning either repository and do
not commit `.env`, private signing keys, integration keys, documents or object-store data.
