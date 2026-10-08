# Synthetic Requirement Breakdown Authoring Protocol v1

Dataset: `jd-requirement-breakdown-synthetic-v1`
Schema: `jd-requirement-breakdown-case@1`
Status: normative authoring/freeze protocol.

## 1. Synthetic-Only Source Rule

Write original fictional postings. Do not use real companies, employees,
applicants, ATS/HRM records, CVs, interviews, job advertisements, or real
posting URLs as seed text. Do not scrape, search, fetch, parse, or follow any
URL. A URL string, when present, must be under `https://example.invalid/` and
serves only as synthetic provenance. No PII is allowed.

Do not add a raw JD upload flow. The source boundary is the existing
`target_job_source` object with only:

- `source_application_ref`
- `job_description_html`
- `job_requirements_html`
- `job_posting_url`

The object and each field may be omitted or null, and string values may be
empty or whitespace-only. Preserve all four states distinctly. Unknown keys
fail validation. Main posting records use complete source objects and synthetic
references/URLs; conformance fixtures exercise omitted/null/empty states,
including omitted/null/empty-object `target_job_source` forms.

The case-level `source_application_ref` is a synthetic dataset correlation
value, not a role ID, canonical JD ID, or capability reference. When both the
case-level and nested source reference are present and non-null, they must be
identical.

## 2. Posting and Statement Contract

Each JSONL line is one case with:

- `case_id`: `jd-syn-v1-001` through `jd-syn-v1-040`.
- `source_application_ref`: deterministic synthetic source reference.
- `target_job_source`: source object only; no new source field.
- `expected_statements`: reviewed atomic gold statements.
- `language_profile`: `VIETNAMESE`, `ENGLISH`, or `MIXED`.
- `domain`: `FINANCE_ACCOUNTING`, `SOFTWARE_ENGINEERING`,
  `DATA_ANALYTICS`, `RECRUITMENT_HR`, `PROJECT_MANAGEMENT`, or
  `BUSINESS_COMMUNICATION`.
- `difficulty`: eval-only `EASY`, `MEDIUM`, or `HARD`, describing decomposition,
  HTML, or semantic-boundary complexity, never candidate seniority.
- `boundary_tags`: unique eval-only taxonomy/test labels.
- `label_source`: exactly `synthetic_spec`.

Each statement follows the record contract in
`requirement-breakdown-taxonomy.v1.md`. Statement IDs are deterministic and
case-local. `source_order` starts at 1 and is unique within each source field;
preserve visible source order and retain duplicate semantics across fields as
separate provenance records. Preserve original requirement strength in text;
V1 adds no requirement-strength field.

`source_text` is the exact contiguous clause span in the normative HTML text
view. The eval-local text-view helper is deterministic validation only; it
does not fetch or invoke a provider. `normalized_statement` cannot alter the
source meaning. Record an exact `capability_signal_text` only when a verbatim
span is useful; never replace it with an ontology label.

## 3. Source HTML and Coverage

Use varied realistic HTML, not perfectly templated markup: paragraphs, `ul` and
`ol` lists, nested lists, headings, inline `<strong>`, `<br>`, mixed paragraphs
and lists, multiple clauses in a list item, and duplicate-style bullets. The
normative text view is defined in the taxonomy. Preserve input HTML strings
exactly and author the corresponding text spans by that view.

Use 40 postings and target 240–320 statements (normally 6–8 per posting),
prioritizing semantic variety over count. Domain counts are 8 finance/accounting,
8 software engineering, and 6 each data analytics, recruitment/HR, project
management, and business communication. Posting language counts are 24
Vietnamese, 10 English, and 6 mixed-language. Do not mechanically translate
one posting to inflate language coverage.

Minimum statement-type counts: 80 `RESPONSIBILITY`, 30
`EXPERIENCE_REQUIREMENT`, 20 `EDUCATION_REQUIREMENT`, 20
`QUALIFICATION_REQUIREMENT`, 30 `BEHAVIORAL_REQUIREMENT`, and 20 `OTHER`.
Include at least 50 `NON_CAPABILITY` and 12 `UNCLEAR` statements; capability
bearing must be a substantial majority but not overwhelming. Include all
boundary families from the milestone, with no near-duplicate padding.

## 4. Conformance Suite Isolation

Author 30–40 small taxonomy/decomposition fixtures in `conformance.v1.jsonl`.
They use a separate ID namespace, do not count as postings or gold statements,
and are never included in a future provider-evaluation dataset. Cover type and
relevance boundaries, split/keep decisions, provenance, HTML text view, provider
projection exclusions, and all optional/null/empty/whitespace source states.
Conformance fixtures test the frozen contract; they are not added to the 40
posting corpus after freeze.

