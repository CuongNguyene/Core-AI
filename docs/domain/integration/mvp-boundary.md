# INTEGRATION-01A — MVP Boundary

## What migrates or integrates for MVP planning

- The ownership map and versioned contract definitions.
- A future PAI-to-LMS `CourseBlueprint` projection limited to approved, source-versioned design metadata.
- Optional PAI-to-LMS `AssessmentBlueprint` projection into a draft delivery Quiz, with the PAI rubric and competency meaning retained separately.
- A future LMS-to-PAI `LearningResult` contract, if product scope requires learning outcomes as evidence.
- Opaque PAI competency/credential references for authorized LMS display.

No runtime code or database migration is part of INTEGRATION-01A.

## What stays in PAI

- CV/JD documents, extraction, CandidateProfile, Evidence and review workflow.
- RoleCompetencyProfile, Skill/Capability semantics, matching and GapAnalysis.
- SemanticPolicy/domain-pack governance and deterministic capability rules.
- LearningObjective, prerequisite meaning, instructional-design quality gates and blueprint persistence.
- Competency assessments, SME review, CompetencyRecord transitions and competency credentials.
- ModelGateway, PrivacyGateway, raw-document safety, retention and intelligence audit.

## What remains LMS-owned

- Login/authentication, user account, operational roles and target frontend.
- Published Course/Module/Lesson, uploads for delivery content and course visibility.
- Enrollment, assignment, lesson Progress, completion state and delivery reporting.
- Learner QuizAttempt scoring, delivery notifications and course-completion Certificates.

## Deferred decisions

- Organization/Tenant authority and whether the product is single-tenant or multi-tenant.
- Whether PAI remains a separate Python service or is later reimplemented in NestJS.
- Whether CV/JD upload is exposed through the LMS UI or a separate PAI UI.
- Exact shared contract versions and event transport.
- Any target persistence for evidence, competency or policy snapshots.
- Automatic linkage between learning outcomes and competency decisions.

## MVP guardrail

Course completion, progress, quiz pass and LMS certificate issuance must never be treated as `CompetencyRecord.status = VERIFIED`. The two lifecycles remain separate until a later, explicitly governed assessment/evidence workflow is designed.
