# COURSE-REC-01A.2B — SkillsCommons New-Site Endpoint Discovery

## Scope and result

This bounded investigation verifies the SkillsCommons host migration and identifies a current machine-readable catalog surface. It does not modify the SkillsCommons provider, add scraping, rank courses, enrich capabilities, or touch LMS/Core-AI integration behavior.

Result: `PUBLIC_DATA_ENDPOINT_FOUND`.

The documented legacy OAI/METS routes are unavailable after migration, but the current SkillsCommons Library exposes a public DSpace 9 REST/HAL surface at `https://library.skillscommons.org/server/api`. The endpoint is sufficient for a later adapter investigation; this milestone deliberately does not repoint production code.

## 1. Repository

| Repository | Path | Branch | HEAD |
|---|---|---|---|
| Core-AI | `/Users/mac/Developers/work/LMS/Core-AI` | `feat/deterministic-ai-course-planning-workspace` | `a078526ab7ea38327fdeece142aba325f3de3352` |
| LMS | `/Users/mac/Developers/work/LMS/lms` | `dev` | `289174af73ad648a2e42c7d55a2273d815790235` |

The Core-AI worktree contained pre-existing uncommitted COURSE-REC-01A implementation, research, test, and `graphify-out/` changes. LMS was clean. No unrelated changes were modified.

## 2. Host Migration

From the host network with normal TLS verification:

```text
https://www.skillscommons.org/  -> 301
Location: https://partner.skillscommons.org/
https://partner.skillscommons.org/ -> 200 text/html
```

The partner site is WordPress and links catalog users to `library.skillscommons.org`. TLS verification was enabled; no insecure certificate option was used.

Evidence: `test/results/course-rec-01a-2b/host-redirect-chain.json`.

## 3. Legacy Endpoint Status (OAI Identify, OAI ListRecords, METS, Bitstream)

| Legacy operation | Result | Classification |
|---|---:|---|
| OAI Identify on `www` | 404 HTML | unavailable |
| OAI Identify on `partner` | 404 HTML | unavailable |
| OAI ListRecords on `www` | 404 HTML | unavailable |
| METS `/metadata/handle/taaccct/7823/mets.xml` on `www` | 404 HTML | unavailable |
| METS same path on `partner` | 404 HTML | unavailable |
| Legacy bitstream pattern on `www` | 404 HTML | unavailable |
| Legacy bitstream pattern on `partner` | 404 HTML | unavailable |

The old documentation is therefore operationally stale for the migrated host. The new DSpace API is the migration target observed at runtime, but exact equivalence to the old OAI material-type semantics is not assumed.

Evidence: `test/results/course-rec-01a-2b/legacy-endpoint-status.json`.

## 4. New Site Inventory

`partner.skillscommons.org` is a WordPress navigation/content site. Its catalog links target a DSpace Angular application at `library.skillscommons.org`.

Observed catalog routes include search and browse-by-type, credential, institution, community, occupation, and program. The public Angular configuration identifies DSpace 9.0 and the REST base `https://library.skillscommons.org/server`.

Evidence: `test/results/course-rec-01a-2b/new-site-inventory.json`.

## 5. Frontend Data Loading

The static Angular configuration and public runtime bundle identify REST/HAL loading through `/server/api`. Direct read-only host requests validated the following data path:

```text
config JSON
  -> DSpace REST root
  -> discover/search
  -> item UUID
  -> bundles
  -> bitstreams
  -> public content link
```

The current CUA browser surface did not provide a usable browser tab for a live network-panel trace. This does not block the endpoint finding: the public config, bundle strings, REST root, and direct host requests independently expose the same route structure.

Evidence: `test/results/course-rec-01a-2b/network-endpoint-inventory.json`.

## 6. Candidate Machine-Readable Endpoints

| Candidate | Result | Use |
|---|---:|---|
| `GET /server/api` | 200 HAL | DSpace API discovery and deployment identity |
| `GET /server/api/discover/search/objects?query=*&size=1` | 200 HAL | public catalog search; total 16,988 |
| `GET /server/api/core/items/<UUID>` | 200 HAL | stable item metadata |
| `GET /server/api/core/items/<UUID>/bundles` | 200 HAL | item package/bundle discovery |
| `GET /server/api/core/bundles/<UUID>/bitstreams` | 200 HAL | file metadata and content link |
| `HEAD /server/api/core/bitstreams/<UUID>/content` | 200 | public package access check |
| `GET /server/api/core/items?size=1` | 401 | protected collection listing; not selected |

The selected discovery candidate is the public DSpace REST/HAL graph, not HTML scraping.

## 7. Catalog Fields

The public item response contains stable identity and catalog metadata including `id`, `uuid`, `name`, `handle`, `metadata`, `lastModified`, `inArchive`, `withdrawn`, `discoverable`, and `entityType`. The sampled metadata includes title, abstract, author, dates, publisher, subject, URI, type, license, rights holder, credential type, credit type, delivery format, industry, instructional mode, occupation, project, and secondary type.

