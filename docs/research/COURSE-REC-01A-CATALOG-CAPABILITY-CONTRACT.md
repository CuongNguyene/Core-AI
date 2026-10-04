# COURSE-REC-01A — Catalog + Course Capability Profile Contract

## Scope and boundary

This milestone defines course supply only. It does not decide what a learner
should learn, rank courses, score fit, call a model, or expose a recommendation
API. COURSE-REC-01B will consume the normalized candidate contract defined here.

```text
Frappe LMS Course
    -> stable internal course reference
    -> CourseCapabilityProfile (Core-AI)
ExternalCourse (provider facts)
    -> provider adapter / manual semantic mapping
    -> CourseCapabilityProfile
    -> NormalizedCourseCandidate
    -> COURSE-REC-01B
```

Frappe LMS remains the owner of Course, Chapter, Lesson, publication, access,
enrollment, progress, and delivery lifecycle. Core-AI owns the semantic course
profile and normalized external-course representation. No LMS DocType field is
added for inferred capabilities, target levels, prerequisites, or scores.

## Existing inventory

Core-AI had no canonical `CourseCapabilityProfile`, `ExternalCourse`, or course
provider contract. Existing `learning` and `instructional_design` prerequisite
objects describe instructional blueprints, not catalog identity, so they are
not reused as course-catalog objects. Existing role requirement semantics keep
`target_level` nullable and preserve semantic-policy governance on role
profiles; course profiles do not invent a numeric level system.

The canonical LMS `LMS Course` DocType exposes these projection candidates:

| LMS field | Meaning | Projection | Decision |
|---|---|---|---|
| `name` | Frappe stable document name, e.g. `CRS-2026-00004` | `frappe_lms:<name>` | DIRECT identity |
| `title` | Course title | `title_snapshot` | DIRECT |
| `short_introduction` | Short learner-facing summary | `description_snapshot` | TRANSFORM snapshot |
| `description` | LMS course description | `description_snapshot` | TRANSFORM snapshot |
| `published` | LMS publication state | `availability` | TRANSFORM: `1` → `available`, `0` → `unavailable` |
| `duration` | Estimated minutes | `duration_minutes` | DIRECT |
| `category` | LMS category reference | metadata only | NOT_USED for capability semantics |
| `instructors` | LMS instructor rows | provenance/ownership context | NOT_USED as capability evidence |
| `published_on` | Publication date | source metadata | OPTIONAL |
| `chapters`, `lessons` | Delivery structure/counts | delivery metadata | NOT_USED for capability inference |
| route/URL | LMS navigation | external display reference | OPTIONAL, not identity |

The projection must not infer capability, level, or prerequisite from title,
description, chapter names, lesson text, duration, or instructor identity.

## Internal course identity

```json
{
  "source_type": "internal",
  "source_system": "frappe_lms",
  "course_ref": "frappe_lms:CRS-2026-00004"
}
```

`LMS Course.name` is the stable source identifier. Course title is not an
identity. The normalized reference is unique within `(source_system,
course_ref)` and is never confused with a Core-AI profile ID.

## External course identity

External provider facts use an extensible provider reference rather than a
hard-coded provider enum:

```json
{
  "source_type": "external",
  "provider_ref": "mock_provider",
  "provider_course_id": "external-software-001",
  "course_ref": "mock_provider:external-software-001"
}
```

The future adapter must namespace provider IDs by `provider_ref`; a provider
course ID alone is not globally unique. No live provider, OAuth, API key, or
network client is part of this milestone.

## CourseCapabilityProfile

| Field | Type | Required | Nullable | Semantics |
|---|---|---:|---:|---|
| `id` | string | yes | no | Core profile identity |
| `version` | positive integer | yes | no | Immutable semantic profile version |
| `course_ref` | string | yes | no | Stable internal/external source reference |
| `source_type` | `internal \| external` | yes | no | Supply origin |
| `source_system` | string | yes | no | Source namespace, e.g. `frappe_lms` |
| `provider_ref` | string | external only | yes | External provider namespace |
| `provider_course_id` | string | external only | yes | Provider-owned course identity |
| `title_snapshot` | string | yes | no | Source title snapshot |
| `description_snapshot` | string | no | yes | Source description snapshot |
| `capabilities` | list of `CourseCapability` | yes | no | Explicit course coverage claims |
| `prerequisites` | list of `CoursePrerequisite` | no | no | Course-local entry conditions |
| `target_level` | string | no | yes | Nullable source/governed level; no inference |
| `duration_minutes` | non-negative integer | no | yes | Estimated learning time |
| `delivery_mode` | string | no | yes | Source delivery metadata |
| `language` | string | no | yes | Course language metadata |
| `availability` | enum | yes | no | `available`, `unavailable`, or `unknown` |
| `status` | enum | yes | no | `draft`, `active`, or `deprecated` |
| `provenance` | non-empty list | yes | no | Source/manual/provider grounding |

