# Instructional Design Core v0.1

## Purpose and scope

Instructional Design Core is a research-only module for testing whether a staged
pedagogical design process aligns objectives, assessment, prerequisites, course
structure, and lesson specifications better than one-shot course generation.

It consumes an explicitly authored `ResearchLearningBrief`; it does not accept
or create a production `RoleCompetencyProfile`, learning path, competency
decision, or verified learner state. `learner_state.unknown` means unknown, not
a learner deficiency.

The implemented flow is:

```text
ResearchLearningBrief
→ LearningObjectiveSpec
→ AssessmentSpec
→ PrerequisiteSpec
→ CourseOutline
→ LessonSpec
→ InstructionalDesignQualityReport
```

The `InstructionalDesignResearchSnapshot` serializes the typed artifacts and
their provenance. It is not persisted as a production learning path in v0.1.

## Architecture

The module separates model proposal contracts from trusted validation:

```text
typed staged proposal
→ typed research snapshot assembly
→ deterministic quality gate
```

Five independent JSON-only proposal contracts are registered at version `0.1`:

- `instructional_objective_design`
- `instructional_assessment_design`
- `instructional_prerequisite_proposal`
- `instructional_course_planning`
- `instructional_lesson_planning`

No v0.1 component invokes a provider. If a future caller uses these contracts
through `ModelGateway`, it must preserve prompt/schema/model provenance and let
the deterministic quality gate—not the model—determine findings.

## Pedagogical framing

The sequence follows the external Backward Design / Understanding by Design
idea of desired performance → acceptable evidence → learning plan. Revised
Bloom metadata stores cognitive process and knowledge dimension separately;
it never derives a Bloom level from role seniority. The assessment structure
uses an Evidence-Centered Design-style chain:

```text
Learning Objective → Capability Claim → Required Evidence → Assessment Task
```

These are external instructional-design frameworks, not PAI inventions. PAI's
architecture decision is to encode their traceability as typed, versioned
research artifacts before content rendering.

## Prerequisites and sequencing

Prerequisites carry a status and a basis. `model_proposed` is valid only with
`status=candidate`; it cannot become confirmed automatically. Candidate and
unknown prerequisites remain in the quality report as unresolved.

Confirmed prerequisite dependencies use DAG semantics. A cycle is `BLOCKING`.
The v0.1 gate checks ordering only when an explicit `teaching_objective_id`
maps a prerequisite to a lesson; it makes no inferred semantic link. The
initial instructional rationale is conservative and policy-driven, not a claim
that one universal teaching order is proven.

## Quality report meaning

The gate checks objective observability, objective/assessment/lesson/module
traceability, cognitive demand, prerequisite graph/order, and explicit
assessment dependency coverage. `passed=true` means no deterministic `ERROR`
or `BLOCKING` finding under policy `pai_instructional_design@0.1`.

```text
quality_report.passed ≠ SME approved
quality_report.passed ≠ learner competent
quality_report.passed ≠ production course approved
```

Warnings leave a research artifact inspectable. They do not resolve
prerequisites or approve an instructional design.

## Boundary with future content generation

`LessonSpec` contains a goal, learner activity, pattern, objective references,
and formative assessment references. It deliberately contains no factual
lesson text, image, audio, video, citations, question bank, or learning object
body. Future content renderers must consume a reviewed pedagogical
specification rather than redesign pedagogy themselves.
