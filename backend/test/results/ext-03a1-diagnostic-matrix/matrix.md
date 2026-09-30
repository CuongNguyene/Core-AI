# EXT-03A.1 Diagnostic Matrix

## Results

| Input | Thinking | Success | Exp | Capabilities | Tools | Education | Grounding | Unsupported | Latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| native_pdf | high | True | 2 | 2 | 2 | 1 | 1.0 | 0 | 16636ms |
| native_pdf | medium | True | 2 | 6 | 2 | 1 | 1.0 | 0 | 6817ms |
| whole_parsed_text | high | False | 0 | 0 | 0 | 0 | 0 | 0 | 0ms |
| whole_parsed_text | medium | False | 0 | 0 | 0 | 0 | 0 | 0 | 0ms |

## Decision

- best_input_mode: native_pdf
- best_thinking: medium
- primary_blocker: PROMPT_SCHEMA_RECALL
- next_action: PROCEED_TO_EXT_03A_2_PROMPT_COVERAGE_CALIBRATION

This artifact contains safe counts, names and metrics only; no document text or raw model response.
