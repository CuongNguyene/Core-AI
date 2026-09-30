# Provider Classification and Privacy Routing TDD Plan

**Goal:** Make provider identity reflect physical locality and prevent restricted CV/JD payloads from being routed to an external provider.

**Implemented contract:**

- Canonical model configuration uses `MODEL_PROVIDER`, `MODEL_BASE_URL`, `MODEL_API_KEY`, `MODEL_NAME`, `MODEL_TIMEOUT_SECONDS`, `MODEL_MAX_RETRIES`, and `MODEL_MAX_TOKENS`.
- `local-vllm` identifies an organization-controlled endpoint.
- `vilao-external` identifies an external OpenAI-compatible endpoint.
- Restricted inference requested for an external provider is denied.
- External routing requires `ALLOW_EXTERNAL_SANITIZED`, explicit external enablement, and an identifiable external provider route.
- Existing extraction orchestration and accepted profiles are unchanged.

## TDD coverage

- Provider factory classifies Vilao and local OpenAI-compatible endpoints by explicit provider ID.
- Provider registry preserves local and external identities separately.
- Restricted data cannot route externally, even with an external request.
- External requests without sanitized privacy approval are denied.
- Explicitly approved sanitized external requests route to `vilao-external`.
- Canonical `MODEL_*` environment names populate existing Settings fields without breaking Python call sites.

## Runtime boundary

The current backend process is not restarted by this change. Before a restart, inject `MODEL_API_KEY` through the runtime secret mechanism. With `MODEL_PROVIDER=vilao-external` and `EXTERNAL_AI_ENABLED=false`, raw CV/JD extraction remains fail-closed instead of silently sending restricted content to Vilao.

## Verification

`305 passed`; Ruff clean; `git diff --check` clean.
