# COURSE-REC-01A.3B — SEMANTIC ENRICHMENT VALIDITY & TAXONOMY FITNESS AUDIT

## Status

COMPLETE

Audit completion is separate from approval of the existing semantic drafts. Taxonomy fitness is partial; the two previous accepted mappings are not equally supported. Production code, taxonomy, previous experiment evidence and LMS remain unchanged.

## 1. Repository

Core-AI path: /Users/mac/Developers/work/LMS/Core-AI
Branch: feat/deterministic-ai-course-planning-workspace
HEAD: a078526ab7ea38327fdeece142aba325f3de3352
Working tree: dirty before audit; preserved.
Pre-existing changes: three tracked changes (.env.example, app/shared/config.py, tests/test_settings.py); untracked COURSE-REC catalog/recommendation code, scripts, tests, docs, evidence, graphify-out, and earlier integration verification evidence. Exact status is in preflight.json.

LMS path: /Users/mac/Developers/work/LMS/lms
Branch: feat/learning-operations-phase-1
HEAD: 129fde12a3856eb07a8690ab0ebac528b2f26e61
Working tree: clean.

The historical 01A.3 report's LMS dev branch/HEAD is not the current checkout. This audit records the current checkout independently.

Production code changed: NO.

Paths beginning app/, scripts/ or tests/ below are relative to services/pai-backend/backend/. Audit reasoning uses local repository evidence and the existing copied provider metadata. No live provider metadata was re-fetched.

## 2. 01A.3 Evidence Boundary

Real SkillsCommons records: YES, as recorded by the earlier provider verification.
Real metadata: YES, selected/copied fields in sample-manifest.json.
Full course semantics inspected: NO.

| Artifact / field | Boundary | Qualification |
|---|---|---|
| Sample UUID, handle, title, source_metadata and DSpace state | REAL_PROVIDER_SOURCE | Sanitized/copied metadata; not original HTTP responses |
| Bundle and bitstream names/types | REAL_PROVIDER_SOURCE | Copied earlier provider metadata; no binary content |
| Sample selection, categories, strict eligibility | EXPERIMENT_DERIVED | Authored strata and provider-policy decisions |
| Four refs, strengths, excerpts and confidence values | MANUAL_SEMANTIC_JUDGMENT | Hard-coded script annotations; ellipses alter literal excerpt text |
| Review outcomes/rationales | MANUAL_SEMANTIC_JUDGMENT | Authored experiment decisions; independent reviewer identity UNKNOWN |
| Two DRAFT profiles | EXPERIMENT_DERIVED | Code-generated from authored accept decisions |
| Coverage arithmetic | EXPERIMENT_DERIVED | Correct arithmetic over four proposals; not exhaustive semantic recall |
| Sufficiency counts, ambiguity rate, MEDIUM effort | MANUAL_SEMANTIC_JUDGMENT | Hard-coded; no per-course review log or timing measurement |
| Provider regression result labels | EXPERIMENT_DERIVED | Recorded previous execution, not rerun in this audit |
| Enrichment unit-test course/evidence | TEST_FIXTURE | Synthetic project-management title; UUID is payroll in live sample |
| Named independent SME/human adjudication | UNKNOWN | No reviewer ID, timestamp or approval record |

All 12 previous experiment JSON files, its report, implementation, tests and both sample/experiment scripts were inspected. The script labels mappings GOVERNED_EXACT_MAPPING, but does not resolve a separately approved exact mapping registry. Confidence 0.98 and 0.35 is assigned from decisions, not measured.

The old report says 20 semantic tests; the current semantic test file contains eight unparametrized test functions. This is a documentation/evidence discrepancy, not a fresh test-failure claim. provider-regression.json separately records 62 catalog tests. Historical execution counts were not re-certified here.

Key boundary conclusion: live provider metadata and traceable generated drafts are established; independent semantic truth and full-course development coverage are not.

## 3. Canonical Taxonomy

