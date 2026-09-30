# EXT-03A.3 Capability Extraction Schema Diagnostic

## Current schema diagnosis

Capability items currently repeat `source_excerpt`, locator, strength and
confidence inside each item even when the same source statement is already
represented by `experience[].evidence[]`. Canonicalization, dedupe,
multiple-experience promotion and document identity are post-model concerns.

## Experimental schema

`evidence_inventory[]` stores each concise grounded excerpt and locator once.
Experience, education, tools and capabilities reference inventory IDs;
capabilities emit `raw_name` plus `evidence_refs[]`. The adapter materializes
the existing V2 shape for grounding and CandidateProfile compatibility.

## Reference configuration

- Fixture: `cv-nguyen-vu-minh-thien`
- SHA-256: `ff28e6315ae1f698e8277b6b572e2dcf8389eb70671a03c472f50a7b3c354ffa`
- Input: native PDF
- Model: `gemini-3.5-flash-lite`
- Thinking: medium
- Provider calls: 1

## One-call result

| Metric | V2.2 | Experimental |
| --- | ---: | ---: |
| Experience recall | 1.0 | 0.12 |
| Education recall | 1.0 | 1.00 |
| Capability family recall | 0.18181818181818182 | 0.18 |
| Grounding | 1.0 | 1.0 |
| Unsupported | 0 | 0 |
| Duplicates | 0 | 0 |
| Output tokens | 5891 | 1643 |
| Latency | 17199ms | 7872ms |

Evidence refs: `2` total, `2` resolved, `0` dangling.

Experience enumeration regressed from `17` to `2` records in the one-call
schema variant. This fails the preservation gate even though evidence
grounding and reference integrity passed.

## Conclusion

Schema hypothesis: `NOT_CONFIRMED`. Two-stage
experiment: `NOT_RUN`; it remains the next bounded experiment if this one-call
variant does not pass the 7/11 gate. No prompt 2.3, production V3 switch,
migration, frontend or multi-CV run was performed.
