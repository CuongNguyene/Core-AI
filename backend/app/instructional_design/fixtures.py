"""Small, explicitly authored fixtures for instructional-design research only."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_SCHEMA_VERSION,
    LESSON_PLANNING_SCHEMA_ID,
    OBJECTIVE_DESIGN_SCHEMA_ID,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
)
from app.instructional_design.orchestrator import build_research_snapshot
from app.instructional_design.schemas import (
    ArtifactProvenance,
    ArtifactSource,
    AssessmentSpec,
    AssessmentTaskSpec,
    CognitiveProcess,
    CourseOutline,
    EvidenceCriterion,
    GenerationProvenance,
    InstructionalDesignResearchSnapshot,
    InstructionalPattern,
    KnowledgeDimension,
    LearnerState,
    LearningObjectiveSpec,
    LessonSpec,
    ModuleOutline,
    PrerequisiteSpec,
    ResearchBriefProvenance,
    ResearchCapability,
    ResearchConstraints,
    ResearchLearningBrief,
)


class CrossDomainDomain(StrEnum):
    IT_AI = "it_ai"
    ACCOUNTING = "accounting"
    LEGAL_COMPLIANCE = "legal_compliance"
    HR_MANAGEMENT = "hr_management"
    CONSTRUCTION_ENGINEERING = "construction_engineering"


class CrossDomainIndustryFamily(StrEnum):
    TECHNOLOGY = "technology"
    FINANCE = "finance"
    LEGAL_SERVICES = "legal_services"
    HUMAN_RESOURCES = "human_resources"
    CONSTRUCTION = "construction"


class CrossDomainLearningType(StrEnum):
    PROCEDURAL_TECHNICAL_SKILL = "procedural_technical_skill"
    REGULATED_PROFESSIONAL_SKILL = "regulated_professional_skill"
    ANALYTICAL_JUDGMENT_SKILL = "analytical_judgment_skill"
    SCENARIO_BASED_PROFESSIONAL_SKILL = "scenario_based_professional_skill"
    PROCEDURAL_SAFETY_SKILL = "procedural_safety_skill"


class CrossDomainDifficulty(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"


class CrossDomainFixtureMetadata(BaseModel):
    """Controlled experiment labels; not an instructional-design ontology."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fixture_id: str = Field(min_length=1)
    domain: CrossDomainDomain
    industry_family: CrossDomainIndustryFamily
    learning_type: CrossDomainLearningType
    difficulty: CrossDomainDifficulty
    description: str = Field(min_length=1)


