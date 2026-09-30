# Instructional Design Prompts v0.2

All structured prompts are JSON-only, research-only contracts at version `0.2`.
They receive typed upstream artifacts and preserve supplied IDs. No prompt can
approve its own output or require private reasoning traces.

| Designer | Input | Output | Boundary |
|---|---|---|---|
| `ObjectiveDesigner` | Brief | Objectives | Observable performance only; no assessments, course, lessons, role level, or factual content. |
| `AssessmentDesigner` | Brief + objectives | Assessments | Preserve objective IDs; claim → evidence → task; no objective redesign, question bank, or competency claim. |
| `PrerequisiteProposer` | Brief + objectives + assessments | Prerequisites | Model-only prerequisite is `basis=model_proposed`, `status=candidate`; rationale is not proof. |
| `CoursePlanner` | Brief + objectives + assessments + prerequisites | Course outline | Objective/prerequisite traceability and conservative rationale; no orphan module or lesson content. |
| `LessonPlanner` | Earlier artifacts + course | Lessons | Preserve module/objective/assessment links; no factual prose, media, citations, or question bank. |

The baseline is `instructional_design_one_shot_baseline@0.1`. It receives the
same brief and returns the canonical aggregate, but is not told to follow the
structured sequence. It cannot generate factual content, learner-deficiency
claims, competency verification, or approval.

On a structured failure, orchestration records stage, failure class, validation
error, retry count, and safe partial typed artifacts; it stops before later
stages and creates no invisible fallback.
