# INTEGRATION-06E Candidate Authorization Boundary

## Decision

Authentication originates in the LMS, but authorization for Candidate data,
claims, evidence, and review actions belongs to PAI. The browser never decides
PAI authorization and never supplies an authoritative actor ID.

## Request flow

```text
LMS JWT/session
    |
    v
LMS Identity Bridge
    |
    v
PaiLearningAdapter
  - forwards authenticated identity assertion
  - carries request/correlation and idempotency metadata
    |
    v
PAI identity resolver
  - resolves Actor
  - resolves Organization membership
  - resolves PAI roles/delegations
    |
    v
Candidate authorization policy
  - organization scope
  - candidate/document ownership
  - reviewer role/action
  - evidence access policy
    |
    v
Candidate API handler/service
```

## LMS responsibilities

- authenticate the user and maintain the LMS session;
- send an identity assertion through the server-side adapter;
- render PAI's authorization result and safe error code;
- never infer a candidate's organization or review permission from UI state;
- never send `actor_id` as a browser-controlled field;
- never reconstruct evidence from `document_id`, `profile_id`, or storage keys.

## PAI responsibilities

- validate the identity bridge assertion and resolve the PAI Actor;
- verify active organization membership;
- apply PAI role/delegation policy to each candidate operation;
- enforce candidate/document/profile/claim ownership relationships;
- authorize evidence retrieval independently from claim listing;
- authorize review actions with profile version and idempotency checks;
- emit safe audit events with actor, organization, resource reference, action,
  policy version, and correlation ID.

The current development-only `X-PAI-Actor-ID` header is not this production
boundary. It may remain a test fixture mechanism, but it must not be accepted
as the LMS production identity bridge.

## Authorization matrix (proposed)

| Operation | Required PAI checks | Typical PAI role |
|---|---|---|
| list candidates | active organization membership and list scope | reviewer/admin |
| read candidate detail | organization + candidate read scope | reviewer/admin |
| read claim evidence | organization + candidate ownership + evidence policy | reviewer/admin |
| attach document | organization + candidate write scope | reviewer/admin |
| accept/revise/reject | organization + candidate write scope + reviewer role + expected version | reviewer |

An LMS role name is not itself a PAI role. Any cross-system mapping must be an
explicit server-side policy version, audited by PAI, and evaluated after actor
resolution.

## Denial behavior

PAI returns a safe status/code pair (`401` for missing/invalid identity,
`403` for authenticated but unauthorized access, `404` where resource
non-disclosure is required, and `409` for stale review state). Responses do not
reveal whether an inaccessible candidate, claim, or evidence object exists when
the policy requires non-disclosure.

## Audit boundary

Audit records contain stable resource references, actor/organization IDs,
policy version, action, result, and correlation/idempotency references. They do
not contain raw CV/JD, provider prompts, raw model output, or unbounded excerpts.
Evidence excerpts are returned only through the authorized evidence contract.

## Future implementation acceptance criteria

1. A forged browser `actor_id` cannot change the PAI-resolved actor.
2. An actor from another organization cannot list or retrieve the candidate.
3. A non-reviewer cannot perform review actions.
4. A reviewer cannot accept a stale profile version.
5. Candidate access does not imply unrestricted raw-document access.
6. All decisions are attributable to the resolved actor and policy version.
