# CAP-DEMO-04B — Current-role capability gap verification
## Boundary

Capability analysis consumes an accepted, current `CandidateProfile` projection
from an `ExtractionProfile` and an approved `RoleCompetencyProfile`. It produces
one target-local assessment per candidate-evaluable requirement and persists the
result through the existing `CapabilityGapProfile` backing store. The legacy
`CombinedGapPortfolio` response remains a compatibility projection.

No learning path, course, generation, or competency-feedback transformation is
part of this milestone.

## Eligibility

Requirements with a non-null `criterion_dimension` are scoreable:

- `skill`
- `experience`
- `education`
- `credential`
- `qualification`

Responsibilities and scope-only/exclusion statements remain role context when
their `criterion_dimension` is null. They are not independently assessed and do
not create capability gaps. This preserves the distinction between a duty in a
role and a candidate-evaluable criterion.

## Evidence and decisions

Matching uses the existing semantic retrieval and compatibility policy. It does
not add fuzzy equivalence, tenure inference, threshold calibration, or ranking
heuristics. Assessment statuses remain source-grounded:

- `supported`
- `insufficient`
- `requires_verification`
- `context_mismatch`
- `not_found_in_evidence`

Each assessment/gap retains matched evidence references, decision details,
threshold provenance, and the existing verification signals. Evidence endpoints
resolve references through the canonical semantic evidence projection.

## Governance and persistence

An approved `PROVISIONAL` role target produces `PREVIEW` output with
`current_target_profile_provisional`, `preview_readiness`, and a verification
queue; it is not an official competency decision. An `ACTIVE` target produces
`OFFICIAL` output under the existing policy. The persisted portfolio contains
safe IDs, references, and decision metadata, not raw CV/JD text, prompts, or
provider responses.

The same candidate profile version, target profile version, policy, and
idempotency key reuse the existing portfolio contract. No new migration or
parallel persistence model is introduced.

## Verification

Focused verification runs with the backend environment's package root:

```bash
cd pai-backend/backend
PYTHONPATH=. UV_CACHE_DIR=/tmp/ct-brain-hub-uv-cache \
  uv run pytest \
  tests/test_capability_analysis_rules.py \
  tests/test_capability_analysis_service.py \
  tests/test_capability_gap_profile.py \
  tests/test_capability_analysis_repository.py \
  tests/test_capability_analysis_api.py \
  tests/test_capability_gap_integration_api.py -q
```

The rules regression fixture explicitly covers 25 scoreable requirements, 15
responsibilities, and 3 exclusions; expected assessment cardinality is 25.
