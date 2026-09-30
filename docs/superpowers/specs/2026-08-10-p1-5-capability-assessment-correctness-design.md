# P1.5 Capability Assessment Correctness & Explainability

## Scope

P1.5 fixes three deterministic projection defects in PREVIEW capability analysis:

1. requirement-aware compatibility for education and credential evidence;
2. claim-level retrieval isolation when observations share a source locator;
3. structured assessment reasons and decision details.

P2 semantic-policy governance, domain-pack vocabulary, extraction, verification workflow,
OFFICIAL analysis, and final competency decisions are unchanged.

## Current data flow

Accepted `CVExtractionOutput` is projected to `CandidateProfile`, then to an
`EvidenceIndex`, `EvidenceSemantics` observations, retrieval candidates, compatibility,
and finally `RequirementAssessment`/`TargetGap` records. `source_locator` identifies the
source span; `evidence_ref` remains the stable observation identity.

## Design

### Requirement-aware compatibility

`EvidenceCompatibility` remains domain-neutral and evaluates expectation, source kind,
context, participation, and authored constraints independently. Education evidence with
`EvidenceExpectation.EDUCATION` and a matching education source is direct compatible
support; credential evidence is direct for credential requirements. This directness is
separate from verification need: source-backed education or credential support remains
provisional and may recommend external verification without becoming unsupported.

Work-practice, production, and ownership constraints continue to reject incompatible
context or participation. No domain labels or inferred target signals are added.

### Claim-level isolation

Domain-pack mapping is applied to claim-owned concepts/source value and authored behavior
signals, not to an entire shared source excerpt for every sibling observation. Multiple
observations may share a locator but retain independent concepts and `evidence_ref`.
Canonical aliases still work when explicitly supplied through the existing semantic policy.
Co-occurring text is not counted as matched evidence unless its own observation carries the
matching claim.

### Explainability

Additive structured decision fields expose deterministic reason codes, supported/missing
signals, and observed/required confidence when relevant. Existing status, rationale,
counts, and persisted portfolio payloads remain readable. Reason codes are a fixed
vocabulary covering no evidence, context/participation/type mismatch, partial coverage,
unsupported target signal, confidence threshold, explicit mention, and external
verification. Every non-supported assessment has at least one structured reason.

### Closing correctness boundaries

Logical alternatives are represented explicitly with `logical_operator`. An `OR` group
is satisfied when at least one authored alternative is covered; it is not expanded into
an implicit `AND` across every term. `logical_group` remains a grouping/provenance label,
not a license to infer missing alternatives. The same rule is domain-neutral for degree,
accounting, language, and other requirement families.

Confidence thresholds are policy data, not competency facts. Every assessment carries
`required_confidence`, `threshold_source`, `threshold_policy_id`, and
`threshold_policy_version`. The current deterministic default is versioned in
`capability_analysis.policy`; accepted historical profiles are not mutated.

An unconstrained/plain capability requirement does not receive an invented usage or
production constraint. Mention evidence may therefore be retrieved and assessed as
provisional/verification-needed according to policy. A requirement explicitly authored
with `demonstrated_usage` remains subject to the corresponding context and participation
eligibility rules.

### Backward compatibility

New schema fields have safe defaults and are serialized additively. Existing portfolio
records are not rewritten. PREVIEW remains provisional; no VERIFIED status, OFFICIAL
analysis, production inference, education-to-work conversion, or verification workflow
change is introduced.

## Test strategy

Focused RED/GREEN tests cover education and credential directness, education not satisfying
work practice, shared-span TensorFlow/Docker/cross-domain sibling isolation, explicit
Apache Kafka alias preservation, status-specific reason codes, confidence/coverage
details, the Python work-evidence regression, OR alternatives, threshold provenance, and
plain-versus-demonstrated usage eligibility. Existing semantic-policy, production,
PREVIEW, repository, and extraction regressions must remain green.
