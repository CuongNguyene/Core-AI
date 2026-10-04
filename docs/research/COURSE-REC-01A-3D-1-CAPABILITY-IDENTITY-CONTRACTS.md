# COURSE-REC-01A.3D-1 — Capability Identity & Dual-Identity Contracts

## Decision

This slice adds three immutable, provider-neutral identity contracts under
`app.capability_governance`: `CanonicalCapabilityRef`, `SourceSemanticRef`, and
`CapabilityIdentityPair`. The pair name describes co-carried identities only;
constructing one does not assert review, mapping, or approval.

This follows the hybrid outcome-plus-domain-pack architecture selected in
COURSE-REC-01A.3C. Source and business identifiers remain owned by their
domains. A canonical capability reference is a separate semantic identity and
may be absent until later governance work creates an approved mapping.

## Canonical capability reference

The canonical form is exactly one string:

```text
capability:<namespace_key>:<semantic_key>
```

Both keys use lowercase ASCII letters, digits, and underscores. Each starts
with a letter. Namespace length is 2–64 characters; semantic-key length is
2–128 characters. Parsing is strict: no case folding, trimming, labels,
additional separators, whitespace, slashes, dots, hyphens, or `@version`
suffixes. Syntactically valid unknown namespaces are accepted because this
identity-only layer does not own a namespace registry.

`CanonicalCapabilityRef` is a frozen Pydantic `RootModel[str]`; JSON and model
serialization therefore use the same string representation. It contains no
label, pack release, provider, course, or requirement metadata. Renaming labels
or releasing a new pack does not change the identity. No capability definitions
or production capability IDs are created here.

Valid syntax examples (not registered capabilities):

```text
capability:professional_core:project_management
capability:software:programming_fundamentals
```

Invalid examples include `project_management`,
`capability:software:Programming`, `capability:software:project-management`,
`capability:software:python@2`, and `capability:software@1:python`.

## Source identity

`SourceSemanticRef` carries `source_namespace`, a bounded `entity_kind`, the
source-owned `source_id`, and optional `source_version`. Supported entity kinds
are role requirement, LearningNeed competency, Learning Path target, course
learning outcome, direct course claim, candidate concept, and provider
classification. The source namespace is a lowercase source key; source IDs are
opaque to this package and preserved as supplied, subject to non-empty,
length, and surrounding-whitespace checks.

Examples include a role-owned `req-123`, a course-scoped outcome identifier,
and a provider's `dc.subject` value. These remain source identities and are not
parsed or upgraded to canonical capability references.

## Dual identity and unmapped state

`CapabilityIdentityPair` requires a structured `source_ref` and allows an
optional typed `canonical_capability_ref`. A source semantic with no governed
canonical identity is valid with the canonical field set to `null`. No
placeholder such as `unknown`, `other`, or a nearest-match capability is
created. Strict Pydantic model boundaries reject raw strings where either
identity object is required.

The pair is not a semantic mapping record. Mapping method, evidence, approval,
status, and lifecycle are deferred to COURSE-REC-01A.3D-3.

## Compatibility and scope

This implementation adds no fields to `RoleRequirement`, `LearningNeedProfile`,
or `CourseCapabilityProfile`; does not change the current opaque
`CourseCapabilityProfile.capability_ref`; and does not modify
`professional_capability_core@0.1`, the COURSE-REC-01B engine, or its fixtures.
Values such as `project_management` are not silently converted to a namespaced
ID. No persistence, API, migration, adapter, capability definition, or LMS
change is part of 3D-1.

## Deferred work

Capability definitions and pack release lifecycle belong to 3D-2. Governed
semantic mapping records belong to 3D-3. Role/LearningNeed and course adapters
belong to 3D-4 and 3D-5. Compatibility and migration planning belongs to 3D-6.