Taxonomy: professional_capability_core@0.1
Source file: app/extraction/capability_taxonomy.py

Original intended purpose: immutable bounded professional capability families for CV fact-to-capability selection and evaluation.

Repository evidence:

- capability_taxonomy.py:1 explicitly calls it an evaluation-only CV extraction taxonomy.
- capability_taxonomy.py:122 registers CV taxonomy selection over grounded statement IDs.
- scripts/ext_03a6_bounded_taxonomy.py:1 and its EXT-03A.6 evaluation bind CV facts to this taxonomy.
- scripts/ext_03a7_multi_cv_taxonomy.py:1 and EXT-03A.7 results evaluate seven CVs across domains.
- app/extraction/worker.py imports selection/discovery; app/extraction/two_stage_composer.py uses the taxonomy in the CV pipeline.
- app/extraction/capability_discovery.py:112 calls it a mapping reference and allows grounded unmapped discoveries.
- app/course_catalog/semantic_enrichment.py:99 reuses it locally for this experiment.

The backend was imported through subtree commit d4bfab8; the canonical repository does not establish original upstream authorship intent beyond these source/evaluation artifacts.

Origin in JD/role normalization: not established; JD/role semantics use independent requirements and policies.
General competency ontology intent: NOT_ESTABLISHED.
Explicitly intended for CourseCapabilityProfile: NOT_ESTABLISHED as a general governed vocabulary. The experiment chooses it; the base course contract does not mandate it.

## 4. Taxonomy Governance

| Dimension | Classification | Evidence |
|---|---|---|
| Owner | ABSENT | No declared taxonomy owner/approval authority found |
| Lifecycle | ABSENT | No taxonomy draft/active/deprecated states |
| Versioning | EXPLICIT | Immutable models, static ID/version and exact lookup |
| Approval semantics | ABSENT | Evaluation validation is not release approval |
| Domain scope | IMPLICIT | Business, commerce, operational and professional families |
| Extension policy | ABSENT | Classification labels exist; extension workflow does not |
| Alias policy | IMPLICIT | Alias strings and exact normalized mapping exist; approval rules absent |
| Hierarchy/parent-child | ABSENT | No hierarchy fields/edges or subsumption rules |
| Granularity definition | ABSENT | No formal family/skill/topic distinction |
| Deprecation policy | ABSENT | No migration/deprecation contract |
| Mapping policy | EXPLICIT | CV exact name/alias mapping and grounded unmapped status |
| Domain-pack support | ABSENT | No pack binding for this taxonomy |
| Semantic-policy integration | ABSENT | No binding to the extraction/course taxonomy |

ABSENT means not found in the inspected repository evidence, not a claim about undocumented organizational practice.

ADR-0019 and ADR-0020 establish separate role-assessment SemanticPolicy and DomainKnowledgePack governance. Exact versions, lifecycle and checksums there must not be attributed to this extraction taxonomy.

Governance maturity: adequate as a bounded versioned extraction reference; insufficient to designate a general enterprise course capability vocabulary.

## 5. Taxonomy Granularity

Observed semantic levels: broad professional capability families, domain operating/delivery families, operational functional families and people/team behaviors.
Consistency: MIXED.

Examples:

- project_management: planning, coordinating, executing and delivering projects.
- digital_platform_development: designing/developing/delivering platforms, systems and technical product capabilities.
- order_management: order lifecycle and fulfillment coordination.
- ecommerce: operating/delivering commerce through electronic channels.
- team_leadership: leading, coordinating, mentoring or managing people/team delivery.

All 11 entries have descriptions, but there is no formal hierarchy or course-outcome granularity rule. Mixed scope cannot establish a formal broader/narrower relationship or prove a TAXONOMY_GRANULARITY_GAP.

## 6. CourseCapabilityProfile Semantics

Repository-supported definition: core semantic profile describing what a course develops, expressed through explicit direct/supporting coverage claims with mandatory provenance.

