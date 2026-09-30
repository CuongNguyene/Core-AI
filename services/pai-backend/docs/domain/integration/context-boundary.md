# INTEGRATION-01A — Bounded Context Boundary

## LMS Context

The LMS owns the operational learning-delivery experience:

- account registration, authentication, JWT/refresh/logout and email verification;
- LMS user account role and operational user management;
- delivery Course, Module, Lesson, assets and publication visibility;
- Enrollment, assignment, Progress and completion state;
- delivery Quiz, Question, Answer and learner QuizAttempt scoring;
- course-completion Certificate and CertificateTemplate;
- notifications, dashboard/reporting and LMS frontend API contracts.

The LMS must not decide that a learner is competent merely because a course or quiz was completed.

## PAI Intelligence Context

PAI owns the semantic and evidence-based capability lifecycle:

- CV/JD document intake, safety/retention and extraction jobs;
- CandidateProfile, JD requirements, source locators and Evidence items;
- RoleCompetencyProfile, Skill/Capability identifiers and exact SemanticPolicy binding;
- preliminary matching, evidence allocation and CapabilityGapPortfolio;
- LearningObjective, prerequisite graph, CourseBlueprint, ModuleBlueprint and LessonBlueprint;
- AssessmentTemplate, rubric, artifact/evidence linkage, SME review and CompetencyDecision;
- CompetencyRecord transitions, competency credential policy and verification;
- ModelGateway, PrivacyGateway and intelligence audit events.

PAI must not own LMS enrollment, lesson progress, target course publication or learner account passwords.

## Shared Integration Context

Only stable contracts cross the boundary:

- `ActorReference`: LMS user ID plus trusted organization/tenant context once defined;
- `BlueprintProjection`: PAI blueprint ID/version, objective and provenance references consumed by LMS;
- `LearningResult`: LMS-owned completion/quiz outcome with source course/assessment references;
- `EvidenceReference`: opaque PAI evidence/credential references when a consuming workflow is authorized;
- correlation ID, schema version and policy/version metadata.

There is no shared database. Each context persists its own records and exchanges versioned messages or API payloads.

## Context map

```text
LMS User/Auth ───── ActorReference ─────> PAI authorization boundary
PAI Blueprint ───── BlueprintProjection ─> LMS delivery authoring
LMS LearningResult ─────────────────────> PAI evidence/learning input
PAI Competency/Credential reference ────> LMS display/verification link
```

The organization/tenant contract is intentionally unresolved. It is a prerequisite for production isolation and cannot be inferred from the current target `User` model.
