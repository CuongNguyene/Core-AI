# JD Role Profile Authoring

This workflow converts an accepted JD extraction profile into a reviewer-owned
draft and then an approved `PROVISIONAL` or `ACTIVE` role profile. JD
extraction alone never creates a role profile.

## API sequence

Use the development reviewer identity:
`00000000-0000-0000-0000-000000000004`.

1. Create a draft from an accepted JD profile:

   ```bash
   curl -X POST http://localhost:8000/role-profile-drafts \
     -H 'X-PAI-Actor-ID: 00000000-0000-0000-0000-000000000004' \
     -H 'Content-Type: application/json' \
     -d '{"source_jd_profile_id":"<accepted-jd-profile-id>","correlation_id":"role-authoring-run-1"}'
   ```

   Expect `201` and `status=draft`. A pending or superseded source returns
   `409 role_profile_draft_source_not_accepted`.

2. Edit the full structured requirement set. Send the current draft version:

   ```json
   {
     "expected_version": 1,
     "title": "Python Engineer",
     "requirements": [
       {
         "id": "python",
         "criterion_dimension": "skill",
         "classification": "role_critical",
         "evidence_terms": ["python"],
         "conflicting_terms": [],
         "confidence_threshold": 0.7,
         "assessment_recommendation": "practical_task",
         "rubric_version": "rubric-v1"
       }
     ]
   }
   ```

   Expect the version to increment. Stale versions return `409`.

3. Validate with `{"expected_version":2}`. Findings contain only safe codes:
   `no_requirements`, `duplicate_requirement_id`, `invalid_requirement_id`,
   `empty_evidence_terms`, `invalid_threshold`, `empty_recommendation` and
   `empty_rubric_version`.

4. Approve with an explicit semantic policy reference. Do not omit the policy
   or rely on an implicit domain default:

   ```json
   {
     "expected_version": 2,
     "requested_status": "provisional",
     "semantic_policy_ref": {
       "policy_id": "<active-policy-id>",
       "policy_version": "<active-policy-version>"
     },
     "semantic_policy": {
       "core_version": "semantic-core-v1",
       "pack_refs": [{"pack_id": "<selected-pack-id>", "version": "<selected-pack-version>"}]
     }
   }
   ```

   Use `"active"` only after every mandatory quality gate passes. Reviewer
   approval with a passing gate may create `ACTIVE`; a failing gate can create
   only `PROVISIONAL`. The policy and pack versions must resolve exactly and
   their checksum is snapshotted in analysis output. The response includes the
   resulting role profile ID, but never raw JD, excerpts, prompts or model data.

Drafts are not valid matching or capability-analysis targets. Use the returned
role profile ID only after approval. `PROVISIONAL` is non-official and must not
be described as a verified role definition.

## CAP-DEMO-04A compatibility contract

An accepted `JDRequirementExtractionOutputV2` is adapted without flattening its
semantic roles. Candidate-evaluable requirements preserve `skill`,
`experience`, `education`, `credential` or `qualification`; a responsibility
keeps `modality=responsibility` and `criterion_dimension=null`; and an
unspecified scope exclusion keeps `modality=unspecified` and is contextual, not
capability-scoreable. Logical groups/operators and `source_requirement_ref`
plus the supported `SourceLocator`/`NativePdfLocator` are carried into the
draft and the approved role profile.

Approval materializes the existing `RoleCompetencyProfile` persistence record;
there is no parallel aggregate or migration. A `PROVISIONAL` result remains
eligible only for preview usage, while `ACTIVE` continues to require the
existing passing quality gate and semantic-policy governance. CAP-DEMO-04A
does not execute or alter capability-gap scoring.