The first sample had `dc.type = Program`; the free-text `Online Course` query returned a result whose `dc.type` was `Student Support Materials`. Therefore free-text search is not an exact material-type filter.

## 8. Identity

Each sampled item exposed a stable UUID and handle (`taaccct/7823` for item `033ef675-a2dc-426b-b174-eac304086ec6`). The UUID is the preferred API identity; the handle is retained as provider provenance and a human-facing identifier.

## 9. Pagination

DSpace search responses expose HAL page metadata with `totalElements`, `size`, `number`, and `totalPages`. A bounded one-record page returned `totalElements = 16988`, `size = 1`, `number = 0`, and `totalPages = 16988`. The `Online Course` free-text query reported `7049` results.

Pagination is therefore supported. Exact material-type filtering syntax was not established: bounded `f.dc.type=Online Course,equals` variants returned HTTP 400. No unbounded crawl was attempted.

## 10. Authentication

The REST root, discover search, individual item, bundle, bitstream metadata, and content HEAD checks succeeded anonymously. No cookie, bearer token, API key, or authentication bypass was used. The generic item collection endpoint returned 401 and is treated as protected, not worked around.

## 11. Availability Verification Support

The new endpoint supports a later bounded availability verifier:

- item metadata provides stable identity and metadata;
- HAL links expose bundles and bitstreams;
- bitstream metadata exposes a content URL;
- the sampled content URL returned HTTP 200 with `Accept-Ranges: bytes` and an attachment content disposition;
- no binary package was downloaded during discovery.

This is enough to design a later bounded provider verification pass, while exact course/material selection still needs an explicit contract.

## 12. Current Contract Compatibility

The existing `ExternalCourse` and `NormalizedCourseCandidate` contracts can be populated by an adapter-local DSpace mapping without changing canonical schemas. The existing SkillsCommons provider would need a later bounded transport replacement from OAI/METS to DSpace HAL. It should preserve provider-specific metadata and keep capabilities empty until semantic enrichment.

Required later work is limited to adapter behavior: exact `dc.type` selection, HAL link traversal, package/access verification, and provenance mapping. No provider repoint was performed here.

Evidence: `test/results/course-rec-01a-2b/provider-contract-compatibility.json`.

## 13. Documentation Drift

The public support page `https://support.skillscommons.org/home/discover-reuse/skillscommons-apis/` still advertises keyword search, METS for a specific item, and OAI metadata harvesting. Runtime probes show the documented OAI/METS routes return 404 HTML on both old and partner hosts. This is classified as `DOCUMENTATION_STALE` for the legacy route set.

The DSpace REST surface was found from the current library configuration and runtime API root; it was not treated as officially documented SkillsCommons API guidance.

## 14. Scraping Decision

HTML scraping is not required and is not approved. The partner and library HTML pages are used only to identify the current application and public configuration. Catalog extraction should use the public machine-readable DSpace REST/HAL surface in a later provider task.

## 15. Security

- TLS verification remained enabled.
- No cookies, credentials, bearer tokens, or private data were collected.
- The protected collection endpoint was not bypassed.
- No binary package was downloaded.
- Existing bounded SSRF/access-verification requirements remain applicable to any future adapter.
- No secret or credential was added to source or evidence.

## 16. Evidence

The bounded evidence set is in `test/results/course-rec-01a-2b/`:

- `host-redirect-chain.json`
- `legacy-endpoint-status.json`
- `new-site-inventory.json`
- `network-endpoint-inventory.json`
- `candidate-endpoint-analysis.json`
- `provider-contract-compatibility.json`
- `decision.json`
- `summary.json`

## 17. Files Changed

Production code: none.

LMS: none.

PAI/Core-AI provider: none.

Documentation and evidence: this report and the eight JSON evidence files above.

## 18. Recommendation Impact

`COURSE-REC-01B` can proceed independently as an engine/contract task. The SkillsCommons endpoint discovery is now sufficient to plan a later provider repoint, but the existing legacy provider has not been live-validated against the new API.

Even with a working new endpoint, semantic enrichment remains a separate boundary:

```text
ExternalCourse capabilities=[]
        -> semantic enrichment
        -> CourseCapabilityProfile
```

## 19. Final Decision

- Current legacy API usable: **NO**
- New public machine-readable endpoint found: **YES**
- Provider should be repointed: **YES, in a later bounded task**
- HTML scraper should be built: **NO**
- Milestone status: **PUBLIC_DATA_ENDPOINT_FOUND**

## 20. Recommended Next Step

Create a narrowly scoped follow-up to implement and test a DSpace REST/HAL SkillsCommons adapter. Keep bounded page/record limits, exact material-type selection, stable UUID/handle provenance, public access verification, and SSRF protections. Do not add recommendation ranking, capability enrichment, or LMS changes in that follow-up.

## 21. Git Status

No commit and no push were performed. Existing Core-AI worktree changes were preserved. LMS was not modified.

Evidence was validated with JSON parsing and `git diff --check` after creation.
