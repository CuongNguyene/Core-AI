# EXT-03A.2A Reference Fixture Integrity

| Check | Result |
| --- | --- |
| Document id matches reference run | True |
| Stored metadata matches blob | True |
| Reference checksum/size/MIME/pages match blob | True |
| Gemini request bytes match blob | True |
| Gemini input mode | `native_pdf` |
| Gemini prompt version | `2.1` |
| Expected labels machine-bound to checksum | False |

## Content sentinels

- Expected education terms present: False
- Expected domain terms present: False
- Mechanical-testing terms present: True

## Runtime history

- Jobs for document: 1
- Profiles for document: 1
- V2.1 calibration persisted: False
- Cross-fixture reuse detected: False

Only identifiers, storage metadata and SHA-256 fingerprints are included. No CV text or model response is stored.
