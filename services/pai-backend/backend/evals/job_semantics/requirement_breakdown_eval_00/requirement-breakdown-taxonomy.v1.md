# Job Requirement Breakdown Taxonomy v1

Status: normative for `jd-requirement-breakdown-synthetic-v1`.

This is an evaluation/research taxonomy for breaking source JD text into
individually classifiable statements. It does not extend production extraction,
role-profile, capability-mapping, or gap semantics. In particular, ADR 0022
remains authoritative: responsibility statements have no candidate-evaluable
criterion dimension and are not independently scored or converted into
production capability gaps.

## 1. Source Boundary and Provenance

The source object is `target_job_source` in
`EmployeeLearningProjectionV1`. Its only fields are:

```json
{
  "source_application_ref": "synthetic source/application reference",
  "job_description_html": "...",
  "job_requirements_html": "...",
  "job_posting_url": "https://example.invalid/..."
}
```

The object and each field may be omitted or null in the source DTO. Empty and
whitespace-only strings are distinct from null and omission and must not be
silently rewritten. Unknown fields are invalid. Synthetic gold cases use only
these source fields and keep source HTML exactly as authored. The case-level
`source_application_ref` is synthetic metadata and, when the nested field is
present and non-null, must match it.

Every statement retains its originating field as one of:

- `JOB_DESCRIPTION`
- `JOB_REQUIREMENTS`

Field location is provenance only. It does not determine semantic type. A duty
may occur under requirements; a degree or credential may occur in the job
description. Identical statement text in both fields produces two statements
with different provenance, not a deduplicated row.

## 2. Statement Type

Every atomic statement receives exactly one type.

### `RESPONSIBILITY`

Expected role work: a duty, action, decision, output, or accountable outcome.
It answers what work the person is expected to perform.

Examples:

- “Prepare monthly financial statements.”
- “Coordinate project risks and dependencies.”
- “Develop and maintain REST APIs.”
- “Submit weekly timesheets.”

A responsibility can be `CAPABILITY_BEARING` or `NON_CAPABILITY`; type alone
does not answer whether the wording contains meaningful capability semantics.
This eval annotation never turns the responsibility into a production scoring
criterion or gap.

### `EXPERIENCE_REQUIREMENT`

Prior duration, exposure, practice, or work history required or preferred.

Examples:

- “Minimum 3 years of Python development experience.”
- “At least 2 years working in accounts payable.”

Duration is not proficiency: three years never means level 3, intermediate, or
advanced. If the statement names a concrete activity such as Python development,
that exact wording may be recorded as `capability_signal_text`.

### `EDUCATION_REQUIREMENT`

Academic education, degree, or field-of-study eligibility.

Examples:

- “Bachelor's degree in Accounting.”
- “Degree in Computer Science or a related field.”

Degree subject does not become a capability. In the absence of an additional
explicit capability clause, relevance is `NON_CAPABILITY`.

### `QUALIFICATION_REQUIREMENT`

Certification, license, formal credential, regulatory qualification, or
professional eligibility.

Examples:

- “CPA certification preferred.”
- “PMP certification is an advantage.”
- “Hold a current nursing license.”

Credential name does not imply capability truth or level. In the absence of an
additional explicit capability clause, relevance is `NON_CAPABILITY`.

### `BEHAVIORAL_REQUIREMENT`

General interpersonal, communication, cognitive, behavioral, or work-style
expectation, rather than a concrete duty in the role.

Examples:

- “Strong business communication skills.”
- “Able to work effectively with cross-functional teams.”
- “Detail-oriented and organized.”

If the statement instead names an action/outcome expected as role work, classify
it as `RESPONSIBILITY` (for example, “Present monthly findings to business
stakeholders”). A concrete transferable behavior may be `CAPABILITY_BEARING`;
generic wording may be `UNCLEAR` or `NON_CAPABILITY` under the definitions
below.

### `OTHER`

Source statement retained in the breakdown but outside the preceding semantic
types. Examples include age, location, schedule, travel, compensation,
benefits, and application logistics.

Examples:

- “Age 25–35.”
- “Willing to work Saturday shifts.”
- “Based in Ho Chi Minh City.”
- “Attractive salary and benefits.”

These remain `NON_CAPABILITY`; they are not discarded from the source record.
Discriminatory personal-attribute examples are limited to a small number of
boundary cases.

## 3. Capability Relevance (Independent Axis)

This axis labels semantic content only. It does not assign a canonical
capability, validate a candidate, create a role criterion, or infer proficiency.

### `CAPABILITY_BEARING`

The text explicitly states a concrete behavior, skill, knowledge, tool use, or
work capability that may warrant a later human-governed mapping review.

Examples:

- “Prepare monthly financial statements.”
- “Minimum 3 years of Python development experience.”
- “Strong business communication skills.”

It is only a semantic signal. It does not mean mapped, canonical, validated,
required at a proficiency level, or eligible for automatic scoring. A
responsibility tagged this way remains a responsibility under ADR 0022.

