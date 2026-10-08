# PAI-JD-SEMANTIC-REQUIREMENT-BREAKDOWN-EVAL-00

Status: `SYNTHETIC_REQUIREMENT_CORPUS_FROZEN_AND_READY` (local synthetic evaluation corpus only; no provider evaluation has started).

## Frozen artifacts

Canonical artifacts are under `backend/evals/job_semantics/requirement_breakdown_eval_00/`:

- `dataset.synthetic.v1.jsonl` — 40 synthetic postings, 301 gold statements.
- `requirement-breakdown-taxonomy.v1.md` and `authoring.protocol.v1.md` — labeling contract and authoring rules.
- `review.pass1.md` and `review.pass2.md` — complete posting/statement review logs. Pass 2 is explicitly `NOT INDEPENDENT HUMAN REVIEW` because it was performed by the same Codex agent.
- `conformance.v1.jsonl` and `conformance.review.v1.md` — 32 executable source-state / semantic fixtures.
- `manifest.synthetic.v1.json` — counts, distributions, all artifact hashes, semantic fingerprint, code HEAD, UTC freeze time, and `provider_calls_before_freeze: 0`.

## Corpus composition

| Dimension | Distribution |
|---|---|
| Domain | Finance/Accounting 8; Software Engineering 8; Data Analytics 6; Recruitment/HR 6; Project Management 6; Business Communication 6 |
| Language | Vietnamese 24; English 10; Mixed 6 |
| Difficulty | Easy 14; Medium 13; Hard 13 |
| Statement type | Responsibility 125; Experience 40; Education 30; Qualification 30; Behavioral 36; Other 40 |
| Capability relevance | Capability-bearing 181; Non-capability 108; Unclear 12 |
| Source field | Job description 168; Job requirements 133 |

Type × relevance and domain × type/relevance matrices are serialized in the manifest for exact review and reproduction. The corpus deliberately does not map statements to canonical capabilities.

Source-state acceptance is within the 40-posting corpus: cases 001–004 represent requirements omitted/null/empty/whitespace; cases 005–006 represent description omitted/null. Their gold statements point only to the surviving non-empty source field. Conformance separately exercises all four states across each source key and outer source object states.

## Review and corrections

Pass 1 covered all 40 postings and 301 statements. Its correction ledger records source-state/provenance changes, coordinated and mixed-clause decomposition, duplicate cross-field evidence, behavior-versus-responsibility adjudication, 12 `UNCLEAR` generic behavior statements, eight routine non-capability responsibilities, and explicit non-inference for age/tool mentions. Pass 2 re-read the corrected corpus and recorded no further corrections. It is same-agent review, not independent human review.

## Conformance and provider boundary

The 32 conformance rows include 3 outer source-object states, 16 per-source-field nullable states, and 13 complete semantic cases. Every semantic case is run through the real `validate_case`; tests also verify HTML text views, source-field crossover, split/keep decisions, non-inference, and exact provider projection. The projection includes only present `job_description_html` / `job_requirements_html`; it excludes `source_application_ref`, `job_posting_url`, statement gold, and fixture metadata. No provider client is imported or called by authoring, validation, conformance, or freezing.

## Freeze identity

See `manifest.synthetic.v1.json` for the authoritative exact values. It binds:

- exact JSONL SHA-256 (physical bytes and line order);
- semantic fingerprint (canonical case/statement/tag ordering plus taxonomy hash);
- taxonomy, protocol, Pass 1, Pass 2, conformance-review, and conformance JSONL hashes;
- validated counts and cross-tab distributions;
- `provider_calls_before_freeze = 0`, current Git HEAD, worktree cleanliness, and UTC timestamp. The checkout is intentionally dirty from pre-existing work and this uncommitted milestone; HEAD identifies the committed base, not a commit containing these artifacts.

Verification command from `services/pai-backend/backend`:

```bash
python -m evals.job_semantics.requirement_breakdown_eval_00.freeze_manifest --verify
UV_CACHE_DIR="$(mktemp -d /private/tmp/pai-jd-breakdown-uv.XXXXXX)" uv run --no-sync pytest tests/test_jd_requirement_breakdown_eval_00.py -q
```

The freeze verifier fails closed on artifact/hash/count/fingerprint mismatch, nonzero provider-call count, or a Git HEAD mismatch. Current focused suite result: 30 passed. Ruff, Ruff format check, and mypy results are recorded in the task handoff; no commit or push was performed.

## Decision

The synthetic corpus is frozen and ready for a separately approved provider evaluation. This status does not claim independent human annotation, model quality, provider performance, or production fitness.
