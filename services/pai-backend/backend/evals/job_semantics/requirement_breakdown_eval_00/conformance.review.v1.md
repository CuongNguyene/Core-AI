# Conformance fixture review

Date: 2026-10-08. Reviewer: same Codex agent; **NOT INDEPENDENT HUMAN REVIEW**.

Reviewed all 32 fixtures: 3 outer `target_job_source` states; 16 source-field states covering omitted/null/empty/whitespace across source ref, both HTML fields, and posting URL; and 13 semantic fixtures. The semantic fixtures are complete validator inputs with reserved case IDs outside the 40-posting corpus, exact HTML text views, valid gold statement provenance, and executable provider-projection expectations. The suite asserts all semantic fixtures pass `validate_case`, the deterministic HTML view equals the independently specified fixture expectation, and provider projection omits correlation ref, URL, and gold metadata. No provider call was made.

Coverage: `split_types` includes separate Experience/Education gold plus two independent responsibility splits; `coherent_keep` retains one coherent responsibility; `source_field_crossover` checks responsibility and education across source fields; `html_entity_and_inline` exercises entity decoding and transparent inline markup; `html_list_and_br` checks text boundaries; `provider_exclusion` checks the exact provider projection; and `capability_non_inference` keeps education/qualification non-capability. All 32 fixture IDs are unique. Review status: PASS, subject to focused suite and freeze verification.
