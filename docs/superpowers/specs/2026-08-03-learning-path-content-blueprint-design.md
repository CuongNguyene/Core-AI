# PR-007 Learning Path & Content Blueprint Design

## Goal

Tạo learning path và course blueprint có version, provenance và prerequisite
graph từ verified competency, target competency profile, approved preliminary
gaps và mục tiêu phát triển; không tạo competency decision hay credential.

## Scope

### Inputs

`LearningPathRequest` chỉ nhận references và mục tiêu:

- `subject_id` (phải trùng actor trong development MVP);
- `target_profile_id` và `target_profile_version` của `RoleCompetencyProfile`
  `ACTIVE`;
- `preliminary_match_id` của match đã được review;
- danh sách `verified_competency_record_id` có status `VERIFIED`, cùng subject/
  organization, còn validity;
- danh sách `approved_gap_id` trỏ tới preliminary match `REVIEWED`, đúng subject,
  target role profile, approval state và confidence threshold;
- `development_goal` đã normalize, không chứa raw CV/JD;
- `target_completion_date` trong tương lai;
- `correlation_id`.

Request không nhận competency level, evidence payload, raw document, role,
organization authority hoặc generated content body từ client.

### Outputs

`LearningPath` trả về:

- stable ID, immutable version và lifecycle status;
- subject/organization;
- target profile ID/version;
- verified competency references và approved gap references;
- learning objectives;
- prerequisite graph;
- course blueprints, modules, lessons và learning object metadata;
- assessment template/rubric references;
- generator/policy/rule versions;
- correlation ID và `human_review_required=true` cho MVP metadata review.

Không có overall competency score, verified transition, credential hoặc raw
content body.

## Domain model

- `LearningObjective`: objective ID, competency ID, current verified level (nếu
  có), target level, measurable outcome, gap reference và sequence.
- `PrerequisiteNode`: stable node ID, learning object/module reference và
  competency/level metadata.
- `PrerequisiteEdge`: `from_node_id`, `to_node_id`, reason reference; graph
  validator bảo đảm DAG.
- `LearningPath`: subject/organization, target snapshot, approved input
  snapshots, objective list, graph, blueprint list, status/version, audit
  metadata.
- `CourseBlueprint`: blueprint ID/version, title, description reference,
  objective IDs, ordered module IDs và provenance status.
- `Module`: module ID/version, title, objective IDs, ordered lesson IDs,
  prerequisite node IDs.
- `Lesson`: lesson ID/version, title, objective IDs, ordered learning object
  metadata IDs.
- `LearningObjectMetadata`: object ID/version, type, title, estimated duration,
  competency ID, target level, assessment reference, approved source reference,
  provenance status. Không có body generated trong PR-007.

All IDs are stable within a versioned aggregate. A changed objective, graph,
blueprint or learning object creates a new aggregate version.

## Eligibility and policy

Application service performs all checks before generation:

1. Resolve actor through development identity adapter.
2. Require actor subject equality and one active organization.
3. Resolve target profile and require exact requested version plus `ACTIVE`.
4. Resolve every verified record and require `VERIFIED`, same subject/org and
   `valid_until` after the target date.
5. Resolve every gap approval and require `REVIEWED`, approved, exact match and
   confidence at or above requirement threshold.
6. Reject superseded/stale profile or match versions.
7. Normalize goal/date and reject empty, past or inconsistent dates.
8. Generate metadata through `ContentBlueprintGenerator`.
9. Validate prerequisite DAG, links and assessment references.
10. Persist the immutable snapshot and safe audit event in one transaction.

## Interfaces

```python
class ContentBlueprintGenerator(Protocol):
    async def generate(
        self, request: ContentGenerationRequest
    ) -> GeneratedBlueprint: ...
```

`ContentGenerationRequest` contains only normalized objectives, approved gap
summaries, target competency IDs/levels, deadline and generator policy/version.
`FakeContentBlueprintGenerator` returns deterministic metadata fixtures. It must
never access document source, ModelGateway, filesystem raw documents or client
prompt.

## API

- `POST /learning-paths`: validate eligible inputs and create a versioned path.
- `GET /learning-paths/{path_id}`: return the immutable current snapshot to the
  subject; future scoped authorizations may add delegated readers.
- `POST /learning-paths/{path_id}/supersede`: create a new version from a new
  eligible input snapshot; no in-place mutation.

Errors use ADR-0003 safe envelope and include stable codes for not-verified,
target-not-active, gap-not-approved, stale-input, graph-invalid and
learning-path-access-denied.

## Persistence and audit

SQLAlchemy repositories are runtime adapters; in-memory repositories are for unit
and adapter tests. Recommended tables:

- `learning_paths`;
- `learning_objectives`;
- `course_blueprints`;
- `learning_modules`;
- `learning_lessons`;
- `learning_object_metadata`;
- `learning_prerequisite_edges`;
- `learning_competency_links`;
- `learning_gap_approvals`;
- `learning_audit_events`.

Constraints include unique aggregate/version keys, one active/current version
per path, foreign keys for all links, unique prerequisite edge, and indexes for
subject, organization, target profile and source match IDs. Audit is append-only;
failed audit insert rolls back the path snapshot.

## Security and data handling

- CV/JD and extraction payload remain upstream untrusted data and are never
  passed to the generator.
- No prompt injection from documents can control system instructions or tools.
- Audit stores identifiers, versions, policy and reason codes only.
- Completion is explicitly outside this module and cannot mutate competency.
- No external provider is configured; fake provider is test-only.

## Test strategy

- Schema validation rejects inline/raw inputs and invalid dates.
- Eligibility tests cover unverified, expired, superseded, wrong subject/org,
  inactive target, unapproved/low-confidence gap and stale versions.
- DAG tests cover valid ordering, cycle, self-edge, duplicate and unknown node.
- Provenance tests ensure every learning object links to approved source,
  competency, level and assessment metadata.
- Fake generator tests are deterministic and prove no raw document/prompt is
  passed.
- API tests cover create/get/access/error contracts.
- Persistence tests cover immutable versions, transaction rollback on audit
  failure and supersession.
- Golden harness reruns the same eligible input and asserts byte-equivalent
  normalized blueprint metadata.

## Explicit non-goals

- No full LMS, enrollment, progress tracking or completion engine.
- No real content generation, external AI, publishing or recommendation ranking.
- No credential issuance or automatic competency updates.
- No new microservice or queue provider; keep the modular monolith boundary.
