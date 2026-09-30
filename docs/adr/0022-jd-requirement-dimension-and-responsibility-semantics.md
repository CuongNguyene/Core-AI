# ADR 0022: JD Requirement Dimensions and Responsibility Semantics

## Status

Accepted for JD-DEMO-03A.2D.

## Decision

`criterion_dimension` describes the candidate-evaluable criterion type. `modality`
describes the semantic role of the requirement in the JD. They are separate axes.

Responsibility or duty statements use:

```text
modality = responsibility
criterion_dimension = null
```

Explicit scope/exclusion statements such as "not required", "outside the scope", or
"does not own" use the existing contextual representation:

```text
modality = unspecified
criterion_dimension = null
```

They are preserved for review/context but are never positive candidate requirements.

Candidate-evaluable requirements use one of:

```text
skill | experience | education | credential | qualification
```

Responsibilities remain in `ExtractionProfile` and `RoleProfileDraft`, including
their evidence and observable behaviours, but are not independently scored by
capability matching or converted into capability gaps. Only requirements with a
non-null `criterion_dimension` enter those scoring paths.

## Validation

- A null dimension is valid for `modality=responsibility` or `modality=unspecified`.
- A non-responsibility requirement without a dimension fails closed in the JD
  source adapter and quality gate.
- A responsibility with a non-null dimension is rejected by the quality gate.
- Context-only unspecified rows are excluded from matching and capability-gap scoring.
- Credential and qualification are first-class dimensions; they are not inferred
  from generic skill or experience wording.
- Optional wording such as `may`, `can`, or `when needed` remains in the extracted
  statement and is not strengthened into an unconditional duty.

## Compatibility

This is a contract expansion only. It does not add a database column or migration,
does not change locator/provenance identity, and does not alter the CandidateProfile
schema. Existing requirements with a dimension preserve their prior matching and
Capability Gap behavior.
