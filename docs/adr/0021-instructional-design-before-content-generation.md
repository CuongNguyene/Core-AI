# ADR-0021: Separate Instructional Design from Content Generation

## Status

Accepted.

## Context

PAI's future learning flow may use capability gaps, assessments, lessons, and
learning objects. The current system does not yet have complete approved
role-level competency semantics, observable behaviors, target levels, evidence
constraints, or a verified knowledge base. A direct `gap → one-shot generated
course` flow would let a generation model choose objectives, evidence, sequence,
and content together without a trusted alignment boundary.

## Decision

- Add a research-only Instructional Design Core based on explicitly authored
  `ResearchLearningBrief` fixtures, not production role profiles or raw CV/JD.
- Treat objectives, assessment specifications, prerequisites, course outlines,
  and lesson specifications as canonical pedagogical design artifacts.
- Keep text, image, audio, video, tutor behavior, question banks, and learning
  object generation downstream renderers for a future decision.
- Use independently versioned staged proposal contracts instead of a primary
  one-shot `generate_course()` prompt.
- Run deterministic policy validation after proposals. Models cannot decide
  whether their own design passes.
- Persist no production learning path and expose no API in v0.1; snapshots are
  serializable research artifacts only.

## Alternatives considered

- **One-shot course generation from gaps:** rejected because it collapses
  outcome, evidence, sequence, and content decisions into non-auditable output.
- **Use production `RoleCompetencyProfile` as research input:** rejected because
  incomplete or provisional competency semantics could masquerade as approved
  instructional truth.
- **Generate factual lesson content now:** rejected because there is no approved
  source package, RAG policy, content governance, or production publishing path.

## Consequences

The module can test structural alignment across domain-diverse fixtures while
keeping research assumptions visible. Passing deterministic checks does not
mean SME approval, learner competency, or production-course approval. Future
content generation must consume a reviewed pedagogical specification and comply
with ModelGateway, PrivacyGateway, source, and publishing governance.
