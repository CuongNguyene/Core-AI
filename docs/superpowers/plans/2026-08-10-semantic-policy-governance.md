# P2 Small — Semantic Policy Governance Plan

1. Lock lifecycle, exact-version resolver, checksum and pack-authority tests.
2. Add immutable in-memory and SQL policy repositories with lifecycle audit.
3. Add nullable role binding fields and forward-only migration `20260810_23`.
4. Validate explicit policy references during role-profile approval/binding.
5. Resolve current/future target policies independently and snapshot exact
   dependencies in portfolios.
6. Expose only minimal exact-version governance endpoints; never accept a
   client-supplied domain-pack override in capability analysis.
7. Run cross-domain/unit regressions plus the full backend suite, Ruff and
   `git diff --check`.

Out of scope: ontology growth, semantic recall optimization, OFFICIAL analysis,
VERIFIED capability, final competency decisions, learning paths, UI, automatic
domain detection, and implicit historical IT backfill.