### `NON_CAPABILITY`

The statement, by itself, contains no capability semantics that should be
considered for canonical capability mapping.

Examples:

- A degree requirement by itself, including its subject.
- A certification/license by itself.
- Age, location, schedule, compensation, benefits, or application logistics.
- A routine administrative duty with no meaningful skill/behavior signal, such
  as “Submit weekly timesheets.”
- Generic personality language such as “positive attitude.”

### `UNCLEAR`

The text is too vague to decide whether meaningful capability semantics are
present. Use only for genuine semantic vagueness, not because a future ontology
match is hard.

Examples:

- “Good professional skills required.”
- “Strong overall aptitude.”

`UNCLEAR` does not mean the person lacks a capability and must never be
interpreted as a negative candidate finding.

## 4. Atomicity and Decomposition

One atomic statement is one independently classifiable semantic requirement or
responsibility. It is recorded once per source-field occurrence.

Split clauses when each states an independently meaningful behavior or when
their semantic types differ. Keep coordinated verbs when they form one bounded
behavior on the same object for the same outcome. Do not split mechanically on
“and”.

| Source text | Decision | Why |
|---|---|---|
| “Prepare monthly reports and conduct candidate interviews.” | Split into two responsibilities. | Each activity can stand alone and be classified independently. |
| “Design and implement REST APIs.” | Keep one responsibility. | Both verbs form one bounded API-delivery behavior. |
| “Prepare monthly financial statements and explain material variances.” | Keep one responsibility when the explanation is the completion of the same reporting outcome. | The linked actions form one coherent reporting responsibility. |
| “At least 3 years developing Python services and a bachelor's degree in Computer Science.” | Split into experience and education statements. | The clauses have distinct semantic types and eligibility meaning. |

Preserve source order independently within each source field, starting at 1.
For a split from one source position, assign consecutive order values in textual
order. The semantic fingerprint uses fixed field order
`JOB_DESCRIPTION` then `JOB_REQUIREMENTS`, then `source_order`, then
`statement_id`.

## 5. HTML and Exact `source_text`

`source_text` is the exact contiguous clause span in the normative text view of
the selected raw HTML field. It is not a markup substring, a translation, or a
paraphrase. The raw HTML remains unchanged in the source object.

The normative text view:

1. Parses HTML structure without browser rendering or network access.
2. Decodes named and numeric character references once.
3. Treats inline tags (including `<strong>`) as transparent; they add no text.
4. Inserts a line boundary before and after `<p>`, `<div>`, `<h1>`–`<h6>`, and
   `<li>` elements, and at `<br>`, preserving DOM/list/nesting order.
5. Treats unknown tags as transparent and HTML comments as having no text.
6. Maps non-breaking spaces to ordinary spaces, collapses whitespace runs
   inside each block to one ASCII space, trims blocks, and removes empty blocks.
7. Joins nonempty blocks with a single `\n`.

The source span for a statement must occur contiguously in that view. When the
source has markup within the visible text, `source_text` uses the visible text
after the above rendering rules. `normalized_statement` may normalize only
boundary whitespace or punctuation required to make the span readable alone;
it may not add facts, remove a condition, strengthen preference to requirement,
or otherwise change meaning.

The eval-local validator implements this text view only to check gold spans and
fixtures. It is not provider extraction and cannot be imported by production
`app/` modules.

## 6. Optional Requirement Wording

V1 has no `requirement_strength` field. Preserve “must”, “required”,
“preferred”, “an advantage”, and similar wording in source and normalized text.
Use boundary tags to test mandatory-versus-preferred and weak-preference
semantics; do not convert these words into proficiency levels.

## 7. Excluded Inferences

- `3 years Python experience` does not produce a Python level, proficiency, or
  canonical capability reference.
- A degree subject does not produce a capability.
- A certificate does not produce a capability.
- A responsibility is not automatically capability-bearing and is never
  automatically scored or converted into a production gap.
- `source_field` is provenance and never determines `statement_type`.
- `CAPABILITY_BEARING` is not a canonical mapping or validated capability.
- `NON_CAPABILITY`/`UNCLEAR` are not findings about a candidate.

## 8. Statement Record Contract

Each expected statement contains:

- `statement_id`: stable case-local ID (`jd-syn-v1-NNN-sNN`).
- `source_field`: `JOB_DESCRIPTION` or `JOB_REQUIREMENTS`.
- `source_text`: exact contiguous span from the normative HTML text view.
- `normalized_statement`: source-faithful standalone text.
- `statement_type`: one enum from Section 2.
- `capability_relevance`: one enum from Section 3.
- `capability_signal_text`: optional exact source span; omitted when not useful.
- `decomposition_group_id`: optional ID connecting source clauses split into
  multiple statements.
- `source_order`: one-based order unique within its source field.
- `label_source`: exactly `synthetic_spec`.
- `review_status`: exactly `REVIEWED` after both review passes.

No canonical capability identifier, capability level, proficiency, confidence,
role profile, or gap field is allowed.