Capabilities represent: evidence-supported development/coverage claims, not learner verification and not automatically any topic mentioned in the description.
Explicit contract: YES.

Evidence: app/course_catalog/schemas.py:1, :45 and :111; COURSE-REC-01A-CATALOG-CAPABILITY-CONTRACT.md capability coverage section.

The contract uses opaque capability_ref strings. It requires non-empty coverage/provenance and unique profile entries; it does not enforce a global taxonomy, approved aliases, ontology version or topic-to-developed-capability rule. DRAFT controls lifecycle eligibility, not semantic correctness.

## 7. Capability Identity Alignment

| Object | Actual identity | Classification |
|---|---|---|
| CandidateProfile | Evidence-backed entity/skill labels; no required taxonomy ref | PARTIALLY_SHARED |
| RoleCompetencyProfile | Authored RoleRequirement.id and evidence_terms, separate semantic policy | NOT_ESTABLISHED for this taxonomy |
| CapabilityGapProfile | Role requirement_id plus candidate evidence refs | PARTIALLY_SHARED |
| LearningNeedProfile | competency.id copied from requirement.id | PARTIALLY_SHARED |
| LearningPath | Analysis path preserves need competency; legacy path uses gap_id | PARTIALLY_SHARED |
| CourseCapabilityProfile | Opaque capability_ref; only experiment restricts to taxonomy raw IDs | PARTIALLY_SHARED |

Classification: PARTIALLY_SHARED.

Exact target/course capability identity is explicitly intentional at the 01B engine boundary: app/course_recommendation/engine.py:123 intersects exact strings. End-to-end alignment across all six objects is not established.

Concrete mismatch evidence: catalog fixtures use capability:python; recommendation tests use cap:python; SkillsCommons experiment uses project_management; role/need contracts use requirement IDs. These are examples from different contracts/fixtures, not newly created capabilities. No automatic equivalence is permitted.

Sources: app/matching/schemas.py:95/:124; app/capability_analysis/schemas.py:238; app/learning_need_profile/projection.py; app/learning/mapper.py:41; app/learning/service.py:440; app/course_catalog/fixtures.py:58.

## 8. Existing Claim Re-Audit

| Course | Capability Ref | Original Outcome | Audit Outcome | Evidence Assessment |
|---|---|---|---|---|
| MAN2582 Introduction to Project Management | project_management | ACCEPT | SUPPORTED | Explicit objective to use project-management techniques |
| PHT1007 Topics in Physical Therapy | team_leadership | ACCEPT | AMBIGUOUS | Leadership/teams presented as topics; developed team-leadership behavior not established |
| COP1510 Programming Concepts I | digital_platform_development | REJECT | UNSUPPORTED | Introductory programming content does not establish system/platform development capability |
| EGS1000 Professional Performance for the Technician | team_leadership | REJECT | UNSUPPORTED | Interpersonal/professional topics do not establish leading a team |

All four full abstracts were compared against existing capability descriptions. Source UUID locators and exact supporting passages are in existing-claim-reaudit.json. Audit annotations are new reasoning, not changes to old review outcomes/profiles.

The physical-therapy DIRECT claim is not independently justified by the metadata. Keep it experimental; this milestone does not edit it. Its current DRAFT status prevents 01B eligibility.

## 9. Positive Control

Course: MAN2582 Introduction to Project Management
Capability: project_management
Mapping still supported: YES.

The source says it prepares students to use project-management techniques in the workplace. This is compatible with the defined planning/delivery family. No stronger proficiency, verified learner capability or comprehensive mastery is implied.

## 10. Negative Control

Course: COP1510 Programming Concepts I
Rejected capability: digital_platform_development
Rejection still supported: YES.

The source names introductory algorithms, APIs, debugging/testing and OOP. The taxonomy describes design/development/delivery of platforms or software systems. Its software-development alias gives conceptual overlap, but neither the abstract nor an approved equivalence establishes the claimed developed capability.

