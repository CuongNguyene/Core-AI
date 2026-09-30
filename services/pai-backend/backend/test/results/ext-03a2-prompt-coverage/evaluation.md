# EXT-03A.2 Prompt Coverage Calibration

## Configuration

- Input: native PDF
- Thinking: medium
- Prompt: cv_full_extraction@2.1
- Model: gemini-3.5-flash-lite
- Output budget: 16384

## Result

| Metric | V2.0 Medium | V2.1 Medium |
| --- | ---: | ---: |
| Technical success | True | True |
| Experience | 2 | 2 |
| Education | 1 | 1 |
| Capabilities | 6 | 5 |
| Tools | 2 | 2 |
| Grounded rate | 1.0 | 1.0 |
| Latency | 6817ms | 9130ms |

The artifact contains counts and metrics only; it does not contain document text or a raw provider response.
