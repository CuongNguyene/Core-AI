# INTEGRATION-04A Monorepo Conflict Matrix

| Surface | Current overlap/conflict | Safe target rule | Risk |
|---|---|---|---|
| Backend roots | LMS `backend/`; PAI `backend/` | `apps/lms-api` and `apps/pai-api`; keep language toolchains separate | High |
| Frontend | LMS `frontend/`; no PAI frontend | Move LMS to `apps/lms-web`; no PAI UI assumption | Low |
| API prefix | LMS `/api`; PAI no global prefix | Expose explicit `/api/lms` and `/api/pai` at gateway, preserve internal routes | High |
| Documents | LMS `/documents` course assets; PAI `/documents` secured sources | Namespace endpoints and storage; adapter passes document IDs only | High |
| Learning paths | LMS `/learning-paths`; PAI learning endpoints | LMS remains system of record; PAI returns proposals through contract | High |
| Assessment/quizzes | LMS quizzes/attempts; PAI assessments/capability decisions | Separate semantics; Learning Result is not evidence | High |
| Database | Prisma/PostgreSQL versus SQLAlchemy/Alembic/PostgreSQL | Separate DB/schema and migration runners | Critical |
| Redis | LMS BullMQ/Socket.IO; PAI queue/cache | Namespace keys/queues and credentials; do not share serialization implicitly | Medium |
| File storage | LMS local `UPLOAD_DIR`; PAI MinIO/S3 | Keep stores separate; signed references at boundary | High |
| Auth | LMS JWT/roles; PAI actor/delegation/privacy authorization | Adapter exchanges scoped service identity, never user DB rows | High |
| Model/provider | PAI ModelGateway/PrivacyGateway only | No LMS direct provider calls or raw CV/JD logging | Critical |
| Environment | Both use `DATABASE_URL` and Redis names | Prefix variables per app in monorepo; map at process boundary | Medium |
| CI/CD | PAI GitHub/GitLab quality scripts; LMS package scripts | Path-filtered jobs plus contract tests; independent deploys first | Medium |
| Docker | Multiple compose files and service names | One dev compose with explicit service names, no implicit DB merge | Medium |
| Migrations | Alembic revisions versus Prisma migrations | Independent ordered jobs and rollback plans | Critical |
| Graph artifacts | `graphify-out/` is PAI/project tooling | Keep generated graph outside runtime images and migration paths | Low |

Any conflict not listed here is a migration discovery item, not permission to auto-resolve by renaming or merging.
