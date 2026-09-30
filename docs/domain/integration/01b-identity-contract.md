# INTEGRATION-01B — Identity Contract

## Decision

LMS owns user authentication, credentials, registration, account roles, deletion, and account lifecycle. PAI does not create a shadow LMS user, store passwords/JWT refresh tokens, or accept browser-supplied identity fields as authoritative.

## ActorReference v1

```json
{
  "external_user_id": "lms-user-uuid",
  "source_system": "lms",
  "organization_ref": "org:pending-authority",
  "tenant_ref": "tenant:pending-authority",
  "role_refs": ["TRAINER"],
  "status": "ACTIVE"
}
```

`external_user_id` is the stable LMS identity key. `organization_ref` and `tenant_ref` are required once authority is established; current target evidence does not prove either model exists, so they must not be fabricated or mapped from a user ID. `role_refs` are claims for PAI authorization mapping, not a transfer of LMS lifecycle ownership.

## Trust and lifecycle rules

- LMS service identity authenticates the caller; the PAI service validates issuer, audience, expiry, and the trusted actor reference.
- PAI may persist a minimal external reference and PAI-owned authorization/delegation context, but never credentials or an LMS account copy.
- LMS account deletion/deactivation produces an identity-status update or causes future calls to use `status: DEACTIVATED`; PAI stops accepting new actions and retains only records required by its governed retention/audit policy.
- Identity changes do not rewrite historical PAI decisions. Historical actor references remain audit references.
- PAI authorization for SME review, competency decisions, and delegation remains PAI-owned. An LMS role does not automatically grant a PAI privilege.

## Tenant prerequisite

Tenant isolation is a release prerequisite for cross-organization integration. Until an authoritative organization/tenant mapping is agreed, only a deliberately single-tenant pilot with an explicit fixed scope can use this boundary. The contract never infers organization membership from email, role, course, or user ID.
