# Exclude from the initial MVP migration

- `backend/test/results/**` experiment outputs, review packets, manifests, raw result folders and generated artifacts.
- Human reviewer submissions, blinded-review recovery/merge scripts and private condition mappings.
- Smoke/experiment CLIs and model-comparison runners under `backend/app/instructional_design/`.
- `graphify-out/` and other temporary analysis outputs.
- Raw CV/JD files, model prompts, model traces, provider payloads and secrets.
- Source Alembic history as a direct target migration input.
- Source SQLAlchemy repositories/models until target domain ownership and Prisma schema are approved.
- Source FastAPI routes as direct copy/paste; target uses a global `/api` prefix and different auth/response contracts.
- Source certificate/credential code until course certificates and competency credentials are explicitly separated.
- Target seed passwords, local `.env` files and uploaded assets.
- Any target sibling deletion/replacement state under `5. SOURCE/source_code/ndt-training-management-system-main`; resolve repository ownership separately.
