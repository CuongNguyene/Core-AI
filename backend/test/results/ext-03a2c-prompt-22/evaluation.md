# EXT-03A.2C Prompt 2.2 Capability Derivation Calibration

## Reference

- Fixture: `cv-nguyen-vu-minh-thien`
- SHA-256: `ff28e6315ae1f698e8277b6b572e2dcf8389eb70671a03c472f50a7b3c354ffa`
- Input: native PDF
- Model: `gemini-3.5-flash-lite`
- Thinking: medium
- Provider calls: 1

## Hypothesis

Prompt 2.2 makes capability derivation explicitly dependent on inspecting every
experience record, while preserving V2.1 enumeration, strict grounding,
proficiency safeguards and tool/capability separation.

## Comparison

| Metric | V2.1 | V2.2 |
| --- | ---: | ---: |
| Experience recall | 1.0 | 1.0 |
| Education recall | 1.0 | 1.0 |
| Capability family recall | 0.09090909090909091 | 0.18181818181818182 |
| Grounding | 1.0 | 1.0 |
| Unsupported | 0 | 0 |
| Duplicates | 0 | 0 |
| Latency | 21030ms | 17199ms |
| Output tokens | 8016 | 5891 |

## Capability family results

- Project Management: FOUND
- Product Management: NOT_FOUND
- eCommerce: NOT_FOUND
- Omnichannel Commerce: FOUND
- Order Management: NOT_FOUND
- Warehouse Management: NOT_FOUND
- Delivery / Logistics Management: NOT_FOUND
- Operations Planning: NOT_FOUND
- Digital Platform Development: NOT_FOUND
- Team Leadership: NOT_FOUND
- Process Optimization: NOT_FOUND

Extracted capabilities are recorded by name and deterministic quality metrics
only; raw CV text and raw Gemini response are not stored.

## Decision

- Capability gate: `False`
- Experience gate: `True`
- Education gate: `True`
- Grounding gate: `True`
- Unsupported gate: `True`
- Duplicate gate: `True`
- Next action: `REVISIT_V2_SCHEMA_BEFORE_MORE_PROMPT_TUNING`

No prompt 2.3, schema redesign, migration, frontend change or multi-CV run
was performed.
