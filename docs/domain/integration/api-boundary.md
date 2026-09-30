# INTEGRATION-01A — API Boundary

The boundary is service-to-service and contract-based. Neither system reads the other system's database or imports its ORM models.

| Concept / flow | Direction | Request owner | Response/event owner | Source of truth | Boundary rule |
|---|---|---|---|---|---|
| Actor authentication | LMS → PAI | LMS | LMS identity contract | LMS | PAI accepts a trusted integration identity, never a client-supplied role or organization claim. |
| Actor authorization/delegation | PAI internal | PAI | PAI | PAI | Scoped SME delegation and competency permissions stay in PAI until an explicit cross-context authorization contract exists. |
| CV/JD upload and extraction | Client/LMS → PAI | PAI intake API | PAI | PAI | Do not route through target `/api/documents`; PAI owns raw document safety, retention and extraction state. |
| CandidateProfile/Evidence | PAI internal | PAI | PAI | PAI | Expose only authorized versioned projections or opaque references. |
| RoleCompetencyProfile and GapAnalysis | PAI internal | PAI | PAI | PAI | No target LMS CRUD endpoint should mutate these semantics. |
| CourseBlueprint | PAI → LMS | PAI | LMS projection acknowledgement | PAI for blueprint; LMS for delivery record | LMS stores source blueprint ID/version and cannot mutate source semantic meaning. |
| LearningObjective/prerequisite metadata | PAI → LMS | PAI | LMS projection | PAI | Delivery ordering may be enforced by LMS, but prerequisite meaning remains PAI-owned. |
| Delivery Course/Module/Lesson | LMS internal | LMS | LMS | LMS | PAI does not write target Prisma records directly. |
| AssessmentBlueprint | PAI → LMS | PAI | LMS draft Quiz/assessment projection | PAI for rubric/alignment; LMS for delivery quiz | Keep blueprint and quiz IDs distinct. |
| Enrollment/progress | LMS internal | LMS | LMS | LMS | PAI consumes events only when a policy requires learning evidence. |
| LearningResult | LMS → PAI | LMS | PAI acknowledgement/analysis | LMS for event facts | Receipt does not transition CompetencyRecord to `VERIFIED`. |
| Competency decision | PAI → LMS | PAI | PAI | PAI | LMS may display status/reference; it cannot approve, revoke or reinterpret it. |
| Course Certificate | LMS internal | LMS | LMS | LMS | Course certificate remains independent of PAI competency credential. |
| Competency Credential verification | PAI → LMS | PAI | PAI verification response | PAI | LMS may link/display valid/expired/revoked result, not persist an authoritative copy without a reference contract. |

## Boundary payload rules

- Every payload carries `schema_version`, stable IDs, source system and correlation ID.
- Cross-context IDs are references, not foreign keys.
- Blueprint projections are immutable by source version; a new source version creates a new projection decision.
- LMS learning outcomes are evidence inputs, not competency decisions.
- Raw CV/JD content, prompts, model traces and secrets do not cross into LMS operational APIs by default.
