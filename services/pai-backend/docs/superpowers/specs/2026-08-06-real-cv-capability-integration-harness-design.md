# Real CV Capability Integration Harness Design

## Goal

Provide a controlled, repeatable integration harness that runs one real CV
through the existing capability-analysis API against a seed-only active role
profile. The harness proves the managed-input workflow without accepting a raw
JD or creating a role profile from JD extraction.

## Scope

The harness covers this path:

1. Start PostgreSQL, Redis, MinIO, backend, extraction worker and CTPAI/vLLM.
2. Upload an operator-supplied PDF or DOCX CV.
3. Create and poll an extraction job.
4. Reviewer accepts the resulting CV extraction profile.
5. Create and read a capability-gap portfolio using a seeded active target.
6. Assert target-local assessments and gaps, preliminary-safe portfolio fields,
   and cleanup of the controlled test data. Pair the live run with the existing
   rule contract test that verifies the internal provisional capability profile.

It does not upload a JD, generate role requirements, author a target, or
exercise the future-role track. Those belong to the role-profile authoring and
approval milestone.

## Data Boundary

- The CV stays outside the repository. The operator supplies its absolute path
  through `PAI_REAL_CV_PATH`; it is never copied into tests, fixtures, git,
  stdout, audit assertions or snapshots.
- The harness receives an expected SHA-256 through `PAI_REAL_CV_SHA256` and
  checks it before upload. This prevents accidentally using an unintended
  document without printing its contents.
- Test logs and assertion failures may contain document/profile/job/portfolio
  IDs, status values and response error codes only. They must not print request
  bodies from the document upload or extraction output.
- The seed target contains no raw JD. Its requirements are controlled test
  metadata and include `seed-integration-unavailable-signal`, a normalized
  sentinel evidence term that the operator confirms is absent from the CV.

## Seed Target

`seed_real_cv_capability_integration.py` seeds one immutable
`RoleCompetencyProfile`:

| Field | Value |
| --- | --- |
| ID | `seed-real-cv-capability-target` |
| Version | `1.0` |
| Status | `active` |
| Source JD profile | `seed-real-cv-capability-jd` version `1` |
| Rule/policy version | `capability-real-cv-v1` / `capability-policy-v1` |

The script also seeds a succeeded synthetic JD extraction job and its accepted
JD extraction profile required by the existing capability service source-version
guard. It stores only structured empty JD output and IDs; it does not create or
upload a raw JD.

The target has a normal low-risk requirement set for Python/FastAPI evidence
plus the sentinel requirement. The sentinel guarantees at least one
target-local provisional current-role gap without making a claim about the
person's real capability.

The script is idempotent: an identical target/profile is a no-op; a conflicting
version or payload exits non-zero. It prints only target/profile IDs.

## Runtime Preconditions

All services use the split compose stack and the migrated database:

```bash
bash devops/scripts/init-network.sh
docker compose -f devops/database/docker-compose.yml up -d
docker compose -f devops/redis/docker-compose.yml up -d
docker compose -f devops/minio/docker-compose.yml up -d
docker compose -f devops/backend/docker-compose.yml up -d --build
docker compose -f devops/backend/docker-compose.yml exec backend uv run alembic upgrade head
```

The operator verifies API and worker containers are running, the configured
CTPAI/vLLM endpoint is reachable, and `EVIDENCE_GRAPH_RUNTIME_ENABLED=true`
when the relation/section CandidateProfile path is being exercised. The legacy
adapter remains acceptable for this harness if it produces source-backed
CandidateProfile evidence.

## API Sequence

Use the development identities seeded by migration `20260803_08`:

- learner: `00000000-0000-0000-0000-000000000005`
- reviewer: `00000000-0000-0000-0000-000000000004`

1. Run the seed script and record `TARGET_PROFILE_ID`.
2. `POST /documents` with multipart `file=@$PAI_REAL_CV_PATH` and
   `document_kind=cv`, using the learner `X-PAI-Actor-ID`; record `document.id`
   only.
3. `POST /extraction-jobs` with
   `{"document_id":"<document-id>","document_kind":"cv"}` and the learner
   identity; poll
   `GET /extraction-jobs/{id}` until `succeeded` or a terminal failure.
4. Read `GET /extraction-profiles/{profile_id}`, then reviewer calls
   `POST /extraction-profiles/{profile_id}/accept` with
   `{"expected_version":<returned-version>}`.
5. Learner calls `POST /capability-gap-portfolios` with accepted CV profile ID,
   seeded target ID and a fresh valid correlation ID:

   ```json
   {
     "cv_profile_id": "<accepted-cv-profile-id>",
     "current_target_profile_id": "seed-real-cv-capability-target",
     "correlation_id": "real-cv-run-<opaque-suffix>"
   }
   ```

6. Learner reads `GET /capability-gap-portfolios/{portfolio_id}` and compares
   safe normalized output to the creation response.

The local runner performs these calls with `httpx`; the documented curl
equivalents use `PAI_API_BASE_URL`, never embed a CV filename or body in logs,
and send the required development identity header.

## Required Assertions

- The uploaded document reaches `clean`, and its extraction job reaches
  `succeeded` with one CV profile ID.
- The accepted CV profile is `accepted`, non-superseded and has a
  `CandidateProfile`; it is not treated as a verified human competency result.
- The create response is `201`; every current-role assessment/gap has
  `target_type=current_role`; `usage_mode=official` for the seeded active
  target; there is no combined readiness score.
- `ProvisionalCurrentCapabilityProfile` is currently an internal, non-persisted
  service value and is deliberately absent from the public portfolio response.
  Its `verification_status=provisional` invariant is checked by a rule-level
  contract test executed alongside the live harness, while the live harness
  checks that the API never upgrades CV evidence to a verified/assessed claim.
- The sentinel requirement yields a current-role gap whose missing signal does
  not claim absence of human capability.
- The portfolio has the seeded target version, owner/organization snapshots,
  safe IDs/versions/warning codes and no raw document, source excerpt,
  CandidateProfile, prompt or model-response field.
- A same-organization reviewer can read the portfolio; a non-owner,
  non-reviewer receives `403 capability_gap_access_denied`.

## Cleanup

The harness takes an explicit `PAI_REAL_CV_CLEANUP=true` switch. Cleanup is
disabled by default. When enabled, it removes only the exact document/object,
extraction job/profile and portfolio/audit rows from the harness run. The
shared seed target/source profile is retained for subsequent runs. Cleanup
never truncates shared tables or removes unrelated documents. A failed cleanup
reports opaque IDs and leaves data for manual inspection.

## Exit Criteria

Step A is complete when the harness succeeds against the live local stack with
an operator-provided CV, produces the required safe assertions, and has one
documented cleanup result. This is not evidence that JD-to-role-profile
authoring is implemented.
