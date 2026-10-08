# PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-EVAL-00 Design

## Goal

Create a frozen, provider-blind synthetic corpus and conformance suite for
decomposing the exact HRM-to-PAI target-job source into atomic structured
statements. This is evaluation/research data only; it does not implement
extraction or change production behavior.

## Confirmed Repository Context

- Repository: Core-AI, independently maintained from LMS.
- Expected branch: `feat/deterministic-ai-course-planning-workspace`.
- The current external source model is `LearningTargetJobSource` nested at
  `EmployeeLearningProjectionV1.target_job_source` with fields
  `source_application_ref`, `job_description_html`, `job_requirements_html`,
  and `job_posting_url`.
- The source object and its fields are optional/nullable in the production DTO.
  Synthetic cases will include the exact four field names and use synthetic
  values; no additional field will be added to the source object.
- ADR 0022 keeps responsibility semantics separate from candidate-evaluable
  requirement dimensions. The corpus's `capability_relevance` axis is
  evaluation-only semantic annotation; it does not create a criterion,
  capability mapping, score, or gap and does not alter ADR 0022 behavior.
- The checkout already contains unrelated and candidate-semantic uncommitted
  work. New files will be confined to the dedicated job-semantics eval path,
  its focused tests, and its research report.

## Scope

### In scope

- Normative statement-type and capability-relevance taxonomies.
- Atomicity, splitting/keeping, HTML extraction, whitespace normalization,
  source-order, and provenance rules.
- Forty original synthetic job-posting cases, targeting 240–320 gold atomic
  statements across six domains and the specified language mix.
- A separate 30–40 case taxonomy/decomposition conformance suite, never reused
  as provider-evaluation data.
- Two documented authoring review passes, consistency matrices, deterministic
  validation/fingerprint tooling, and a freeze manifest.
- Focused tests for schema/data invariants, HTML/source provenance, provider
  leakage, hash behavior, and manifest consistency.

### Explicitly out of scope

- Jev, LLM, ModelGateway, embedding, or other provider calls; prompts or
  provider comparison.
- Production extraction or semantic interpretation.
- Canonical capability IDs/mapping, levels/proficiency, RoleCompetencyProfile,
  candidate-role gap analysis, or competency decisions.
- Raw JD upload/fetch/scraping/OCR; the URL is synthetic provenance only and
  must never be fetched or parsed.
- API, database, migration, LMS, ATS, or HRM changes.
- Commit or push.

## Data and Taxonomy Design

The source object contains exactly these keys (the production DTO permits the
object itself and each field to be omitted or null):

```json
{
  "source_application_ref": "synthetic reference",
  "job_description_html": "synthetic HTML",
  "job_requirements_html": "synthetic HTML",
  "job_posting_url": "https://example.invalid/..."
}
```

`source_application_ref` identifies only a synthetic source/application. The
posting case also carries the contract's case-level `source_application_ref`
metadata; it must equal the nested source value and is not an additional field
inside `target_job_source`. Nullable, omitted, empty-string, and whitespace-only
values are distinct source states; the contract and projection must preserve
them without silently converting one to another. The conformance suite covers
the `target_job_source` object omitted/null/empty-object forms and, for each of
the four fields, omitted/null/empty/whitespace-only values. Main gold postings
use nonempty source content in at least one HTML field; a null/empty companion
field remains legal.
Description/requirements field location is provenance only, never a label
shortcut. No actual company, employee, applicant, ATS/HRM record, CV, or job
posting is used.

Each gold statement has a stable ID, source field, exact source text span,
normalized statement, source order, statement type, capability relevance,
optional exact capability-signal span, optional decomposition group, the
`synthetic_spec` label source, and `REVIEWED` status. No canonical capability
reference or level is part of this contract.

Statement types are `RESPONSIBILITY`, `EXPERIENCE_REQUIREMENT`,
`EDUCATION_REQUIREMENT`, `QUALIFICATION_REQUIREMENT`,
`BEHAVIORAL_REQUIREMENT`, and `OTHER`. Capability relevance is a separate axis:
`CAPABILITY_BEARING`, `NON_CAPABILITY`, or `UNCLEAR`. `CAPABILITY_BEARING` means
only that explicit behavior/skill/knowledge/tool semantics may merit future
mapping review; it is not a mapped or validated capability and does not make a
responsibility eligible for production scoring by itself. `UNCLEAR` means the
text is too vague to identify meaningful capability semantics, not that a
future ontology match is difficult. Education and credentials remain
eligibility/qualification semantics and do not imply a capability.