Conservative conclusion: UNSUPPORTED_MAPPING for this proposed claim, not a formal hierarchy/granularity gap.
Alternative capability searched: NO.

## 11. Zero-Coverage Source Semantics

SOURCE_SEMANTICS_CLEAR: 9
SOURCE_SEMANTICS_PARTIAL: 4
SOURCE_SEMANTICS_INSUFFICIENT: 0
Total: 13.

| Course | Classification | Source basis |
|---|---|---|
| BA 177 Payroll Accounting | CLEAR | Explicit payroll tax computation outcomes |
| General Education MOOC | PARTIAL | Broad reading/English/math; specific competencies not listed |
| Canvas Orientation | PARTIAL | Generic successful-online-student description/tags |
| PRN0020 Human Development | CLEAR | Lifespan development/stages explicitly presented |
| PRN0070 Basic Nutrition | CLEAR | Nutrition principles and diet therapy explicitly presented |
| CTS1131 Hardware Configuration | CLEAR | Hands-on hardware content and certification preparation |
| COP1510 Programming Concepts I | CLEAR | Concrete programming fundamentals and techniques |
| HCP0796 Patient Care Technician | PARTIAL | Generic clinical organizational/management skills |
| PTN0086 Pharmacy Technician III | CLEAR | Drug preparation/dispensing plus pharmacy practicum |
| DES1051C Pain Management | CLEAR | Dental pain/anxiety relief and local anesthesia |
| EGS1000 Professional Performance | PARTIAL | Broad professional topics without developed behaviors |
| CGS1560 Operating Systems | CLEAR | OS concepts/components/usage and hands-on activities |
| HIM1253 Medical Coding | CLEAR | CPT-4/ICD-9-CM coding and practice |

CLEAR means concrete content or outcomes at metadata resolution. It does not certify learner outcomes, full syllabus content or proficiency. Only source sufficiency was classified; no new capability mappings were created.

## 12. Taxonomy Representation Check

Only SOURCE_SEMANTICS_CLEAR courses evaluated: YES, nine from the original zero-coverage set.
EXACT_CANONICAL_MATCH: 0
NO_CANONICAL_MATCH: 9
NOT_ENOUGH_EVIDENCE_TO_ASSESS: 0
Nearest/fuzzy matching used: NO.

Each concrete source topic was compared against all 11 definitions and declared aliases. No exact/governed equivalent represents the listed payroll, nutrition, lifespan-development, hardware, programming-fundamentals, pharmacy, dental anesthesia, OS or medical-coding semantics.

These are source topics being checked, not proposed new capability IDs. Absence of an equivalent does not prove that the full course develops no other professional capability.

## 13. Taxonomy Gap Claims

Strong taxonomy coverage gaps proven: nine concrete source semantics have no equivalent representation in this bounded vocabulary on the inspected sample.
Strong taxonomy granularity gaps proven: NONE.
Unresolved taxonomy-scope questions: whether/how professional families represent course topics/outcomes; who governs mapping; how requirement IDs connect to course refs; applicable domains.
Any speculative gap relabeled conservatively: YES, NO_CANONICAL_MATCH or TAXONOMY_SCOPE_QUESTION.

The nine checks are not a population-wide SkillsCommons coverage estimate or a mandate to add nine capabilities.

## 14. Taxonomy Fitness

Decision: TAXONOMY_PARTIALLY_FIT.

Project-management coverage is source-compatible; the vocabulary may support a shared professional subset. Many concrete sample semantics are unrepresented, governance does not designate it as a general course ontology, and end-to-end identity is unresolved. Evidence does not justify asserting all course use is incompatible or that redesign is mandatory.

Fitness questions answered independently:

