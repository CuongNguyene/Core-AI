# ID-04C Practice-before-Assessment Coverage

ID-03C.3 recorded `instruction_assessment_alignment = 3.6/5`. ID-04C makes
practice traceability explicit without changing assessment capability semantics,
dependency normalization, objective ownership, workload arithmetic, or
prerequisite governance.

## Coverage unit and invariant

Each summative `required_capabilities` entry produces an
`AssessmentCoverageRequirement` keyed by the assessment, its objective refs,
capability name, and a source requirement reference. The deterministic trace
records instruction, guided-practice, independent-practice, and formative refs.

For `COVERED`, explicit prior instruction and at least one prior practice or
valid formative assessment are required. Instruction without practice is
`PARTIALLY_COVERED`; neither is `NOT_COVERED`; missing canonical objective refs
are `UNRESOLVED`. Matching uses objective/module/lesson/assessment references
only. No fuzzy text matching, embeddings, or semantic similarity is used.

Instruction is represented by explanation, demonstration, or worked-example
patterns. Guided and independent practice are distinct patterns. Formative
assessment counts only when its role is `FORMATIVE`; a summative assessment
cannot satisfy its own practice requirement or appear as a formative ref.

## Ordering and interactions

Lesson order comes from `CourseOutline.modules[].lesson_ids`, with deterministic
input-order fallback when that list is absent. Practice after the summative
assessment does not count and produces `practice_reference_after_summative`.
Self-reference produces `summative_used_as_practice`; role mismatches produce
`practice_reference_role_mismatch`.

Coverage focuses on `required_capabilities`, not dependency candidates. An
`ENTRY_PREREQUISITE` is not a course practice requirement; `IN_COURSE_SUPPORT`
may be used by planners but is not promoted into summative capability
requirements. Workload context remains authoritative for time arithmetic: extra
practice may coexist with `workload_time_budget_exceeded` and neither finding
suppresses the other.

## Planner prompt and compatibility

The active structured planner prompt is patch-versioned as `0.3.4`.
Historical prompt versions `0.3.1`, `0.3.2`, and `0.3.3` remain available for
replay. CoursePlanner and LessonPlanner receive explicit summative coverage
requirements alongside workload context. The deterministic gate computes the
coverage trace; it never trusts an LLM-proposed coverage status.

The deterministic cross-domain examples are under
`backend/test/results/instructional-design-id-04c-practice-coverage/` and use no
external model calls.

Practice coverage means the design provides an opportunity to prepare for the
assessed performance. It does not prove learner mastery, competency, or
successful completion.
