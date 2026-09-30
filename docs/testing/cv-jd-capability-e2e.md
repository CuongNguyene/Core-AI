# CV-JD Capability E2E

This is the full raw-document harness. It is separate from the seeded real-CV
capability harness and runs both a provisional preview and an active official
scenario.

## Preconditions

```bash
export PAI_API_BASE_URL=http://localhost:8000
export PAI_REAL_CV_PATH=/absolute/path/consented-candidate.pdf
export PAI_REAL_CV_SHA256=<sha256>
export PAI_REAL_JD_PATH=/absolute/path/consented-role.pdf
export PAI_REAL_JD_SHA256=<sha256>
```

The runner verifies both hashes before the first upload. A mismatch aborts
without uploading either file.

Start the split stack and apply migrations:

```bash
bash devops/scripts/init-network.sh
docker compose -f devops/database/docker-compose.yml up -d
docker compose -f devops/redis/docker-compose.yml up -d
docker compose -f devops/minio/docker-compose.yml up -d
docker compose -f devops/backend/docker-compose.yml up -d --build
docker compose -f devops/backend/docker-compose.yml exec backend uv run alembic upgrade head
curl --fail "$PAI_API_BASE_URL/health/ready"
```

New role profiles require an exact active semantic policy before analysis. The
harness must create/activate or bind the operator-selected policy and pack
version explicitly; it must not rely on a latest/default domain. Historical
profiles without `semantic_policy_ref` may use only their explicit legacy
mapping. Migration `20260810_23` must be present before exercising the
governance API.

## Run

```bash
cd backend
uv run python -m scripts.run_cv_jd_capability_e2e
```

The runner performs independent CV and JD extraction jobs, reviewer acceptance,
draft creation and authoring, quality validation, approval, and capability
analysis. It prints only document/profile/draft/portfolio IDs, statuses and
mode names.

The two scenarios assert:

- `PROVISIONAL` role profile → `PREVIEW` capability analysis;
- `ACTIVE` role profile → `OFFICIAL` capability analysis;
- both scenarios resolve current and future policies independently and persist
  target-specific policy/pack/checksum snapshots;
- no `BLOCKING` gate is bypassed;
- no combined/final competency decision is emitted;
- no raw CV/JD, excerpt, prompt or model-response field appears in role,
  portfolio or audit output.
- each assessment exposes separate `retrieved_candidate_count` and
  `eligible_candidate_count`; for an explicit production requirement, related
  project evidence may be retrieved while eligible count remains zero and the
  status is `context_mismatch`.
- PREVIEW output keeps `capability_verification_status=PROVISIONAL` and
  `final_competency_decision_prohibited=true`; it does not update employee
  capability status to `VERIFIED` or emit learning objectives/paths.

For legacy accepted CV extraction profiles, the analysis service must derive
its evidence view from accepted raw claims whenever they exist. A stale
compatibility CandidateProfile must not downgrade `work_experience` to a
mention or drop `project_usage`; graph-only profiles continue to use their
CandidateProfile evidence directly.

JD extraction creates only a JD extraction profile. A draft can be created only
after reviewer acceptance, and profile approval is the only path to
`PROVISIONAL` or `ACTIVE`.

Cleanup is opt-in and must use the exact IDs printed by the run. It must remove
only that run's documents, objects, jobs, profiles, drafts, role profiles,
portfolios and child audit rows; it must never delete by owner, filename or a
broad table scan.

Set `PAI_REAL_CV_JD_CLEANUP=true` before the same command to execute this exact-
ID cleanup. The default is `false`.