No `requirement_strength` field will be added in v1. Required/preferred wording
remains in source/normalized text and is covered by evaluation-only boundary
tags, avoiding an additional contract axis before a consumer needs it.

An atomic statement is one independently classifiable semantic requirement or
responsibility. Split independently meaningful coordinated behaviors and
different semantic types; keep coordinated verbs when they form one bounded,
coherent behavior. Do not split mechanically on “and”. A mixed experience plus
education clause becomes two statements. Statements retain source field, exact
source span, and deterministic source order; semantically duplicated text in
different fields remains two provenance records.

`source_text` is the exact contiguous span from a deterministic text view of
the selected HTML field, not raw markup and not a paraphrase. To construct that
view: decode named/numeric HTML character references once; treat inline tags as
transparent (they add no characters); insert a newline at `<br>`, `<p>`,
`<div>`, `<h1>`–`<h6>`, and `<li>` start/end boundaries in DOM order; keep
nested list items in DOM order; map non-breaking spaces to ordinary spaces;
collapse runs of horizontal whitespace inside each block to one ASCII space;
trim each block; and discard empty blocks. Unknown tags are transparent and
comments contribute no text. A split statement's `source_text` is its exact
contiguous clause span in that view. `normalized_statement` may change only
boundary whitespace/punctuation needed to present that span as a standalone
sentence; it cannot add, remove, or strengthen meaning. The source HTML itself
remains byte-for-byte equivalent as a Unicode string in the source and
provider-input projection.

An eval-local deterministic HTML text-view helper implements this definition
solely to validate authored source spans and conformance fixtures. It is not a
provider extractor, is not imported by `app/`, and is never used on a URL or
network response. Validation checks exact source-span occurrence against this
text view, source-field provenance, and exact raw HTML preservation in the
provider-input projection.

## Artifact Layout

```text
services/pai-backend/backend/evals/job_semantics/requirement_breakdown_eval_00/
  requirement-breakdown-taxonomy.v1.md
  authoring.protocol.v1.md
  dataset.synthetic.v1.jsonl
  manifest.synthetic.v1.json
  review.pass1.md
  review.pass2.md
  conformance.v1.jsonl
  conformance.review.v1.md
  validate_and_freeze.py

services/pai-backend/backend/tests/
  test_jd_requirement_breakdown_eval_00.py

services/pai-backend/docs/research/
  PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-EVAL-00.md
```

The JSONL corpus is authoritative and human-reviewable. The tool is eval-local
and uses repository-managed Python; it validates corpus/fixtures, builds the
future provider-input projection without gold or correlation metadata,
computes distributions and matrices, computes semantic and exact-byte hashes,
and verifies/writes the freeze manifest. Its provider input is only a
`target_job_source` object containing the HTML fields that were present in the
source. It excludes `job_posting_url` and `source_application_ref`; the latter
remains local correlation metadata only. Omitted fields stay omitted, `null`
stays `null`, and empty/whitespace strings remain unchanged. No module under
`app/` and no production entrypoint will be added or modified.

## Identity, Fingerprints, and Freeze

- Dataset: `jd-requirement-breakdown-synthetic`.
- Dataset version: `jd-requirement-breakdown-synthetic-v1`.
- Schema version: `jd-requirement-breakdown-case@1`.
- Case IDs: `jd-syn-v1-001` through `jd-syn-v1-040`.
- Statement IDs: deterministic case-local sequence, such as
  `jd-syn-v1-001-s01`.
- Semantic fingerprint binds dataset identity/schema, taxonomy version/hash,
  complete source fields including presence/null/empty state, ordered gold
  statements and labels, and case metadata. Canonicalization is deterministic:
  cases sort by `case_id`; statements sort by source-field order
  (`JOB_DESCRIPTION`, then `JOB_REQUIREMENTS`), `source_order`, then
  `statement_id`; `boundary_tags` are unique and sorted lexicographically.
  `source_order` is one-based and unique within each source field, so changing
  semantic order changes the fingerprint while reordering JSONL lines alone does
  not. Object keys sort lexicographically; values serialize as UTF-8 JSON with
  `ensure_ascii=false`, compact separators `(',', ':')`, and non-finite numbers
  forbidden. No Unicode normalization is applied: source HTML/text code points
  remain exact. Omitted keys, `null`, empty strings, and whitespace-only strings
  have distinct canonical encodings. The canonical byte sequence has no trailing
  newline. The separate artifact SHA-256 remains sensitive to every JSONL byte
  and line order.
