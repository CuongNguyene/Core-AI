# Instructional Design Research Plan

## Hypothesis

The research hypothesis is that a structured pipeline:

```text
Research brief → objectives → assessment → prerequisites → course → lessons
```

will have stronger pedagogical alignment than one-shot course generation.

ID-01 is implemented: it supplies typed fixtures, contracts, provenance, and
deterministic checks. ID-02 is implemented as a research experiment harness
with fair one-shot/structured conditions, fixture-only smoke execution, human
review contracts, and descriptive aggregation. No live-model experiment or
benchmark result has been run.

## Comparison design

For the same controlled `ResearchLearningBrief`, compare a staged design with a
one-shot baseline. Human reviewers should assess both artifacts without treating
the deterministic gate as a pedagogical oracle.

Planned evaluation dimensions:

- objective measurability;
- objective-assessment alignment;
- cognitive alignment;
- objective coverage;
- prerequisite quality and unresolved assumptions;
- sequence coherence;
- under-teaching and over-teaching;
- human correction effort.

The controlled fixture matrix has 12 explicitly authored research briefs:
Model Monitoring, Python Data Processing, and Technical Communication, each
with limited/substantial prior-evidence and application/analysis variants. The
intended full matrix is 12 fixtures × 2 conditions × 3 repetitions; ID-02's
smoke runner verifies mechanics with fixture artifacts only.

## Interpretation boundaries

The quality gate can identify structural defects consistently. It cannot prove
subject-matter correctness, instructional effectiveness, learner competency,
or production readiness. Any later experiment must separately document human
rubrics, raters, sample size, model configuration, prompt/schema versions, and
correction procedure.

## Framework references

The research rationale draws conceptually on Backward Design / Understanding by
Design, Revised Bloom's cognitive process and knowledge dimensions,
constructive alignment, and Evidence-Centered Design. Mastery learning and
worked-example/guided-practice research are future progression and strategy
policies; they are not implemented as achievement or content-generation rules
in v0.1.