| Question | Finding |
|---|---|
| CandidateProfile valid? | Explicit bounded CV mapping use; not exhaustive candidate semantics |
| RoleCompetencyProfile valid? | Binding to this taxonomy not established |
| Capability gaps valid? | Preserve requirements/context, no mandatory taxonomy binding |
| Explicit general course validity? | Not established beyond experiment-local reuse |
| Broad enough for sampled SkillsCommons domains? | No for nine concrete source semantics; population unknown |
| Compatible granularity? | Positive-control subset compatible; mixed scopes, no formal rule |
| Exact role/course matching intentional? | Engine boundary yes; upstream identity conversion unresolved |
| Main cause of low coverage? | Mixed observed causes; relative causal share not measurable |

## 15. 01A.3 Validity

Decision: VALID_WITH_OVERSTATED_CONCLUSIONS.

Supported conclusions: real copied metadata, four traceable authored proposals, two original accept decisions/two rejections, two schema-valid DRAFT outputs, zero ACTIVE outputs.

Overstated/unsupported conclusions:

- 2/15 measures source sufficiency or exhaustive taxonomy recall.
- The two drafts are equally trustworthy without independent semantic review.
- All 13 zero-coverage cases require package inspection.
- An enum label constitutes a separately approved mapping registry.
- Authored confidence values are calibrated.
- Hard-coded metadata/ambiguity/effort figures are independently measured.

No catastrophic factual bug requiring a code fix was found. These are semantic validity, provenance and documentation limitations; code and old artifacts are unchanged.

## 16. Metadata-Only Coverage Interpretation

Observed 2/15 coverage means: two of 15 sampled course records received authored ACCEPT decisions under this script's chosen vocabulary and four proposals.

What it DOES establish: bounded generated-output coverage and traceability to selected metadata.

What it DOES NOT establish: provider-wide recall, exhaustive mapping, independent semantic accuracy, proportion of insufficient metadata, taxonomy fitness across all domains, or package-parsing yield.

The current audit supports one mapping, marks one ambiguous and preserves both rejections. This does not rewrite the original 2/15 result. The new 9/4 source classification uses a different axis and must not replace historical metrics silently.

## 17. Package Content Research

Decision: PACKAGE_CONTENT_RESEARCH_PREMATURE.

Broad package inspection cannot solve absent governed representations or approve identity mappings. First define applicable vocabulary, development versus topic coverage, review authority and namespace/version relationships.

Eligible cases, if any: future selected objectives in physical therapy might clarify team-leadership development; orientation/patient-care objectives might clarify broad outcomes. They require a later bounded task after semantic rules are settled. No package was downloaded or parsed here.

## 18. Architecture Implications

Current architecture safe: PARTIAL.
Shared capability namespace appropriate: PARTIAL.

The opaque-ref/exact-intersection abstraction is useful; the specific cross-pipeline canonical namespace is not established. ACTIVE-only eligibility contains current experiment risk, but a DRAFT label is insufficient proof of semantic validity.

Risks: silent mismatches between requirement IDs and course refs; unjustified topic-to-development promotion; static CV vocabulary mistaken for approved universal ontology; losing taxonomy/identity provenance when persisting opaque refs.

ADR-0019/0020's policy/pack architecture is relevant as a possible governance model, not proof that the extraction taxonomy already inherits it.

## 19. Architecture Options

| Option | Benefit | Risk | Migration impact | Explainability impact | Recommendation impact |
|---|---|---|---|---|---|
| A: Govern one shared professional capability namespace | Direct exact joins and compatible approved refs | Broad families may omit course-specific semantics; forcing topics would be invalid | Version/reference decisions and explicit reviewed mappings; no silent historical rewrites | Common refs simplify explanation if scope/mapping evidence is retained | Exact engine can remain; caller/profiles must provide approved shared refs |
| B: Preserve course outcomes/topics, map through approved rules to professional refs | Separates what source teaches from professional capability it may develop | Mapping governance/review cost and unsupported projection risk | Separate outcome/provenance representation and versioned mapping would require a later ADR | Source outcome plus mapping evidence explains projection | Engine consumes approved projected refs; no similarity change required |
| C: Explicit versioned domain packs for shared normalization/mapping hints | Reuses existing role-side policy/pack pattern | Present packs are hints, not taxonomy extensions or course approval; domains cannot be inferred | New approved binding/mapping design; existing taxonomy unchanged until authorized | Exact pack/policy refs improve reproducibility | Resolve before target/candidate assembly; no ranking changes now |

