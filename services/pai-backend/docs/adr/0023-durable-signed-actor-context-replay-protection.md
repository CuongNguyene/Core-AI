# ADR-0023: Durable replay protection for signed LMS actor context

## Status

Accepted.

## Context

The LMS bridge (`lms/lms/pai/client.py`, formerly the `pai_frappe` app) signs a short-lived actor context when it calls PAI on behalf of
an LMS author. The previous verifier remembered used nonces in a process-local
set. That prevented immediate replay only while the same FastAPI worker lived;
another API instance or a process restart could accept the same signed request.

## Decision

- Keep Ed25519 signature validation and the maximum 60-second context lifetime
  in the PAI API boundary.
- After validation, atomically insert the nonce and signed expiry time into the
  PAI PostgreSQL database. A duplicate primary key is an
  `ACTOR_CONTEXT_REPLAYED` authorization failure.
- Purge expired nonce rows during successful nonce consumption. The nonce table
  contains no raw PII, request content, private key or access token.
- Production `create_app` always configures the SQLAlchemy nonce store. An
  in-memory store remains only for FastAPI unit fixtures that intentionally do
  not create a database.
- The migration is a merge revision for the two current Alembic heads. It must
  be applied before deploying an API process containing this code.

## Alternatives considered

- Process-local set: rejected because it is not multi-instance safe.
- Redis-only nonce key: rejected for this deployment because Redis availability
  and dependency are not yet wired into the PAI runtime. PostgreSQL is already
  the durable authoritative store for PAI domain operations.
- Accept replay until a future queue implementation: rejected because signed
  authorization must fail closed independently of long-running job dispatch.

## Consequences

- Database availability is now required for signed LMS integration calls. A
  store failure returns a safe `actor_context_unavailable` response rather than
  accepting an unprotected request.
- Operators must run `alembic upgrade head` before rolling out the API and
  preserve the `actor_context_nonces` table in database backup policy.
- The Frappe bridge continues to sign a fresh nonce per call; no browser client
  receives the signing key.

## Migration

Create `actor_context_nonces(nonce, expires_at)` with a primary key on `nonce`
and an expiry index. No existing signed context or user data is migrated.
