# COURSE-REC-01A.2 — SkillsCommons Course Availability Verification Spike

## Scope

This milestone adds a deterministic, bounded SkillsCommons OAI/METS provider
spike. It does not implement recommendation ranking, semantic enrichment,
LLM extraction, persistence, LMS projection, or scheduled synchronization.

The intended flow is:

`OAI ListRecords → material type classification → Online Course filter → METS → public URL/bitstream verification → learning access → ExternalCourse → NormalizedCourseCandidate`

## Access model and live result

SkillsCommons access is unauthenticated. The provider targets:

- `GET https://www.skillscommons.org/oai/request?verb=ListRecords&metadataPrefix=oai_dc`
- `GET https://www.skillscommons.org/oai/request?verb=ListRecords&resumptionToken=...`
- `GET https://www.skillscommons.org/metadata/handle/<handle>/mets.xml`

The host-network live attempt reached the domain, but the root redirected to
`https://partner.skillscommons.org/` and the documented OAI endpoint returned
HTTP 404 HTML rather than OAI-PMH XML. The Python provider additionally hit a
local TLS certificate-chain failure before receiving the endpoint response.
TLS verification was not disabled. No live counts are claimed. Sanitized
deterministic fixtures cover the same parsing and access branches.

Bounds are five OAI pages, 200 raw records, five concurrent course
assessments, finite redirects, and 32 KiB maximum inspected access body. No
course archive is persisted or fully downloaded.

## OAI and METS contracts

OAI records preserve repeated Dublin Core values: identifier, datestamp, title,
creator, subject, description, date, type, identifier, language and publisher.
The OAI resumption token is sent without repeating `metadataPrefix`.

METS parsing preserves title, description/abstract, type, publisher, subject,
language, license, archive, level, industry, occupation, instructional,
`object.uri`, `cw.timeRequired`, and submitted file references.

`taaccct.archive` is normalized according to SkillsCommons semantics:

- `No` means archived.
- `Yes` means not archived under this rule.
- missing/other means unknown.

License classification is independent from accessibility. Known Creative
Commons/Public Domain values are `KNOWN_OPEN`; `Other` is `OTHER`; missing is
`UNKNOWN`.

## Material type and access rules

Exact `dc.type` values determine classification:

- `Online Course` → `ONLINE_COURSE`
- `Hybrid/Blended Course` → `HYBRID_COURSE`
- `Online Course Module` → `COURSE_MODULE`
- recognized instructional resources → `LEARNING_RESOURCE`
- missing/unknown → `UNKNOWN`

Only `ONLINE_COURSE` enters the default full-course assessment pool.

Access verification is separate from catalog availability and license reuse:

- 2xx → `VERIFIED_ACCESSIBLE`
- 401/403 → `RESTRICTED`
- 404/410 → `BROKEN`
- timeout, DNS, connection, 429, 5xx → `UNKNOWN`

Learning access is classified as `ONLINE_COURSE`, `DOWNLOADABLE_COURSE`,
`RESTRICTED`, `BROKEN`, or `UNKNOWN`. Enrollment, completion, certification
and course usability beyond bounded URL/bitstream accessibility are not
claimed.

## Security boundary

OAI/METS XML rejects DTD/entity/system/public constructs before parsing.
Provider bitstreams must be relative `/bitstream/handle/...` paths. Declared
public URLs accept only HTTP(S), reject credentials and non-public IP targets,
and re-check every redirect target. Localhost, loopback, link-local,
RFC1918/private, metadata-service and other non-global addresses are rejected.
HEAD is preferred; GET fallback sends a bounded Range and stops at 32 KiB.

## Canonical contract boundary

Provider-specific assessment data remains in `skillscommons.py`. The existing
`ExternalCourse` and `NormalizedCourseCandidate` contracts remain sufficient;
no new canonical fields or migration were added. `timeRequired` is mapped to
`duration_minutes` only for strict ISO minute/hour or explicit-minute forms.
Subjects, industry, occupation, instructional metadata and `taaccct.level` do
not become capabilities or target level. Provider-only candidates retain
`capabilities=[]`, `target_level=None`, and `prerequisites=[]`.

## Decision

The additive provider implementation and deterministic fixture verification
pass. The milestone remains `LIVE_NETWORK_BLOCKED` because the documented
OAI endpoint did not expose OAI-PMH data from the host network, so no real
SkillsCommons sample could be harvested.
Evidence is in `test/results/course-rec-01a-2/`.