- Artifact SHA-256 is computed separately over the exact final JSONL bytes.
- The manifest records counts/distributions, taxonomy/protocol/review/conformance
  hashes, semantic fingerprint, exact artifact hash, code HEAD, UTC freeze time,
  and `provider_calls_before_freeze: 0`.
- Freeze verification fails closed if any hash, count, identifier, enum,
  provenance, or zero-provider assertion does not match.

## Coverage Targets

- Posting count: 40; gold statement count: 240–320; usually 6–8 per posting.
- Domains: finance/accounting 8, software engineering 8, and six each for data
  analytics, recruitment/HR, project management, and business communication.
- Language profile by posting: Vietnamese 24, English 10, mixed 6.
- Dataset domain enum values: `FINANCE_ACCOUNTING`, `SOFTWARE_ENGINEERING`,
  `DATA_ANALYTICS`, `RECRUITMENT_HR`, `PROJECT_MANAGEMENT`,
  `BUSINESS_COMMUNICATION`; language values: `VIETNAMESE`, `ENGLISH`, `MIXED`.
- Difficulty is eval-only metadata with `EASY`, `MEDIUM`, and `HARD`; it denotes
  decomposition/HTML/semantic-boundary complexity, not candidate seniority.
- Minimum statement counts: responsibility 80; experience 30; education 20;
  qualification 20; behavioral 30; other 20.
- Capability relevance: at least 50 `NON_CAPABILITY`, at least 12 `UNCLEAR`,
  with `CAPABILITY_BEARING` a substantial but not overwhelming majority.
- Required boundary families and coverage matrices follow the milestone request.
  Counts are reported, never padded with near-duplicate cases.
- Conformance fixtures: 30–40, separate from the 40 posting evaluation corpus.

## Review and Testing

Pass 1 checks each case/statement for source provenance, atomization,
normalization, type/relevance, signal span, order, language/domain/difficulty,
and boundary tags; changes are recorded. Pass 2 reviews the corrected full
corpus for split consistency, type/relevance boundaries, source/HTML fidelity,
and accidental capability mapping. Both passes will be labeled
`NOT INDEPENDENT HUMAN REVIEW` if performed by this author; no inter-rater
agreement claim is permitted.

Tests will cover unique and deterministic IDs; valid exact source keys and
source fields; nonempty raw/normalized text; valid enums and provenance/order;
absence of canonical capability output; split/keep fixtures; education,
qualification, experience, responsibility, behavior, and `OTHER` boundaries;
HTML/list/inline/line-break behavior; provider projection leakage; semantic
fingerprint stability and sensitivity; and freeze manifest counts/hashes.

Verification runs the focused tests, Ruff check and format check on touched
Python, scoped mypy where compatible with repository conventions, and
`git diff --check`. No migration is run or changed. A source-contract mismatch,
unreproducible taxonomy/atomicity/relevance boundary, or unresolved domain-owner
decision blocks freeze rather than inviting invented assumptions.

## Acceptance and Handoff

Complete only with a validated 40-posting corpus, 240–320 statements, required
coverage and separate conformance suite, reviewed taxonomy/protocol, both review
passes, reproducible fingerprints/hashes, passing focused verification, and
zero provider calls. Final report status is `COMPLETE_WITH_NON_INDEPENDENT_REVIEW`
or `COMPLETE`; dataset decision is exactly
`SYNTHETIC_REQUIREMENT_CORPUS_FROZEN_AND_READY` or
`SYNTHETIC_REQUIREMENT_CORPUS_NEEDS_REVISION`.

The next milestone may implement provider extraction/decomposition against this
frozen corpus but still cannot perform canonical capability mapping. Mapping
belongs to `PAI-JD-SEMANTIC-CAPABILITY-MAPPING-EVAL-00`.
