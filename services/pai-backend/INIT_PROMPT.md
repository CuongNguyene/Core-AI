# INIT_PROMPT.md — Template conventions adopted by PAI

PAI adopts the template delivery stack: FastAPI async/SQLAlchemy/Alembic,
PostgreSQL 18, Redis 8, ARQ dispatch, Next.js App Router, React, TypeScript
strict, Tailwind CSS, next-intl, Zod, Nginx and split DevOps Compose.

PAI-specific ADRs override generic template instructions. In particular:

- PostgreSQL remains the durable domain/audit/job source of truth.
- Redis is cache and ARQ broker only; raw CV/JD, prompt, model output and
  authorization authority are never stored there.
- Every model operation uses ModelGateway and PrivacyGateway.
- Authentication is ADMIN-provisioned local password/JWT; no public sign-up.
- All module changes update their relevant `*_document.md`.
- Docker images are not rebuilt automatically unless explicitly requested.
