# COURSE-REC-01A.1 — Open edX External Course Provider Spike

## Scope and decision

This spike adds a bounded, read-only Open edX Courses API adapter for future
course-supply consumers. It does not rank courses, infer capabilities, call a
model, create recommendations, or alter LMS data.

The adapter targets the standard Open edX endpoints:

- `GET /api/courses/v1/courses/`
- `GET /api/courses/v1/courses/{course_key}/`

The repository currently has no approved Open edX base URL or read-only
credential. Therefore the HTTP contract is covered with sanitized local
fixtures and `httpx.MockTransport`; live provider verification remains
blocked until an instance and credential are supplied.

## Configuration

Optional settings are loaded by `app.shared.config.Settings`:

- `OPENEDX_BASE_URL` (empty disables opt-in configuration)
- `OPENEDX_ACCESS_TOKEN` (`SecretStr`, never included in logs/evidence)
- `OPENEDX_TIMEOUT_SECONDS` (default 10, maximum 60)
- `OPENEDX_MAX_PAGES` (default 2, maximum 5)
- `OPENEDX_PAGE_SIZE` (default 50, maximum 100)

The adapter performs no automatic retries. Requests are bounded by the
configured timeout and pagination ceiling.

## Normalization contract

The provider mapping is intentionally conservative:

| Open edX field | ExternalCourse field | Rule |
| --- | --- | --- |
| `course_id` or `id` | `provider_course_id` | Required stable provider identity |
| `name` | `title` | Required; malformed/missing values fail closed |
| `overview`, then `short_description` | `description` | Provider text is preserved; backend does not render HTML |
| `effort` | not mapped | Never converted to fake `duration_minutes` |
| `pacing` | `delivery_mode` | Only known pacing values are mapped |
| `marketing_url` or `course_url` | `course_url` | Optional |
| `start`, `end`, `hidden` | `availability` | `AVAILABLE` only for an explicit active window; otherwise conservative |
| all provider identity fields | provenance | `provider_metadata`, endpoint locator, no token/body persistence |

The normalized candidate uses `course_ref=openedx:<provider_course_id>` and
has `capabilities=[]`, `target_level=None`, and `prerequisites=[]`. An
external provider record is not a Core-AI capability profile. Manual semantic
mapping must happen later before a profile can be activated.

## Error and security boundary

HTTP 401/403/404/429/5xx, timeout, transport failure, invalid JSON, malformed
list/detail shapes, and missing identity/title are returned as safe
`OpenEdxProviderError` messages. Response bodies are not copied into the
error message or evidence. The access token is sent only as an HTTP
`Authorization: Bearer` header when explicitly configured and is absent from
all repository fixtures and reports.

## Verification

Focused provider tests cover list/detail mapping, pagination bounds, minimal
records, HTML overview preservation, effort handling, nullable semantics,
availability cases, provenance, all required negative HTTP cases, malformed
payloads, timeout/transport handling, optional auth headers, and the
provider-only normalized candidate path. Existing mock provider tests remain
in place.

The live smoke was not run because this checkout contains no approved
`OPENEDX_BASE_URL` or credential. See `test/results/course-rec-01a-1/` for
machine-readable evidence.

## Boundary decision

`COURSE-REC-01A.1` is `OPENEDX_ACCESS_BLOCKED`: implementation and mocked
contract verification pass, but actual Open edX API behavior cannot be claimed
without an approved live target. No LMS or recommendation runtime code was
changed.