Profiles reject duplicate `capability_ref` entries. External profiles require
both provider fields; internal profiles reject provider identity. Unknown
levels remain `null`.

## Capability coverage

`CourseCapability` contains:

```json
{
  "capability_ref": "capability:feedback",
  "coverage_type": "direct",
  "target_level": null,
  "provenance": [
    {
      "kind": "manual_mapping",
      "source_ref": "fixture:course-001",
      "source_field": "capabilities",
      "method": "fixture_authoring"
    }
  ]
}
```

Capability identity is an opaque canonical reference. This milestone does not
create a new skill taxonomy. Coverage is `direct` or `supporting`. Mapping
provenance is mandatory and may be `source_fact`, `manual_mapping`, or
`provider_metadata`; no runtime AI extraction is enabled.

## Target level

The course contract uses nullable string `target_level` to preserve existing
Core semantics. There is no new numeric scale. `Senior`, years of experience,
course duration, title wording, and keyword frequency must not be converted to
a level. Normalization is deferred until an approved policy exists.

## Prerequisites

Prerequisites are local to a course and have a small extensible shape:

```json
{
  "kind": "capability",
  "ref": "capability:active-listening",
  "minimum_level": null,
  "provenance": []
}
```

Supported V1 kinds are `capability`, `level`, `course`, and
`provider_condition`. This is not a generalized capability progression graph.
An empty prerequisite list is valid and means no declared entry condition.

## Metadata and availability

| Field | V1 priority | Internal source | External source |
|---|---|---|---|
| title | REQUIRED_V1 | LMS `title` | provider metadata |
| description | OPTIONAL_V1 | LMS `description` / `short_introduction` | provider metadata |
| duration | OPTIONAL_V1 | LMS `duration` | provider metadata |
| delivery mode | OPTIONAL_V1 | future managed LMS metadata | provider metadata |
| language | OPTIONAL_V1 | future managed LMS metadata | provider metadata |
| availability | REQUIRED_V1 | LMS `published` | provider status |
| provider/reference | REQUIRED_V1 | `frappe_lms` + Course.name | provider namespace + ID |
| URL | OPTIONAL_V1 | LMS route | provider URL |

Internal publication is canonical: published courses are `available`; drafts
are `unavailable`. External availability is normalized as available,
unavailable, or unknown. COURSE-REC-01B should consume only active profiles whose
normalized availability is eligible under its future policy.

## Provenance

`CourseProvenance` records `kind`, `source_ref`, optional source field/locator,
optional evidence text, and method. Manual fixtures use `manual_mapping` or
`source_fact`; external fixtures use `provider_metadata`. `AI_DERIVED` is not
used by this milestone and no model call or extraction runtime was added.

## External provider contract

`ExternalCourse` contains provider-owned facts only. The minimal mock interface
is:

```python
class MockExternalProvider:
    def list_courses() -> tuple[ExternalCourse, ...]: ...
    def get_course(provider_course_id: str) -> ExternalCourse: ...
```

The mock is deterministic and in-memory. It makes zero network or model calls.

## Normalized recommendation input

COURSE-REC-01B consumes `NormalizedCourseCandidate`:

```json
{
  "course_ref": "frappe_lms:CRS-2026-00004",
  "source_type": "internal",
  "source_system": "frappe_lms",
  "provider_ref": null,
  "provider_course_id": null,
  "title": "Feedback Fundamentals",
  "description": "...",
  "capabilities": [],
  "prerequisites": [],
  "target_level": null,
  "duration_minutes": 90,
  "delivery_mode": "self_paced",
  "language": "en",
  "availability": "available",
  "provenance": []
}
```

The future engine does not branch on internal versus external semantics. Only
catalog retrieval/provider adaptation differs.

## Versioning and lifecycle

`CourseCapabilityProfile` has `id` and positive integer `version`. A later
persistence layer must create a new version when source metadata or capability
mapping changes rather than mutating an accepted semantic snapshot. Minimal
states are `DRAFT`, `ACTIVE`, and `DEPRECATED`; only `ACTIVE` is eligible for
future recommendation input. No persistence or migration is added here.

## Fixture catalog

The deterministic fixtures contain 24 internal and 24 external courses across
software/AI, sales, finance/accounting, and HR/communication. They include
direct and supporting coverage, nullable levels, prerequisites, short/long
durations, self-paced/instructor-led delivery, and unavailable/unknown states.
All IDs and descriptions are synthetic. No production course data is used.

## Deliberate deferrals

- recommendation fit, ranking, scoring, top-k, and explainability output;
- LearningNeed/LearningPath integration;
- live LMS synchronization or capability authoring UI;
- external provider HTTP clients, credentials, and OAuth;
- persistence/migrations for course profiles;
- AI capability extraction, embeddings, and vector search;
- changes to LMS Course, Chapter, or Lesson schemas.