## 5. Provider Boundary and Zero-Call Rule

No Jev, LLM, ModelGateway, embedding, HTTP, or provider operation is permitted
during authoring, reviewing, validating, or freezing. Do not write provider
prompts or compare models.

The eval-only future model-input projection is:

```json
{
  "target_job_source": {
    "job_description_html": "...",
    "job_requirements_html": "..."
  }
}
```

It includes only HTML keys present in the source, preserving exact raw values;
missing keys remain missing, null remains null, and empty/whitespace-only
strings remain unchanged. If the outer target object is omitted, it stays
omitted; if null, it stays null; if empty, it stays `{}`. The model input
excludes `source_application_ref`, `job_posting_url`, expected statements,
types, relevance, signal spans, tags, language, domain, difficulty, label source,
review status, IDs, and all other gold/evaluation metadata. The application
reference may be retained locally for correlation, never sent as model input.
This projection helper is not a network client and is never sent anywhere in
this milestone.

The freeze manifest must record `provider_calls_before_freeze: 0`. Code review
and scoped source inspection must confirm no provider client import/call was
introduced.

## 6. Review Procedure

### Pass 1 — per-record review

Review every case and statement for:

- synthetic-only source and exact contract keys;
- exact source field, visible source span, and order;
- atomicity, split/keep, and decomposition-group consistency;
- normalization faithfulness;
- statement type and independent capability relevance;
- exact optional capability signal span;
- language/domain/difficulty and boundary tags;
- absence of canonical capability refs/levels or candidate conclusions.

Record every changed case ID and what was corrected in `review.pass1.md`.

### Pass 2 — full consistency review

Re-read the entire corrected corpus against the frozen taxonomy. Focus on split
consistency; responsibility versus behavioral/experience semantics; education
and credential boundaries; capability-bearing versus non-capability/unclear;
HTML and source provenance; duplicated semantics across source fields; and
accidental canonical mapping or level inference. Record findings in
`review.pass2.md`. Because both passes are authored by one agent, label both
`NOT INDEPENDENT HUMAN REVIEW`; do not claim independent validation,
inter-rater agreement, or SME approval.

Review conformance fixtures separately and record rule-to-fixture coverage in
`conformance.review.v1.md`.

## 7. Canonical Semantic Fingerprint

The semantic fingerprint is distinct from the exact artifact hash. It binds
dataset ID/version/schema, taxonomy version and exact taxonomy-file SHA-256,
all cases, source field presence/null/empty/whitespace states, source HTML,
ordered gold statements and labels, and all case metadata.

Canonicalization:

1. Sort cases by `case_id`.
2. Sort statements by fixed `source_field` rank (`JOB_DESCRIPTION` before
   `JOB_REQUIREMENTS`), then integer `source_order`, then `statement_id`.
3. Sort unique `boundary_tags` lexicographically.
4. Sort object keys lexicographically; preserve every other scalar, field
   presence, null, string, and HTML code point exactly. Do not Unicode-normalize.
5. Serialize using UTF-8 JSON, `ensure_ascii=false`, compact separators
   `(',', ':')`, and reject non-finite numbers. The canonical bytes have no
   trailing newline.
6. Hash the canonical bytes with SHA-256.

Reordering physical JSONL lines or the JSON statement array without changing
`source_order` must leave the semantic fingerprint unchanged. Changing
`source_order`, source HTML/text, a label, a presence/null/empty state, taxonomy
bytes, or any bound case metadata must change it. The independent artifact
SHA-256 hashes exact final JSONL bytes and therefore changes with line order,
whitespace, escaping, or any other byte-level edit.

## 8. Freeze and Immutability

`manifest.synthetic.v1.json` records dataset identity/schema, posting/statement
counts, taxonomy hash, semantic fingerprint, exact artifact hash, distributions
for type/relevance/source/language/domain/difficulty/tags, both review hashes,
protocol hash, conformance hash, code HEAD, one UTC freeze timestamp, and zero
provider calls. The validator recomputes counts and hashes and fails closed on
any mismatch.

After freeze, do not modify the dataset, taxonomy, protocol, reviews, or
conformance fixtures in place. Any semantic edit requires a new dataset or
taxonomy version and regenerated manifest; record exact artifact and semantic
hashes separately.

## 9. Prohibited Output and Side Effects

The corpus and tooling must contain no `canonical_capability_ref`,
`capability_id`, `capability_namespace`, `capability_semantic_key`,
`capability_level`, proficiency, confidence, `RoleCompetencyProfile`,
`RoleCapabilityRequirement`, `CapabilityGapProfile`, candidate comparison,
production API, database table, or migration. Do not alter HRM, ATS, LMS, or
candidate semantic modules. Do not commit or push.
