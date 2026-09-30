# Instructional Design Policy v0.1

Identity: `pai_instructional_design@0.1`.

`passed` means deterministic structural checks have no `ERROR` or `BLOCKING`.
It is not approval or competency verification. The policy is versioned so a
snapshot retains the exact rules used for its report.

| Code | Severity | Trigger | False-positive / configuration note |
|---|---|---|---|
| `objective_not_observable` | ERROR | Performance begins with an obvious vague formulation such as “understand”, “know”, “learn”, or “become familiar with”. | Conservative prefix check only; human review handles deeper measurability judgment. Configurable prefix list. |
| `objective_without_assessment` | ERROR | No assessment references an objective. | Objective IDs are explicit; no semantic matching. |
| `orphan_assessment` | ERROR | Assessment has no objective reference. | A formative diagnostic still needs an objective reference in v0.1. |
| `orphan_module` | ERROR | Module has no objective reference. | Empty administrative modules are out of v0.1 scope. |
| `orphan_lesson` | ERROR | Lesson has no objective reference. | Does not judge lesson wording. |
| `objective_not_taught` | ERROR | No lesson references an objective. | Explicit IDs only; no inferred teaching coverage. |
| `insufficient_cognitive_demand` | ERROR for summative, WARNING for formative | Assessment Bloom demand is below an objective. | Ordered demand is `remember < understand < apply < analyze < evaluate < create`; exact equality is not required. Configurable. |
| `prerequisite_order_violation` | ERROR | An explicitly mapped confirmed prerequisite is taught after its dependent objective. | Requires `teaching_objective_id`; missing mapping is not guessed. |
| `prerequisite_cycle` | BLOCKING | Confirmed prerequisite graph contains a directed cycle. | The graph is not silently repaired. |
| `assessment_dependency_not_covered` | ERROR | Required assessment capability is not explicitly known, confirmed, or taught. | Coverage uses exact references; unknown is not absence. |
| `assessment_evidence_task_not_structurally_aligned` | ERROR | Assessment lacks required evidence or a task description. | Structural check only; adequacy needs human review. |

Unresolved `candidate` and `unknown` prerequisites are reported in
`unresolved_prerequisites` but are not promoted. A `model_proposed` prerequisite
must be `candidate` at schema validation time.