These are bounded design options, not selected implementation. Governed broader-taxonomy work is prerequisite design consideration, not authorization to expand the taxonomy.

## 20. COURSE-REC-01B Impact

Decision: ENGINE_VALID_BUT_CATALOG_COVERAGE_LIMITED.

Exact intersection and ACTIVE-only eligibility remain correct for callers supplying governed compatible refs. Taxonomy coverage and unsupported upstream mappings affect candidate supply/meaning; they do not establish an engine algorithm defect. No new test run is claimed.

Recommendation engine code changes required now: NO.

Do not activate the ambiguous physical-therapy draft. Both existing drafts are currently ineligible.

## 21. COURSE-REC-01C Readiness

Can persistence/API work proceed independently: YES_WITH_SEMANTIC_COVERAGE_WARNING.

Mechanical storage/read boundaries can proceed while preserving original identity/provenance and DRAFT status, keeping SkillsCommons enrichment experimental. Do not freeze this extraction taxonomy as universally canonical, auto-approve mappings, or equate requirement IDs with capability refs. A global semantic binding requires a separate governance decision before it becomes API/persistence authority.

01C was not implemented.

## 22. Recommended Next Step

B. Perform taxonomy governance/design work first.

Set ownership, intended domains, identity/version binding, topic/development coverage rules and review authority before broader enrichment or activation.

## 23. Evidence Created

DOCS: docs/research/COURSE-REC-01A-3B-SEMANTIC-VALIDITY-TAXONOMY-FITNESS-AUDIT.md

EVIDENCE: test/results/course-rec-01a-3b/

- preflight.json
- experiment-evidence-boundary.json
- taxonomy-origin-audit.json
- taxonomy-governance-audit.json
- taxonomy-granularity-audit.json
- course-semantics-contract.json
- capability-identity-alignment.json
- existing-claim-reaudit.json
- zero-coverage-source-evidence.json
- taxonomy-representation-check.json
- taxonomy-fitness.json
- package-research-decision.json
- recommendation-engine-impact.json
- summary.json
- validation.json

Production code: NONE.
Tests changed: NONE.
LMS: NONE.

Validation scope: generated JSON and cross-artifact counts/IDs/source excerpts/locators, repository diff checks, and unchanged byte checksums for backend app/tests/scripts, bridge apps and earlier 01A.3 evidence. No broad Ruff/mypy remediation or production tests are required for documentation-only changes. The repository has no discovered Markdown documentation lint configuration for this artifact. Existing lint/type findings were not rerun or reclassified.

Graphify: read-only existing-graph queries located taxonomy/learning relationships; truncated output was not used as authority. Source inspection established findings. No graph rebuilding, result saving or graph mutation was performed.

## 24. Final Decision

Taxonomy fitness: TAXONOMY_PARTIALLY_FIT.
01A.3 validity: VALID_WITH_OVERSTATED_CONCLUSIONS.
Package research readiness: PACKAGE_CONTENT_RESEARCH_PREMATURE.
Recommendation engine impact: ENGINE_VALID_BUT_CATALOG_COVERAGE_LIMITED.
01C readiness: YES_WITH_SEMANTIC_COVERAGE_WARNING.

Overall decision: TAXONOMY_DECISION_REQUIRED for further semantic enrichment/activation. This does not block 01C mechanics under the stated constraints.

## 25. Git Status

Core-AI: pre-existing worktree preserved; only this report and test/results/course-rec-01a-3b/ added by the audit.
LMS: clean, branch/HEAD unchanged.
No commit; no push.

STOP.
