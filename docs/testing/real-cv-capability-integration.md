# Real CV Capability Integration

This procedure runs one operator-supplied CV through CV extraction and
capability analysis against the seeded active target. It does not upload a JD
or author a role profile. Keep the CV outside the repository and do not save
command output containing extraction responses.

## Preconditions

Set these values in the shell running the harness:

```bash
export PAI_API_BASE_URL=http://localhost:8000
export PAI_REAL_CV_PATH=/absolute/path/to/consented-candidate.pdf
export PAI_REAL_CV_SHA256=<lowercase-sha256-of-that-file>
export PAI_TARGET_PROFILE_ID=seed-real-cv-capability-target
```

Start PostgreSQL, Redis, MinIO, backend, worker and the configured vLLM/CTPAI
endpoint, then migrate and seed:

```bash
bash devops/scripts/init-network.sh
docker compose -f devops/database/docker-compose.yml up -d
docker compose -f devops/redis/docker-compose.yml up -d
docker compose -f devops/minio/docker-compose.yml up -d
docker compose -f devops/backend/docker-compose.yml up -d --build
docker compose -f devops/backend/docker-compose.yml exec backend uv run alembic upgrade head
curl --fail "$PAI_API_BASE_URL/health/ready"
docker compose -f devops/backend/docker-compose.yml exec backend uv run python -m scripts.seed_real_cv_capability_integration
```

The seed command is idempotent and prints only the target/source IDs.

## API Flow

Use the development identities seeded by migration `20260803_08`:

- learner: `00000000-0000-0000-0000-000000000005`
- reviewer: `00000000-0000-0000-0000-000000000004`

1. Upload the CV as multipart data. Assert HTTP `201` and `status=clean`; keep
   the returned document ID in a local shell variable.

   ```bash
   curl --fail -X POST "$PAI_API_BASE_URL/documents" \
     -H 'X-PAI-Actor-ID: 00000000-0000-0000-0000-000000000005' \
     -F 'document_kind=cv' \
     -F 'file=@/absolute/path/to/consented-candidate.pdf;type=application/pdf'
   ```

2. Create the extraction job with
   `{"document_id":"<document-id>","document_kind":"cv"}`. Poll the job
   until `status=succeeded`, then read only the profile ID/version.

3. Read the pending profile as learner and accept it as reviewer with
   `{"expected_version":<version>}`. Assert `review_state=accepted`, a
   non-null `candidate_profile`, and no supersession.

4. Invoke capability analysis as learner:

   ```json
   {
     "cv_profile_id": "<accepted-profile-id>",
     "current_target_profile_id": "seed-real-cv-capability-target",
     "correlation_id": "real-cv-run-<opaque-suffix>"
   }
   ```

   Assert HTTP `201`, `current_role.target_type=current_role`,
   `current_role.usage_mode=official`, non-empty assessments and gaps, and a
   gap for `seed-integration-unavailable-signal`. The response must contain no
   raw CV, source excerpt, CandidateProfile, prompt, model response or combined
   readiness score. Read the portfolio once more as learner and compare the
   same safe fields.

5. Run the existing rule contract test
   `test_provisional_current_capability_profile_is_immutable_and_source_referenced`.
   The public portfolio does not expose the internal provisional capability
   snapshot; the live assertion is that evidence remains preliminary-safe.

The equivalent runner is:

```bash
cd backend
PAI_API_BASE_URL="$PAI_API_BASE_URL" \
PAI_REAL_CV_PATH="$PAI_REAL_CV_PATH" \
PAI_REAL_CV_SHA256="$PAI_REAL_CV_SHA256" \
PAI_TARGET_PROFILE_ID="$PAI_TARGET_PROFILE_ID" \
uv run python -m scripts.run_real_cv_capability_integration
```

It prints only opaque IDs, states, gap count and cleanup status.

## Cleanup

Cleanup is disabled by default. To remove exactly this run after recording the
safe result, rerun with `PAI_REAL_CV_CLEANUP=true`. The runner deletes the
portfolio children/audit, extraction profile/audit/job, exact document row and
its exact MinIO object key. It never truncates tables, deletes by owner or
removes the shared seed target/source JD. Any cleanup failure leaves the IDs for
manual inspection and does not print document content.

```bash
PAI_REAL_CV_CLEANUP=true \
PAI_API_BASE_URL="$PAI_API_BASE_URL" \
PAI_REAL_CV_PATH="$PAI_REAL_CV_PATH" \
PAI_REAL_CV_SHA256="$PAI_REAL_CV_SHA256" \
PAI_TARGET_PROFILE_ID="$PAI_TARGET_PROFILE_ID" \
uv run python -m scripts.run_real_cv_capability_integration
```
