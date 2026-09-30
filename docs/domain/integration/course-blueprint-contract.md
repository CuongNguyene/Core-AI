# DEPRECATED

Status: `DEPRECATED`

This document is preserved for historical reference. Do not implement from
this document. Use the canonical v1 contract set:

- `docs/domain/integration/01b-api-contract-design.md`
- `docs/domain/integration/01b-course-blueprint-contract.md`
- `docs/domain/integration/01b-learning-result-contract.md`
- `docs/domain/integration/01b-identity-contract.md`

Canonical version: `v1`

---

# Course Blueprint contract (`INTEGRATION-01B`)

`CourseBlueprint` is the integration intermediate representation between an
approved PAI instructional-design graph and LMS authoring. It is not a live
course and does not assert learner capability.

## Shape

```json
{
  "blueprint_id": "bp-...",
  "status": "DRAFT|IN_REVIEW|APPROVED",
  "source": {
    "brief_id": "...",
    "snapshot_id": "...",
    "policy_id": "...",
    "policy_version": "...",
    "prompt_versions": {}
  },
  "objectives": [{
    "objective_id": "...",
    "statement": "...",
    "observable_behavior": "..."
  }],
  "modules": [{
    "module_id": "...",
    "objective_refs": ["..."],
    "lessons": [{
      "lesson_id": "...",
      "objective_refs": ["..."],
      "instructional_pattern": "...",
      "assessment_refs": ["..."]
    }]
  }],
  "assessments": [{
    "assessment_id": "...",
    "role": "formative|summative",
    "objective_refs": ["..."],
    "required_capability_refs": ["..."]
  }]
}
```

## Invariants

- Objective IDs are source-owned and immutable.
- `lesson.objective_refs ⊆ module.objective_refs ⊆ blueprint.objectives`.
- Formative and summative assessment references remain distinct.
- Prerequisite dispositions remain candidate/model-proposed and retain source
  dependency refs.
- Workload and practice-coverage findings are carried as findings, not hidden
  by projection.
- Unknown references fail closed; adapters never create replacement objectives.

## LMS projection

The adapter may create LMS Course/Module/Lesson drafts and attach a provenance
record. It must not copy source evidence claims, raw documents, capability
verification state, or audit prompts into LMS content tables.