class CrossDomainFixture(BaseModel):
    """Input-only fixture: metadata plus a ResearchLearningBrief, never output artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    metadata: CrossDomainFixtureMetadata
    brief: ResearchLearningBrief


def _cross_domain_fixture(
    *,
    fixture_id: str,
    domain: CrossDomainDomain,
    industry_family: CrossDomainIndustryFamily,
    learning_type: CrossDomainLearningType,
    difficulty: CrossDomainDifficulty,
    description: str,
    capability_name: str,
    performance: str,
) -> CrossDomainFixture:
    brief = ResearchLearningBrief(
        id=f"brief-{fixture_id}",
        capability=ResearchCapability(name=capability_name, target_context="cross-domain research fixture"),
        learner_state=LearnerState(
            known=[],
            unknown=[],
            evidence_refs=[f"cross-domain-fixture:{fixture_id}:learner-state"],
        ),
        desired_performances=[performance],
        constraints=ResearchConstraints(estimated_total_minutes=60, language="en"),
        provenance=ResearchBriefProvenance(authored_by="instructional-design-research"),
    )
    return CrossDomainFixture(
        metadata=CrossDomainFixtureMetadata(
            fixture_id=fixture_id,
            domain=domain,
            industry_family=industry_family,
            learning_type=learning_type,
            difficulty=difficulty,
            description=description,
        ),
        brief=brief,
    )


def cross_domain_validation_fixtures() -> dict[str, CrossDomainFixture]:
    """Return five clean brief-only fixtures for ID-03A; no provider execution."""

    return {
        "python_data_processing": _cross_domain_fixture(
            fixture_id="python_data_processing",
            domain=CrossDomainDomain.IT_AI,
            industry_family=CrossDomainIndustryFamily.TECHNOLOGY,
            learning_type=CrossDomainLearningType.PROCEDURAL_TECHNICAL_SKILL,
            difficulty=CrossDomainDifficulty.MEDIUM,
            description="A learner transforms and validates tabular data with Python.",
            capability_name="python data processing",
            performance="Given a tabular dataset, transform invalid values and justify the choices.",
        ),
        "accounting_financial_reporting_basic": _cross_domain_fixture(
            fixture_id="accounting_financial_reporting_basic",
            domain=CrossDomainDomain.ACCOUNTING,
            industry_family=CrossDomainIndustryFamily.FINANCE,
            learning_type=CrossDomainLearningType.REGULATED_PROFESSIONAL_SKILL,
            difficulty=CrossDomainDifficulty.MEDIUM,
            description="An entry-level accountant prepares basic reports and identifies discrepancies.",
            capability_name="basic financial reporting",
            performance="Given a small ledger, prepare a basic financial report and identify common discrepancies.",
        ),
        "legal_contract_review_basic": _cross_domain_fixture(
            fixture_id="legal_contract_review_basic",
            domain=CrossDomainDomain.LEGAL_COMPLIANCE,
            industry_family=CrossDomainIndustryFamily.LEGAL_SERVICES,
            learning_type=CrossDomainLearningType.ANALYTICAL_JUDGMENT_SKILL,
            difficulty=CrossDomainDifficulty.HIGH,
            description="A junior legal specialist reviews a commercial contract for potential risks.",
            capability_name="basic commercial contract review",
            performance="Given a commercial contract clause, identify potential risks and explain the reasoning without issuing a final legal judgment.",
        ),
        "hr_recruitment_planning_basic": _cross_domain_fixture(
            fixture_id="hr_recruitment_planning_basic",
            domain=CrossDomainDomain.HR_MANAGEMENT,
            industry_family=CrossDomainIndustryFamily.HUMAN_RESOURCES,
            learning_type=CrossDomainLearningType.SCENARIO_BASED_PROFESSIONAL_SKILL,
            difficulty=CrossDomainDifficulty.MEDIUM,
            description="An HR employee creates a recruitment plan for a department.",
            capability_name="basic recruitment planning",
            performance="Given a department hiring scenario, create a recruitment plan and justify the sequencing decisions.",
        ),
        "construction_drawing_and_method_basic": _cross_domain_fixture(
            fixture_id="construction_drawing_and_method_basic",
            domain=CrossDomainDomain.CONSTRUCTION_ENGINEERING,
            industry_family=CrossDomainIndustryFamily.CONSTRUCTION,
            learning_type=CrossDomainLearningType.PROCEDURAL_SAFETY_SKILL,
            difficulty=CrossDomainDifficulty.HIGH,
            description="A junior engineer interprets drawings and prepares a simple construction method proposal.",
            capability_name="basic construction drawing interpretation",
            performance="Given a basic drawing set, interpret the relevant elements and prepare a sequenced method proposal with stated safety considerations.",
        ),
    }


@dataclass(frozen=True)
class ResearchFixtureBundle:
    brief: ResearchLearningBrief
    objectives: tuple[LearningObjectiveSpec, ...]
    assessments: tuple[AssessmentSpec, ...]
    prerequisites: tuple[PrerequisiteSpec, ...]
    course_outline: CourseOutline
    lessons: tuple[LessonSpec, ...]
    snapshot: InstructionalDesignResearchSnapshot


@dataclass(frozen=True)
class ExperimentFixtureFamily:
    capability_name: str
    knowledge_dimension: KnowledgeDimension
    lesson_pattern: InstructionalPattern
    application_performance: str
    analysis_performance: str
    limited_known: tuple[str, ...]
    substantial_known: tuple[str, ...]


_AUTHORED = ArtifactProvenance(source=ArtifactSource.RESEARCHER_AUTHORED)
_GENERATED_AT = datetime(2026, 8, 12, tzinfo=UTC)
_CONTRACT_IDS = (
    OBJECTIVE_DESIGN_SCHEMA_ID,
    ASSESSMENT_DESIGN_SCHEMA_ID,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    LESSON_PLANNING_SCHEMA_ID,
)


def _bundle(
    *,
    fixture_id: str,
    capability_name: str,
    performance: str,
    cognitive_process: CognitiveProcess,
    knowledge_dimension: KnowledgeDimension,
    lesson_pattern: InstructionalPattern,
    learner_known: tuple[str, ...] = (),
    learner_unknown: tuple[str, ...] = (),
) -> ResearchFixtureBundle:
    brief = ResearchLearningBrief(
        id=f"brief-{fixture_id}",
        capability=ResearchCapability(name=capability_name, target_context="research fixture"),
        learner_state=LearnerState(
            known=list(learner_known),
            unknown=list(learner_unknown),
            evidence_refs=[f"research-fixture:{fixture_id}:learner-state"],
        ),
        desired_performances=[performance],
        constraints=ResearchConstraints(estimated_total_minutes=60, language="en"),
        provenance=ResearchBriefProvenance(authored_by="instructional-design-research"),
    )
    objective = LearningObjectiveSpec(
        id=f"objective-{fixture_id}",
        brief_id=brief.id,
        performance=performance,
        cognitive_process=cognitive_process,
        knowledge_dimension=knowledge_dimension,
        success_criteria=["Produces an observable response with a stated rationale."],
        capability_refs=[f"capability-{fixture_id}"],
        provenance=_AUTHORED,
    )
    assessment = AssessmentSpec(
        id=f"assessment-{fixture_id}",
        objective_ids=[objective.id],
        capability_claim=f"Can perform: {performance}",
        required_evidence=[
            EvidenceCriterion(
                id=f"evidence-{fixture_id}",
                criterion="Observable response demonstrates the stated performance.",
            )
        ],
        task=AssessmentTaskSpec(
            task_type="research_scenario",
            description="Complete a supplied scenario and justify the response.",
        ),
        cognitive_process=cognitive_process,
        provenance=_AUTHORED,
    )
    module = ModuleOutline(
        id=f"module-{fixture_id}",
        title=f"Research module: {capability_name}",
        objective_ids=[objective.id],
        lesson_ids=[f"lesson-{fixture_id}"],
        estimated_minutes=60,
    )
    course_outline = CourseOutline(
        id=f"course-{fixture_id}",
        brief_id=brief.id,
        objective_ids=[objective.id],
        modules=[module],
        estimated_minutes=60,
        sequencing_rationale=["Single objective research fixture; no universal order is claimed."],
        provenance=_AUTHORED,
    )
    lesson = LessonSpec(
        id=f"lesson-{fixture_id}",
        module_id=module.id,
        objective_ids=[objective.id],
        lesson_goal=f"Practice: {performance}",
        instructional_pattern=lesson_pattern,
        expected_learner_activity="Respond to a bounded scenario and explain the reasoning.",
        estimated_minutes=60,
        provenance=_AUTHORED,
    )
    provenance = GenerationProvenance(
        research_brief_id=brief.id,
        instructional_design_policy_id="pai_instructional_design",
        instructional_design_policy_version="0.1",
        prompt_versions={
            contract_id: INSTRUCTIONAL_DESIGN_SCHEMA_VERSION for contract_id in _CONTRACT_IDS
        },
        output_schema_versions={
            contract_id: INSTRUCTIONAL_DESIGN_SCHEMA_VERSION for contract_id in _CONTRACT_IDS
        },
        provider="research-fixture",
        model="none",
        model_revision="none",
        generated_at=_GENERATED_AT,
    )
    snapshot = build_research_snapshot(
        brief=brief,
        objectives=[objective],
        assessments=[assessment],
        prerequisites=[],
        course_outline=course_outline,
        lessons=[lesson],
        generation_provenance=provenance,
    )
    return ResearchFixtureBundle(
        brief=brief,
        objectives=(objective,),
        assessments=(assessment,),
        prerequisites=(),
        course_outline=course_outline,
        lessons=(lesson,),
        snapshot=snapshot,
    )


def research_fixture_bundles() -> dict[str, ResearchFixtureBundle]:
    """Return fresh, deterministic domain-diverse fixtures without provider execution."""

    return {
        "model_monitoring": _bundle(
            fixture_id="model-monitoring",
            capability_name="model monitoring response",
            performance=(
                "Given a monitoring dashboard, interpret degradation signals, differentiate "
                "likely causes, and propose a response action."
            ),
            cognitive_process=CognitiveProcess.ANALYZE,
            knowledge_dimension=KnowledgeDimension.PROCEDURAL,
            lesson_pattern=InstructionalPattern.SCENARIO,
        ),
        "python_data_processing": _bundle(
            fixture_id="python-data-processing",
            capability_name="python data processing",
            performance=(
                "Given a tabular dataset, transform missing or invalid values and justify "
                "the transformation choices."
            ),
            cognitive_process=CognitiveProcess.APPLY,
            knowledge_dimension=KnowledgeDimension.PROCEDURAL,
            lesson_pattern=InstructionalPattern.GUIDED_PRACTICE,
            learner_known=("basic Python",),
        ),
        "technical_communication": _bundle(
            fixture_id="technical-communication",
            capability_name="technical communication",
            performance=(
                "Given a complex technical issue and a non-specialist audience, structure an "
                "explanation and adapt terminology to the audience."
            ),
            cognitive_process=CognitiveProcess.APPLY,
            knowledge_dimension=KnowledgeDimension.CONCEPTUAL,
            lesson_pattern=InstructionalPattern.WORKED_EXAMPLE,
        ),
    }


def experiment_fixture_bundles() -> dict[str, ResearchFixtureBundle]:
    """Return 12 explicitly authored fixtures: domain × learner state × performance demand."""

    families = {
        "model-monitoring": ExperimentFixtureFamily(
            capability_name="model monitoring response",
            knowledge_dimension=KnowledgeDimension.PROCEDURAL,
            lesson_pattern=InstructionalPattern.SCENARIO,
            application_performance=(
                "Given a monitoring dashboard, interpret a degradation signal and propose "
                "a justified response action."
            ),
            analysis_performance=(
                "Given monitoring signals over time, differentiate likely degradation causes "
                "and justify a response priority."
            ),
            limited_known=("basic metric interpretation",),
            substantial_known=("basic metric interpretation", "incident response vocabulary"),
        ),
        "python-data-processing": ExperimentFixtureFamily(
            capability_name="python data processing",
            knowledge_dimension=KnowledgeDimension.PROCEDURAL,
            lesson_pattern=InstructionalPattern.GUIDED_PRACTICE,
            application_performance=(
                "Given a tabular dataset, transform missing or invalid values and justify "
                "the transformation choices."
            ),
            analysis_performance=(
                "Given alternative data-cleaning results, evaluate transformation choices and "
                "justify the preferred approach."
            ),
            limited_known=("basic Python",),
            substantial_known=("basic Python", "tabular data transformation"),
        ),
        "technical-communication": ExperimentFixtureFamily(
            capability_name="technical communication",
            knowledge_dimension=KnowledgeDimension.CONCEPTUAL,
            lesson_pattern=InstructionalPattern.WORKED_EXAMPLE,
            application_performance=(
                "Given a complex technical issue and a non-specialist audience, structure an "
                "explanation and adapt terminology to the audience."
            ),
            analysis_performance=(
                "Given stakeholder clarification questions, evaluate an explanation and revise "
                "it to address the audience's misunderstanding."
            ),
            limited_known=("basic written communication",),
            substantial_known=("basic written communication", "audience adaptation"),
        ),
    }
    bundles: dict[str, ResearchFixtureBundle] = {}
    for family_id, family in families.items():
        for learner_state, learner_known in (
            ("limited", family.limited_known),
            ("substantial", family.substantial_known),
        ):
            for variant in ("application", "analysis"):
                fixture_id = f"fixture-{family_id}-{learner_state}-{variant}"
                bundles[fixture_id] = _bundle(
                    fixture_id=fixture_id,
                    capability_name=family.capability_name,
                    performance=(
                        family.application_performance
                        if variant == "application"
                        else family.analysis_performance
                    ),
                    cognitive_process=(
                        CognitiveProcess.APPLY
                        if variant == "application"
                        else CognitiveProcess.ANALYZE
                    ),
                    knowledge_dimension=family.knowledge_dimension,
                    lesson_pattern=family.lesson_pattern,
                    learner_known=learner_known,
                    learner_unknown=(
                        ("additional prior evidence not supplied",)
                        if learner_state == "limited"
                        else ()
                    ),
                )
    return bundles
