# INTEGRATION-04A Database Boundary Analysis

## Ownership decision

The monorepo must not merge the LMS Prisma schema and PAI Alembic schema. They are two bounded contexts with different lifecycle and provenance requirements.

| Context | Owner | Representative data | Migration owner |
|---|---|---|---|
| LMS | NestJS/Prisma | User, Course, CourseModule, Lesson, Enrollment, Progress, Quiz, QuizAttempt, Certificate, Notification, LearningPath | LMS team / Prisma |
| PAI | FastAPI/SQLAlchemy | StoredDocument, ExtractionJob/Profile, CandidateProfile, JDExtractionProfile, RoleProfileDraft/RoleCompetencyProfile, Evidence, SemanticPolicy, CapabilityAnalysis, CombinedGapPortfolio, credentials/evidence graph | PAI team / Alembic |

The LMS `Document` model is a course asset record. PAI's document/extraction records are secured-source and provenance records. Equal names do not imply shared identity or a safe table merge.

## Recommended physical arrangement

Phase one keeps two databases (or two PostgreSQL databases) and two migration runners. If one PostgreSQL server is used operationally, use distinct databases or schemas, credentials, ownership roles, and migration locks. Never run Prisma migrations against PAI tables or Alembic migrations against LMS tables.

Cross-context references are opaque IDs and versioned contract references, not foreign keys. The LMS stores PAI IDs only in adapter-owned integration records, with source/version/checksum and correlation metadata. PAI stores no LMS foreign key and does not treat LMS progress, quiz attempts, or certificates as evidence or verified competency.

## Read/write boundary

```text
LMS writes: courses, modules, lessons, enrollments, progress, quizzes, certificates
PAI writes: extraction, evidence, role profiles, semantic policy, capability/gap analysis
Adapter writes: correlation/idempotency/outbox and external-reference records in LMS
```

Course Blueprint is a publishable LMS-owned projection; PAI may supply a blueprint proposal but cannot mutate LMS course state. Learning Result is an LMS-owned completion/progress projection; it is not a PAI evidence claim. PAI's source credentials remain distinct from LMS-issued certificates.

## Migration blockers

- There is no safe common migration history.
- PAI has privacy, document-retention, and audit constraints absent from the LMS schema.
- Existing target worktree has unrelated dirty/deleted files; migration automation must run from clean, pinned source snapshots.
- Any future shared reporting layer needs read models or events, not table coupling.
