# JD-DEMO-03A.2A Evaluation Packets

This directory contains the final bounded runtime evaluation set for the ten JD
fixtures used by `JD-DEMO-03A.2A — Format-Specific Provider Evidence Contracts`.

Each packet contains:

- `source/`: the original JD `.docx` fixture;
- `output/JDRequirementExtractionOutputV2.json`: the normalized extraction
  output from the final runtime rerun;
- `manifest.json`: source checksum, runtime identifiers, review state, contract
  metadata, and locator counts.

The root `manifest.json` indexes all ten packets.

## Runtime boundary

- 10/10 extraction jobs succeeded.
- 10/10 extraction profiles remain `pending_review`.
- No profile was accepted or materialized into downstream role artifacts.
- The final run used `whole_parsed_text` with the text evidence contract.
- All exported locators are document text spans; no PDF page locator is present
  in this DOCX fixture set.
- `sourceReference`, source document IDs, job IDs, and profile IDs are retained
  only in manifests for evaluation traceability.

The packet outputs are exported artifacts, not a second source of truth. The
database records remain authoritative for runtime state.
