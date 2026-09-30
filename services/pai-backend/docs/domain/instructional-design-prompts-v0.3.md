# Instructional-design structured prompts v0.3

## Why this version exists

v0.3 is an evidence-driven iteration after ID-02 Smoke-2 and the six-packet
blinded human review. It targets upstream causes observed in structured
outputs: cross-stage reference drift, assessment scope creep, prerequisite
inflation, missing instructional practice, and unrealistic time compression.
It does not relax the deterministic quality gate and is not evidence of
pedagogical effectiveness.

The one-shot baseline remains
`instructional_design_one_shot_baseline@0.1` and is not tuned for this
iteration.

## Stage ownership

| Stage | Owns | Must not do |
|---|---|---|
| ObjectiveDesigner | observable objective formulation | invent capabilities, levels, or redundant micro-objectives |
| AssessmentDesigner | claim/evidence/task design for supplied objectives | introduce unscoped assessed capabilities; use dependency candidates instead |
| PrerequisiteProposer | minimal candidate prerequisite proposals | confirm model proposals or label merely helpful background as required |
| CoursePlanner | objective-linked module grouping and order | invent objective IDs or predict final lesson IDs |
| LessonPlanner | activities, practice, and supplied module/objective/assessment references | rewrite upstream objectives, assessments, or prerequisites |
| Orchestration | canonical IDs, module/lesson attachment, exact deduplication, final graph | fuzzy repair or hidden mutation |
| Quality gate | deterministic validation/reporting | repair model output or replace human judgement |

## Contract changes from v0.2

- Structured prompt/schema provenance is `0.3`; the historical `0.2` registry
  remains available for compatibility and Smoke-2 replay.
- Assessment output can carry typed `dependency_candidates`; candidates are
  not required evidence and are not automatically promoted to prerequisites.
- Prerequisites carry `classification` and `required_for_refs`. A v0.3
  model-proposed required prerequisite must remain `candidate`/`model_proposed`
  and include a specific rationale describing what supplied objective or
  assessment would fail without it.
- CoursePlanner leaves `module.lesson_ids` empty. Orchestration derives those
  edges after LessonPlanner returns lessons and final validation checks both
  directions.
- Unknown objective/module/prerequisite/assessment references fail the v0.3
  stage explicitly. There is no string guessing, fuzzy matching, or synthetic
  replacement ID.
- Course and lesson payloads include explicit allow-lists for each reference
  kind. `prerequisite_refs` must contain prerequisite IDs only; objective IDs
  and assessment IDs cannot be used as substitutes. Module-to-lesson edges are
  still application-owned and are derived after lesson generation.

## Prompt behavior changes

Objective prompts now require the smallest coherent set of observable,
assessable objectives. Assessment prompts prohibit professional-behavior
scope creep and separate optional extensions/dependency candidates from
required evidence. Prerequisite prompts define minimality and reject vague
"helpful" rationales. Course prompts treat time as a real constraint and
avoid lesson-ID generation. Lesson prompts require practice before summative
evidence for applied/higher-order objectives where instruction is needed.

Integrated-practice quality remains a prompt/reviewer criterion in v0.3. It is
not promoted to a new deterministic finding until a low-false-positive rule is
demonstrated.

## AssessmentDesigner semantic boundaries in v0.3.1

The `instructional_assessment_design@0.3.1` prompt keeps the existing output
schema and deterministic validation contract, while making ownership explicit:

- `objective_ids` may contain only IDs supplied in the input allow-list. The
  designer must not invent, rename, or borrow an objective from another module
  or stage. Missing objectives remain unresolved according to the existing
  contract; they are never synthesized or fuzzy-matched.
- `required_capabilities` describe capabilities directly demonstrated by the
  assessment and grounded in the objective performance.
- `dependency_candidates` describe supporting knowledge or skills needed before
  that performance. They remain `candidate`/`model_proposed` and are never
  promoted automatically to required evidence.
- An assessment may not introduce capabilities beyond its objective. The rule
  is domain-neutral and does not add IT-specific assumptions.

Version `0.3` remains available unchanged for historical Smoke-3 replay;
`0.3.1` is the boundary-hardened AssessmentDesigner prompt used by Smoke-4.
