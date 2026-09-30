# INTEGRATION-01B — Course Blueprint Contract

## Contract envelope

All PAI-to-LMS blueprint payloads are immutable source-version projections:

```json
{
  "schema_version": "v1",
  "correlation_id": "01J...",
  "source_system": "pai",
  "data": { "...": "CourseBlueprintContract" }
}
```

## CourseBlueprintContract v1

```json
{
  "blueprint_id": "bp_123",
  "version": "1.0.0",
  "title": "Radiographic Testing Fundamentals",
  "summary": "Delivery-facing overview",
  "estimated_duration_minutes": 360,
  "objectives": [
    {
      "objective_ref": "obj_01",
      "title": "Interpret an RT image",
      "sequence": 1
    }
  ],
  "modules": [
    {
      "module_ref": "mod_01",
      "title": "Image interpretation",
      "order": 1,
      "lessons": [
        {
          "lesson_ref": "lesson_01",
          "title": "Recognizing indications",
          "order": 1,
          "delivery_type": "TEXT",
          "estimated_duration_minutes": 45,
          "objective_refs": ["obj_01"],
          "content_reference": "delivery-content:pending"
        }
      ]
    }
  ],
  "assessment_blueprint_refs": [
    { "assessment_id": "asmt_01", "version": "1.0.0" }
  ],
  "projection_constraints": {
    "source_immutable": true,
    "requires_lms_draft": true
  }
}
```

Required fields: `blueprint_id`, `version`, `title`, `estimated_duration_minutes`, one or more objectives/modules/lessons, and the contract envelope fields. IDs are opaque references; they are not LMS primary keys and do not become foreign keys.

## AssessmentBlueprintContract v1

```json
{
  "assessment_id": "asmt_01",
  "version": "1.0.0",
  "assessment_type": "quiz|practical|case",
  "title": "Image interpretation check",
  "objective_refs": ["obj_01"],
  "competency_refs": ["competency:rt-image-interpretation"],
  "evidence_expectations": [
    { "evidence_type": "delivery_result", "required": true }
  ],
  "delivery_guidance": {
    "recommended_pass_score": 70,
    "recommended_max_attempts": 3
  }
}
```

This contract communicates alignment and evidence expectations. PAI retains rubric, risk classification, policy version, validity, reassessment rules, evidence IDs, and competency-decision eligibility. LMS may use `delivery_guidance` to create a quiz, but owns its questions, answers, attempts, score calculation, and final-quiz behavior.

## Projection acknowledgement v1

```json
{
  "schema_version": "v1",
  "blueprint_id": "bp_123",
  "blueprint_version": "1.0.0",
  "course_instance_id": "lms-course-uuid",
  "projection_status": "DRAFT_CREATED",
  "projected_at": "2026-08-17T09:00:00Z",
  "correlation_id": "01J..."
}
```

LMS owns `course_instance_id` and its draft/publish lifecycle. PAI owns `blueprint_id`/`blueprint_version`. A changed PAI blueprint is a new source version requiring an explicit new or updated projection decision; it must not silently mutate an LMS course.
