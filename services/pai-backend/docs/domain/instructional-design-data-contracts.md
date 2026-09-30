# Instructional Design Data Contracts

All contracts in `app.instructional_design.schemas` are Pydantic, frozen,
extra-forbid, and research-only. They are serializable research artifacts, not
ORM models or production API payloads.

| Contract | Meaning and provenance | Authoritativeness and downstream use |
|---|---|---|
| `ResearchLearningBrief` | Controlled input with `research_fixture` provenance, capability context, known/unknown learner state, desired performances, and constraints. | Research input only. Unknown learner state does not assert a deficiency. |
| `LearningObjectiveSpec` | Observable target performance plus Bloom cognitive process, knowledge dimension, criteria, prerequisites, and capability references. | May be researcher-authored or model-proposed/provisional. Used for traceability checks. |
| `AssessmentSpec` | Claim, objective IDs, evidence criteria, task, cognitive demand, optional scoring metadata, and explicit dependencies. | Design specification only; never creates a verified competency. |
| `PrerequisiteSpec` | Capability prerequisite with status, basis, rationale, dependency edges, and optional explicit teaching-objective mapping. | `model_proposed` requires `candidate`; unresolved entries remain visible. |
| `CourseOutline` | Objective-linked modules, prerequisite references, duration, and sequencing rationale. | Research course structure; no production path/publishing state. |
| `LessonSpec` | Module/objective/prerequisite references, goal, instructional pattern, learner activity, and formative assessment references. | Boundary for a future renderer; contains no factual lesson content. |
| `InstructionalDesignQualityReport` | Deterministic policy findings, coverage rates, unresolved prerequisites, and policy ID/version. | Structural quality signal only, not SME approval or competency evidence. |
| `InstructionalDesignResearchSnapshot` | Immutable aggregate of a brief, all artifacts, report, and generation provenance. | JSON research output only in v0.1. |

`ArtifactProvenance` distinguishes researcher-authored from model-proposed
artifacts. Model-proposed artifacts must be marked `provisional=true`.
`GenerationProvenance` records the research brief ID, policy ID/version,
prompt/schema versions, provider/model/revision metadata, and generation time.

The five staged proposal outputs are versioned `0.1` ModelGateway schema and
prompt contracts. They preserve upstream IDs and use JSON-only research context;
they do not call a model by themselves.
