# COURSE-REC-01A.2C — SkillsCommons DSpace Provider Adapter

## Scope

This milestone replaces the live SkillsCommons OAI/METS transport with the current public DSpace 9 REST/HAL API. It does not implement semantic enrichment, recommendation ranking, LMS changes, migrations, commits, or pushes.

## 1. Repository

Core-AI: `/Users/mac/Developers/work/LMS/Core-AI`
Branch: `feat/deterministic-ai-course-planning-workspace`
HEAD: `a078526ab7ea38327fdeece142aba325f3de3352`
Working tree: pre-existing COURSE-REC-01A changes plus this provider/docs/evidence work.

LMS: `/Users/mac/Developers/work/LMS/lms`
Branch: `dev`
HEAD: `289174af73ad648a2e42c7d55a2273d815790235`
Working tree: clean and unchanged.

## 2. DSpace Provider

Base URL: `https://library.skillscommons.org/server`
DSpace version: `9.0`
Authentication required: no for the selected public REST/HAL paths
Provider class: `SkillsCommonsCourseProvider`
Provider ref: `skillscommons`

The obsolete OAI/METS path is no longer used by the provider.

## 3. Material Type Contract

Metadata key: `dc.type`

Observed exact values in the bounded raw sample included:

- `Online Course`: 50
- `Online Course Module`: 8
- `Hybrid/Blended Course`: 1
- `Student Support Materials`: 4
- `Reference Material`: 4
- other provider values: 9

Online Course exact match: **YES**

Selection strategy: **BOUNDED_POST_FILTER**

Free-text-only filtering used: **NO**

The free-text query is recall only. Final eligibility uses item metadata `dc.type == "Online Course"`. DSpace server-side exact filter probes returned `400/422`, so they were not used.

## 4. Search / Pagination

Endpoint: `/server/api/discover/search/objects`
Pagination mechanism: `page` and `size`
Max pages: 5
Max raw records: 200
Target full-course sample: 30
Actual full-course sample: 30 processed from 50 exact candidates observed

Actual bounded run saw 80 raw search results across two pages and stopped after reaching the target.

## 5. Identity

Primary provider ID: DSpace item UUID
Handle retained: **YES**
Normalized course ref: `skillscommons:<UUID>`
Stable: **YES**

Titles and handles are not used as primary identity.

## 6. Item Contract

Fields observed:

`uuid`, `name`, `handle`, `metadata`, `lastModified`, `inArchive`, `withdrawn`, `discoverable`, `entityType`, `_links`

DSpace state fields:

- `withdrawn`: all 30 processed exact courses were `false`
- `discoverable`: all 30 were `true`
- `inArchive`: all 30 were `true`
- `lastModified`: present in observed item responses

Strict eligibility excludes withdrawn items, non-discoverable items, and items with `inArchive == false`.

## 7. Bundle Traversal

Items with bundles: 30/30
Bundle names observed: `TEXT`, `THUMBNAIL`, `ORIGINAL`, `LICENSE`, `METADATA`, `SWORD`
Empty bundle cases: supported by deterministic parser/tests; none in the 30 live exact-course items.

## 8. Bitstream Traversal

Items with bitstreams: 30/30
Bitstreams observed: 123 total
MIME/file types observed: `.imscc`, `.zip`, `.pdf`, `.docx`, `.txt`, `.jpg`; DSpace often returned `mimeType = null`, so filename classification was retained as a provider-local fallback.

Large files downloaded: **NO**

## 9. Access Verification

Hosted learning URLs: 30 item URI values were observed, but the legacy `www.skillscommons.org` URI path was not usable from this runtime and was classified `UNKNOWN`; no hosted courseware was promoted from that path.

Verified hosted: 0
Restricted hosted: 0
Broken hosted: 0
Unknown hosted: 30

Verified bitstreams: 118
Restricted bitstreams: 5
Broken bitstreams: 0
Unknown bitstreams: 0

Bitstream access used bounded `HEAD`, with a maximum 32 KiB Range-GET fallback. No content body was downloaded beyond the bounded verifier.

## 10. Learning Access Classification

| Classification | Count |
|---|---:|
| `HOSTED_COURSEWARE` | 0 |
| `DOWNLOADABLE_COURSE_PACKAGE` | 27 |
| `DOWNLOADABLE_MATERIALS` | 3 |
| `RESTRICTED` | 0 |
| `BROKEN` | 0 |
| `UNKNOWN` | 0 |

An `.imscc` export or explicit package indicator is treated as a complete package. A generic ZIP without package evidence remains materials-only.

## 11. Strict Provider Pool

Exact full-course candidates processed: 30
Strict provider candidates: 27
Observed verified yield in sample: `27 / 30 = 0.90`

Rule:

```text
material_type == FULL_COURSE
AND withdrawn != true
AND discoverable != false
AND inArchive != false
AND learning_access in {HOSTED_COURSEWARE, DOWNLOADABLE_COURSE_PACKAGE}
```

This is an observed bounded sample yield, not a population-wide SkillsCommons rate.

## 12. Example Verified Full Course

