# JD-DEMO-03A.2B — LLM-as-Judge Semantic Evaluation

## Status

JD-DEMO-03A.2B NEEDS_ITERATION

The evaluator is ready, but semantic judging did not run. The configured Vilao
endpoint returned `401 Unauthorized` on both the initial request and the one
format-retry request for the first packet. No packet score, requirement
judgment, aggregate score, or decision gate was fabricated.

## Judge configuration

- Provider: `vilao-external`
- Model: `claude-sonnet-5`
- Rubric: `jd_semantic_judge@0.1`
- Judge independence: independent configuration relative to the extractor
- Packets discovered: 10
- Successful judge calls: 0
- Provider attempts before stop: 2

## Input verification

- 10 source DOCX files discovered and checksum-verified.
- 10 `JDRequirementExtractionOutputV2.json` files discovered.
- 67 extracted requirements discovered.
- 67 text-span locators discovered in the supplied manifest.
- All runtime review states remain `pending_review`.
- Profiles accepted: 0.
- Profiles modified: 0.

## Verification

- Evaluator tests: 4 passed.
- Output-contract tests: covered by the evaluator tests; no live judge output existed to validate.
- Ruff: passed with cache disabled.
- Scoped mypy: passed with backend imports skipped; the full file run otherwise reaches unrelated pre-existing backend errors.
- Compileall: passed.
- `git diff --check`: passed for the checkout's tracked diff.

## Resume

Set `JUDGE_API_KEY` (or the existing provider credential variable) for the
configured Vilao provider, then run:

```bash
UV_CACHE_DIR=/private/tmp/ct_brain_hub-uv-cache uv run --locked --extra dev python \
  evaluation/jd-demo-03a.2b/judge_runner.py
```

The runner will then create `packets/*.judge.json`, `aggregate.json`, and
replace this report with the source-grounded aggregate report.
