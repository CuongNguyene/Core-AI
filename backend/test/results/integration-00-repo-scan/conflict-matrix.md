# INTEGRATION-00 Conflict Matrix

| Area | Source | Target | Conflict Type | Severity | Recommendation |
|---|---|---|---|---|---|
| Runtime | Python/FastAPI modular monolith | TypeScript/NestJS modular backend | dependency_conflict | high | Port contracts/algorithms deliberately or run PAI as a separate service. |
| Identity | Organization-scoped actor UUID, memberships, scoped delegation | User JWT with one role enum; no tenant model | semantic_conflict | blocking | Decide tenant and subject model before any workflow port. |
| Document | CV/JD evidence document with quarantine, hash, retention and extraction linkage | Training resource/document attached to Course | semantic_conflict | high | Keep separate document concepts and endpoints. |
| Learning path | Generated from verified competency and approved gap | Manually authored Course collection and learner assignments | semantic_conflict | high | Add an explicit projection/adapter; never merge models by name. |
| Course content | Objective/evidence/alignment/workload/prerequisite semantics | Course/Module/Lesson content hierarchy | api_contract_conflict | high | Extend target DTO/schema or keep design service upstream. |
| Assessment | Rubric, artifact, evidence, SME review, competency decision | Quiz, answer, attempt, pass score | semantic_conflict | blocking | Separate learning quiz from competency assessment. |
| Evidence | Versioned evidence items, source/locator/verification status | No evidence model | db_schema_conflict | blocking | Introduce target evidence schema or keep source domain service. |
| Credential | Policy-gated competency/course credential with audit and validity | Course Certificate/Template | semantic_conflict | high | Keep certificate and competency credential distinct. |
| API prefix | FastAPI routes without target /api prefix | NestJS global /api | api_contract_conflict | medium | Use an explicit gateway namespace/version. |
| POST /documents | Multipart upload for source documents | Authenticated training document CRUD | naming_conflict | high | Rename source integration route when exposed through target. |
| POST /learning-paths | Capability-derived path with source invariants | LMS path CRUD | naming_conflict | high | Use /development-plans or /generated-learning-paths for source projection. |
| Database | Alembic/SQLAlchemy async tables | Prisma/PostgreSQL tables | migration_conflict | blocking | No direct migration merge; define target-owned schema and forward-only Prisma migrations. |
| Queue | Extraction worker abstraction; provider choice unsettled | BullMQ processors for grading/email/certificates | runtime_conflict | high | Keep extraction in Python or specify a BullMQ-compatible job contract. |
| Storage | MinIO/S3 object storage and safety boundary | Local uploads/static serving | runtime_conflict | high | Do not port raw upload code without security/retention design. |
| Model gateway | Exact provider/schema/privacy policies | No implemented LLM gateway | runtime_conflict | blocking | Isolate gateway behind service boundary and privacy review. |
| Tests | pytest fixtures and golden/research artifacts | Jest/Supertest and target e2e fixtures | test_fixture_conflict | medium | Translate only contract cases; exclude research artifacts. |
| Worktree state | Source dirty with ID-04 work; target parent dirty with sibling deletions | Both have pre-existing changes | runtime_conflict | high | Record baselines and resolve authoritative target subtree before porting. |

## Highest-risk five

1. Missing target organization/tenant and source trusted-actor semantics.
2. Missing target evidence, CV/JD, RoleProfile, competency and policy domains.
3. Same-name but different `Document` and `LearningPath` APIs/models.
4. Quiz/certificate behavior being mistaken for competency assessment/credential behavior.
5. Independent Alembic and Prisma schema histories plus the dirty parent target worktree.
