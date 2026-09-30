# INTEGRATION-01A — Migration Impact

## Port unchanged

No executable domain module is safe to move unchanged across Python/FastAPI and TypeScript/NestJS. The only unchanged candidates are explanatory concepts and stable identifier/version conventions after they are approved as contracts.

## Adapter required

- `CourseBlueprint → Delivery Course` projection.
- `ModuleBlueprint/LessonBlueprint → Delivery Module/Lesson` projection.
- `AssessmentBlueprint → LMS draft Quiz` projection while retaining rubric/evidence semantics in PAI.
- `ActorReference` and future organization/tenant context.
- `LearningResult` from LMS to PAI.
- PAI competency/credential verification references for LMS display.
- Cross-language JSON schemas and golden fixtures for the above contracts.

## Keep separate

- PAI CV/JD extraction, Evidence graph, CandidateProfile, RoleCompetencyProfile, CapabilityGapPortfolio and SemanticPolicy.
- PAI ModelGateway/PrivacyGateway, extraction worker and source persistence.
- PAI AssessmentTemplate, SME review, CompetencyDecision and competency credential policy.
- LMS authentication, operational User, Course/Module/Lesson, Enrollment, Progress, Quiz/Attempt, Certificate and notifications.

## Not MVP

- Full CV/JD authoring and human-review UI inside LMS.
- Target-side competency ontology, role profile authoring and multi-tenant redesign before product decisions.
- Automatic competency verification from LMS completion or quiz score.
- Direct merging of Alembic and Prisma migrations or database tables.
- Research smoke runners, blinded reviews, raw model traces, private mappings and generated experiment outputs.

## Consequence

Integration should begin with a contract/projection design and an explicit service boundary. It should not begin by moving PAI ORM models, FastAPI routes or instructional-design research artifacts into the target repository.