Provider ID: `4f3652e5-82d3-4a78-9b02-73126bb86bc9`
Handle: `taaccct/13001`
Title: `BA 177 - Payroll Accounting Online`
Material type: `Online Course`
Learning access: `DOWNLOADABLE_COURSE_PACKAGE`
Availability: `available`
License: `CC BY`
Access URL: public DSpace bitstream content link
Bitstream count: 8
Capabilities count: 0
Target level: `null`
Prerequisites count: 0

## 13. Example Materials-Only Course

Provider ID: `4ad1ea9b-e45e-4498-88e6-2c5cbd36602a`
Title: `QMS 101`
Reason not strict candidate: accessible files did not carry explicit complete-course package evidence
Learning access: `DOWNLOADABLE_MATERIALS`

## 14. Example Failed / Unknown Course

Provider ID: `4f3652e5-82d3-4a78-9b02-73126bb86bc9`
Title: `BA 177 - Payroll Accounting Online`
Failure reason: legacy metadata URI on `www.skillscommons.org` could not be verified from this runtime
Classification: `UNKNOWN` for hosted URI; DSpace package paths remained verified and the course qualified through `DOWNLOADABLE_COURSE_PACKAGE`.

No exact full-course item failed item/bundle/bitstream parsing in the bounded 30-item sample.

## 15. Capability Boundary

Subject → capability: **NO**
Occupation → capability: **NO**
Industry → capability: **NO**
Title/description inference: **NO**
Provider capability count: **0**

## 16. Target Level

Provider level mapped to Core `target_level`: **NO**
Unsafe inference: **NO**

Raw provider metadata is not promoted into the governed capability profile.

## 17. Prerequisites

Structured prerequisite source found: **NO**
Inferred from text: **NO**

Normalized prerequisites remain empty.

## 18. ExternalCourse Compatibility

Compatible: **YES**

Changes required: adapter-local DSpace parsing and provenance only. Canonical `ExternalCourse` schema changes were not required.

## 19. NormalizedCourseCandidate Compatibility

Compatible: **YES**

Changes required: none to the canonical schema. Provider emits external identity, `skillscommons:<UUID>`, empty capabilities, null target level, and empty prerequisites.

## 20. Security

TLS verification: **PASS**
SSRF protection: **PASS**
Redirect SSRF: **PASS**
Large responses bounded: **PASS**
Binary downloads avoided: **PASS**
Secret scan: **PASS**

The trusted DSpace API host is allowlisted. External URLs use public-IP resolution and redirect re-validation. No credentials were added.

## 21. Provider Regression

MockExternalProvider: **PASS**
OpenEdxCourseProvider: **PASS**
Legacy SkillsCommons fixtures: **RETIRED**

The live provider no longer calls OAI/METS.

## 22. Tests

SkillsCommons provider tests:

```text
uv run pytest tests/test_course_catalog_skillscommons.py -q
13 passed
```

Course catalog regression:

```text
uv run pytest tests/test_course_catalog_*.py -q
54 passed
```

## 23. Static Checks

Ruff format: **PASS**
Ruff: **PASS**
mypy: **PASS** for `app/course_catalog`
JSON validation: **PASS** for evidence files
`git diff --check`: **PASS**
Secret scan: **PASS**

## 24. Files Changed

PROVIDER: `services/pai-backend/backend/app/course_catalog/skillscommons.py`
SCHEMAS: none
SETTINGS: none
TESTS: `services/pai-backend/backend/tests/test_course_catalog_skillscommons.py`
FIXTURES: sanitized inline HAL fixtures in focused tests
DOCS: this report
EVIDENCE: `test/results/course-rec-01a-2c/`
LMS: **NONE**

## 25. Empirical Conclusion

Can SkillsCommons provide exact full-course records? **YES**
Can PAI retrieve those records through DSpace REST? **YES**
Can PAI traverse bundles/bitstreams? **YES**
Can PAI verify hosted/downloadable access? **YES, downloadable access verified**
Can PAI distinguish complete package from materials-only? **YES**

## 26. Sample Limitation

Sampling strategy: bounded free-text `Online Course` recall, exact `dc.type` post-filter, maximum 5 pages/200 raw results, stopped at 30 processed exact courses.

Representative of full catalog: **NO**
Population-wide claims made: **NO**

## 27. Remaining Gap Before Semantic Enrichment

No provider-contract blocker remains for the 27 strict downloadable-course candidates. Hosted-course URL verification remains unavailable for the legacy URI values from this runtime, but is not required for the verified downloadable package path.

Semantic enrichment is still a separate next milestone because provider candidates intentionally have `capabilities = []`.

## 28. Recommendation Engine Readiness

Can COURSE-REC-01B proceed independently: **YES**
Can SkillsCommons participate in real capability-based recommendation now: **NO**

Reason: semantic enrichment must first create governed `CourseCapabilityProfile` data. The provider adapter does not infer capabilities.

## 29. Final Decision

SkillsCommons DSpace provider usable: **YES**
Real external full-course pool validated: **YES**
Semantic enrichment required: **YES**
Decision: `READY_FOR_SKILLSCOMMONS_SEMANTIC_ENRICHMENT`

## 30. Git Status

Core-AI: existing pre-work changes plus this provider, tests, docs, script, and evidence; no commit.
LMS: clean and unchanged.

No migration, commit, or push was performed.

STOP.
