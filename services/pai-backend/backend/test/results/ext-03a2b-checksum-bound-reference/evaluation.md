# EXT-03A.2B Checksum-Bound Reference Evaluation

## Fixture integrity

- Fixture: `cv-nguyen-vu-minh-thien`
- SHA-256: `ff28e6315ae1f698e8277b6b572e2dcf8389eb70671a03c472f50a7b3c354ffa`
- MIME: `application/pdf`
- Pages: `3`
- Preflight: passed before each provider run

## Corrected expectations

- Education: MBA of eCommerce, Bachelor
- Experience minimum: 4
- Capability families: 11

## Comparison

| Metric | V2.0 Medium | V2.1 Medium |
| --- | ---: | ---: |
| Experience recall | 0.50 | 1.00 |
| Education recall | 1.00 | 1.00 |
| Capability family recall | 0.09 | 0.09 |
| Grounding | 1.0 | 1.0 |
| Unsupported | 0 | 0 |
| Duplicates | 0 | 0 |
| Latency | 9869ms | 21030ms |
| Output tokens | 1486 | 8016 |

The previous V2.0/V2.1 calibration is preserved but invalid for recall conclusions: its expected labels were not bound to the evaluated source checksum.

## Conclusion

V2.0 and V2.1 above are the only checksum-bound comparison runs. Prompt 2.2 is not created in this milestone.
