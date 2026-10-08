# Synthetic corpus review — Pass 1

Date: 2026-10-08. Reviewer: Codex (authoring/review agent; not an independent human reviewer).

## Scope and review method

Reviewed all 40 postings and all 301 expected statements in `dataset.synthetic.v1.jsonl` against the source HTML, source field, exact contiguous source span, source order, statement type, capability relevance, language/domain, boundary tags, and the protocol. No capability mapping is present or inferred. Source state exceptions in cases 001–006 were checked against both surviving HTML provenance and the absent/null/empty/whitespace field state.

## Posting-by-posting coverage

| Case | Domain | Language | Statements reviewed | Result |
|---|---|---:|---:|---|
| jd-syn-v1-001 | FINANCE_ACCOUNTING | MIXED | 8 | PASS |
| jd-syn-v1-002 | FINANCE_ACCOUNTING | VIETNAMESE | 8 | PASS |
| jd-syn-v1-003 | FINANCE_ACCOUNTING | VIETNAMESE | 8 | PASS |
| jd-syn-v1-004 | FINANCE_ACCOUNTING | VIETNAMESE | 8 | PASS |
| jd-syn-v1-005 | FINANCE_ACCOUNTING | VIETNAMESE | 8 | PASS |
| jd-syn-v1-006 | FINANCE_ACCOUNTING | VIETNAMESE | 8 | PASS |
| jd-syn-v1-007 | FINANCE_ACCOUNTING | ENGLISH | 8 | PASS |
| jd-syn-v1-008 | FINANCE_ACCOUNTING | ENGLISH | 8 | PASS |
| jd-syn-v1-009 | SOFTWARE_ENGINEERING | MIXED | 8 | PASS |
| jd-syn-v1-010 | SOFTWARE_ENGINEERING | VIETNAMESE | 9 | PASS |
| jd-syn-v1-011 | SOFTWARE_ENGINEERING | VIETNAMESE | 8 | PASS |
| jd-syn-v1-012 | SOFTWARE_ENGINEERING | VIETNAMESE | 8 | PASS |
| jd-syn-v1-013 | SOFTWARE_ENGINEERING | VIETNAMESE | 8 | PASS |
| jd-syn-v1-014 | SOFTWARE_ENGINEERING | VIETNAMESE | 8 | PASS |
| jd-syn-v1-015 | SOFTWARE_ENGINEERING | ENGLISH | 8 | PASS |
| jd-syn-v1-016 | SOFTWARE_ENGINEERING | ENGLISH | 8 | PASS |
| jd-syn-v1-017 | DATA_ANALYTICS | MIXED | 8 | PASS |
| jd-syn-v1-018 | DATA_ANALYTICS | VIETNAMESE | 8 | PASS |
| jd-syn-v1-019 | DATA_ANALYTICS | VIETNAMESE | 8 | PASS |
| jd-syn-v1-020 | DATA_ANALYTICS | VIETNAMESE | 8 | PASS |
| jd-syn-v1-021 | DATA_ANALYTICS | VIETNAMESE | 7 | PASS |
| jd-syn-v1-022 | DATA_ANALYTICS | ENGLISH | 7 | PASS |
| jd-syn-v1-023 | RECRUITMENT_HR | MIXED | 7 | PASS |
| jd-syn-v1-024 | RECRUITMENT_HR | VIETNAMESE | 7 | PASS |
| jd-syn-v1-025 | RECRUITMENT_HR | VIETNAMESE | 7 | PASS |
| jd-syn-v1-026 | RECRUITMENT_HR | VIETNAMESE | 7 | PASS |
| jd-syn-v1-027 | RECRUITMENT_HR | VIETNAMESE | 7 | PASS |
| jd-syn-v1-028 | RECRUITMENT_HR | ENGLISH | 7 | PASS |
| jd-syn-v1-029 | PROJECT_MANAGEMENT | VIETNAMESE | 7 | PASS |
| jd-syn-v1-030 | PROJECT_MANAGEMENT | MIXED | 7 | PASS |
| jd-syn-v1-031 | PROJECT_MANAGEMENT | VIETNAMESE | 7 | PASS |
| jd-syn-v1-032 | PROJECT_MANAGEMENT | ENGLISH | 7 | PASS |
| jd-syn-v1-033 | PROJECT_MANAGEMENT | ENGLISH | 7 | PASS |
| jd-syn-v1-034 | PROJECT_MANAGEMENT | ENGLISH | 7 | PASS |
| jd-syn-v1-035 | BUSINESS_COMMUNICATION | MIXED | 7 | PASS |
| jd-syn-v1-036 | BUSINESS_COMMUNICATION | VIETNAMESE | 7 | PASS |
| jd-syn-v1-037 | BUSINESS_COMMUNICATION | VIETNAMESE | 7 | PASS |
| jd-syn-v1-038 | BUSINESS_COMMUNICATION | VIETNAMESE | 7 | PASS |
| jd-syn-v1-039 | BUSINESS_COMMUNICATION | VIETNAMESE | 7 | PASS |
| jd-syn-v1-040 | BUSINESS_COMMUNICATION | ENGLISH | 7 | PASS |

## Corrections identified and applied before this pass

1. Cases 001–004 now explicitly encode `job_requirements_html` as omitted, null, empty, and whitespace-only respectively; cases 005–006 encode omitted and null `job_description_html`. Gold statement provenance points only to the non-empty surviving HTML field.
2. Case 009 retains the repeated REST endpoint statement in both source fields, with distinct provenance rows; the behavior clause was rewritten as constructive code-review behavior.
3. Case 010 splits coordinated design/testing actions into two responsibility statements with exact source spans and source order.
4. Case 011 represents experience and education in one source clause but keeps separate Experience and Education gold statements.
5. Case 015's behavior statement was changed from a concrete implementation duty to communication of design trade-offs. Case 023's behavior was changed from interview execution to fair, evidence-consistent evaluation. Case 040's behavior was changed from process ownership to collaboration behavior.
6. Cases 017, 021, 032, and 033 were corrected where role-specific outcomes belong to Responsibility rather than generic Behavioral Requirement.
7. Twelve generic, underspecified behavior phrases in cases 002, 004, 006, 008, 010, 012, 014, 016, 018, 020, 022, and 024 are `UNCLEAR`, not capability-bearing.
8. Routine/administrative responsibility clauses in cases 003, 005, 007, 008, 012, 016, 021, and 028 are `NON_CAPABILITY` rather than capability-bearing.
9. The age-range clause in case 018 and the Tableau mention in case 022 are `OTHER/NON_CAPABILITY`; tool mention alone is not capability evidence.
10. Boundary tags were moved to the actual examples: coordinated split to case 010, mixed requirement to case 011, duplicate cross-field semantics to case 009, and tool-without-capability to case 022.

## Outcome

All 40 cases / 301 statements pass structural, exact-span, source-field, ID/order, and taxonomy checks. Review corrections above are reflected in the reviewed artifact. No provider call was made. This pass is not an independent human annotation study and makes no inter-rater agreement claim.
