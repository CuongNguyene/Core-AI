from app.model_gateway.prompts import PromptTemplate

COURSE_GENERATION_PROMPT_ID = "course_content_generation"
COURSE_GENERATION_HISTORICAL_VERSIONS = ("sep-02-v2",)
COURSE_GENERATION_PROMPT_VERSION = "sep-02-v3"
LESSON_GENERATION_PROMPT_ID = "lesson_content_generation"
LESSON_GENERATION_HISTORICAL_VERSIONS = ("sep-02.2-v1",)
LESSON_GENERATION_PROMPT_VERSION = "sep-02.2-v2"
LESSON_REPAIR_PROMPT_ID = "lesson_content_repair"
LESSON_REPAIR_PROMPT_VERSION = "sep-02.2c-v1"
CURRICULUM_PLANNING_PROMPT_ID = "curriculum_planning"
CURRICULUM_PLANNING_HISTORICAL_VERSIONS = ("sep-02.3-v1", "sep-02.3-v2")
CURRICULUM_PLANNING_PROMPT_VERSION = "sep-02.3-v3"
MICROLEARNING_CURRICULUM_PLANNING_PROMPT_VERSION = "sep-08b-v1"


def course_generation_prompt_template() -> PromptTemplate:
    return PromptTemplate(
        template_id=COURSE_GENERATION_PROMPT_ID,
        version=COURSE_GENERATION_PROMPT_VERSION,
        system_instruction=(
            "Generate a substantive self-study draft for SME review, not an outline or "
            "placeholder. Return only the registered JSON object using snake_case keys. "
            "The supplied course_title is the requested course title; set course.title to it "
            "exactly. Do not use output aliases such as course_title, course_description, or a root "
            "objective_refs field. "
            "The root must contain course.title, course.description, and ordered "
            "modules[].lessons[].sections[]. Each section must have type, title, content, "
            "order, and may include steps or success_criteria. Preserve supplied objective "
            "references exactly, including goal-derived references. Use the requested language "
            "and respect duration constraints. Do not write one-sentence sections, shallow "
            "outline prose, generic practice instructions, unsupported citations, invented "
            "capability-gap provenance, or claims of SME approval."
        ),
        user_instruction=(
            "Create a structured course draft with substantive content for every lesson. "
            "Use these section types in instructional order when applicable: introduction, "
            "concept, example, guided_practice, independent_practice, summary. Introduction "
            "must explain why the topic matters, connect it to the course context, and state "
            "the post-lesson learner capability. Concept must include definitions, reasoning, "
            "distinctions, a clear explanation, and key points. Example must include a concrete scenario, worked "
            "example, demonstration, or suitable code example and explain why it works. "
            "Guided practice must include an actual activity, step-by-step guidance, and at least two ordered step strings "
            "in steps, and expected checkpoints. Independent practice must include a task, "
            "context, constraints, deliverable, and at least one explicit success criteria "
            "represented by success_criteria. Summary must provide practical takeaways rather than repeat the opening. "
            "Meet the configured section depth policy; do not pad with repetitive prose. "
            "Use only objective IDs supplied in learning_objectives or generated_objectives. "
            "For every supplied objective, preserve its ID in lesson objective_refs and align "
            "assessment questions to it. Supported questions are multiple_choice with at least "
            "three plausible options and an answer key, or short_answer with expected answer "
            "or grading guidance and objective_refs. Preserve goal-driven origin; never claim "
            "goal-derived objectives came from Capability Analysis. The exact JSON shape is: "
            "{\"course\":{\"title\":\"...\",\"description\":\"...\"},\"modules\":[{"
            "\"title\":\"...\",\"order\":1,\"lessons\":[{\"title\":\"...\","
            "\"order\":1,\"objective_refs\":[],\"sections\":[{\"type\":\"introduction\","
            "\"title\":\"...\",\"content\":\"...\",\"order\":1,\"steps\":[],"
            "\"success_criteria\":[]}]}]}],\"assessment\":null}."
        ),
    )


def lesson_content_generation_prompt_template(
    version: str = LESSON_GENERATION_PROMPT_VERSION,
) -> PromptTemplate:
    if version == "sep-02.2-v1":
        return PromptTemplate(
            template_id=LESSON_GENERATION_PROMPT_ID,
            version=version,
            system_instruction=(
                "Generate one substantive self-study lesson for SME review, not an outline, "
                "summary, or placeholder. Return only the registered JSON object using snake_case "
                "keys. Preserve lesson_ref, title, order, and objective_refs from the lesson plan "
                "exactly. Do not invent capability-gap provenance, citations, or SME approval."
            ),
            user_instruction=(
                "Generate exactly one lesson with lesson_ref, lesson, and optional assessment. "
                "The lesson must contain sections in this order when applicable: introduction, "
                "concept, example, guided_practice, independent_practice, summary. Introduction "
                "must explain why the topic matters, connect it to the course, and state what the "
                "learner can do afterward. Concept must include definitions, reasoning, distinctions, "
                "and key points. Example must include a concrete scenario, worked example, "
                "demonstration, or suitable code example and explain why it works. Guided practice "
                "must be an actual activity with multiple ordered steps in steps and checkpoints. "
                "Independent practice must include context, task, constraints, deliverable, and "
                "explicit success_criteria. Summary must provide practical takeaways without merely "
                "repeating the introduction. Meet the configured section depth policy; do not use "
                "one-sentence sections, generic practice instructions, or repetitive padding. "
                "Use the requested language and duration context. If objective_refs are supplied, "
                "preserve them exactly in the lesson and align every assessment item to them. "
                "Use multiple_choice with at least three plausible options and an answer key, or "
                "short_answer with an expected answer or grading guidance. The exact JSON shape is: "
                "{\"lesson_ref\":\"...\",\"lesson\":{\"title\":\"...\",\"order\":1,"
                "\"objective_refs\":[],\"sections\":[{\"type\":\"introduction\","
                "\"title\":\"...\",\"content\":\"...\",\"order\":1,\"steps\":[],"
                "\"success_criteria\":[]}]},\"assessment\":null}."
            ),
        )
    if version != LESSON_GENERATION_PROMPT_VERSION:
        raise ValueError(f"unsupported lesson generation prompt version: {version}")
    return PromptTemplate(
        template_id=LESSON_GENERATION_PROMPT_ID,
        version=LESSON_GENERATION_PROMPT_VERSION,
        system_instruction=(
            "Generate one substantive self-study lesson for SME review, not an outline, "
            "summary, or placeholder. Return only the registered JSON object using snake_case "
            "keys. Preserve lesson_ref, title, order, and objective_refs from the lesson plan "
            "exactly. Do not invent capability-gap provenance, citations, or SME approval. "
            "Treat the configured section thresholds as minimum quality requirements, not as "
            "an invitation to pad or repeat content."
        ),
        user_instruction=(
            "Generate exactly one lesson with lesson_ref, lesson, and optional assessment. "
            "The lesson must contain sections in this order when applicable: introduction, "
            "concept, example, guided_practice, independent_practice, summary. Introduction "
            "must explain why the topic matters, connect it to the course, and state what the "
            "learner can do afterward. concept must include clear definitions, a conceptual model, "
            "why the concept matters, key distinctions or contrasts, the mechanism of how it works, "
            "a relevant misconception or failure mode, and a direct connection to the lesson objective. "
            "Concept must be substantive enough to satisfy the configured minimum depth without filler. "
            "Example must include a concrete scenario or problem, a worked example, demonstration, "
            "or suitable code example when appropriate, intermediate reasoning, why the solution works, "
            "and a connection back to the concept. Do not require code for non-technical topics. "
            "Guided practice must be an actual activity: content gives setup/context/instructions, "
            "and checkpoints; steps[] contains the actual ordered learner procedure. The combined "
            "instructional payload must satisfy the guided-practice depth requirement. "
            "Independent practice content must provide task context, constraints, and the expected "
            "deliverable; success_criteria[] must contain observable completion criteria. The combined "
            "instructional payload must satisfy the independent-practice depth requirement, without "
            "duplicating the criteria verbatim in content. Summary must include key takeaways, practical "
            "implications, and a learner self-check describing what the learner should now be able to do; "
            "do not turn it into another concept section or repeat the introduction. "
            "Use the requested language and duration context. If objective_refs are supplied, "
            "preserve them exactly in the lesson and align every assessment item to them. "
            "Use multiple_choice with at least three plausible options and an answer key, or "
            "short_answer with an expected answer or grading guidance. The exact JSON shape is: "
            "{\"lesson_ref\":\"...\",\"lesson\":{\"title\":\"...\",\"order\":1,"
            "\"objective_refs\":[],\"sections\":[{\"type\":\"introduction\","
            "\"title\":\"...\",\"content\":\"...\",\"order\":1,\"steps\":[],"
            "\"success_criteria\":[]}]},\"assessment\":null}."
        ),
    )


def lesson_content_repair_prompt_template() -> PromptTemplate:
    return PromptTemplate(
        template_id=LESSON_REPAIR_PROMPT_ID,
        version=LESSON_REPAIR_PROMPT_VERSION,
        system_instruction=(
            "Repair one previously generated lesson that failed deterministic quality validation. "
            "Return only the registered GeneratedLessonDraft JSON object using snake_case keys. "
            "Repair only deficient instructional sections; preserve the lesson contract, exact "
            "lesson_ref, exact planned lesson title, objective_refs, section order, and valid assessment alignment. "
            "Do not add filler, repetition, unsupported citations, capability-gap provenance, or SME approval claims."
        ),
        user_instruction=(
            "The original parsed lesson draft and a deterministic repair context are supplied below. "
            "The previous draft was structurally parseable but failed quality validation. Repair only "
            "the listed deficient sections. For each deficient section, provide substantive coverage "
            "beyond the minimum required instructional depth; do not write exactly the threshold and "
            "do not pad. Preserve already-valid sections unless a small coherence adjustment is needed. "
            "Guided practice must retain actual ordered steps, and independent practice must retain "
            "observable success criteria. Preserve a valid assessment and its objective alignment; do "
            "not remove or redesign it unnecessarily. Return the same six-section lesson structure and "
            "the exact lesson_ref, title, order, and objective_refs from the supplied lesson plan."
        ),
    )


def curriculum_planning_prompt_template(
    version: str = CURRICULUM_PLANNING_PROMPT_VERSION,
) -> PromptTemplate:
    if version == MICROLEARNING_CURRICULUM_PLANNING_PROMPT_VERSION:
        return PromptTemplate(
            template_id=CURRICULUM_PLANNING_PROMPT_ID,
            version=version,
            system_instruction=(
                "Plan a scope-first microlearning curriculum for SME review. Return only the "
                "registered JSON object using snake_case keys. Learning horizon is a pacing "
                "window, not content volume. Do not pad the curriculum to fill months."
            ),
            user_instruction=(
                "Use the confirmed outcomes and prerequisites to create the minimum sufficient "
                "set of focused units. Each normal unit should teach or practice one useful "
                "capability in one focused session. Use objective_refs only as exact identifiers "
                "objective-1, objective-2, and so on; never put an objective statement in an "
                "objective_refs field. Use only these exact lesson_type values: foundation, "
                "concept, applied, practice, integration, assessment, capstone. Preserve every "
                "objective reference and sequence modules by dependency and coherence. Workload category is advisory; "
                "deterministic code owns final instruction, practice, unit, module, and course "
                "effort. Do not infer module or lesson count from learning_horizon. When an "
                "explicit effort target is provided, create enough focused units for the target "
                "to fit the bounded per-unit effort ranges; do not pad units merely because the "
                "horizon is long. Do not invent effort merely because the horizon is long. The output shape is the "
                "same registered curriculum planning schema."
            ),
        )
    return PromptTemplate(
        template_id=CURRICULUM_PLANNING_PROMPT_ID,
        version=CURRICULUM_PLANNING_PROMPT_VERSION,
        system_instruction=(
            "Plan a domain-specific, duration-aware curriculum for SME review. Return only "
            "the registered JSON object using snake_case keys. This is planning only: do not "
            "generate lesson body content, citations, capability-gap provenance, or claims "
            "of SME approval. Respect the supplied duration, audience context, and the "
            "resolved required_scope bounds in the payload; module and lesson counts must "
            "remain within those inclusive bounds."
        ),
        user_instruction=(
            "For a GOAL_DRIVEN training brief, decompose the goal into multiple distinct learner "
            "capabilities with measurable outcomes, then sequence them into domain-specific "
            "modules and lessons. Use objective_refs exactly as objective-<sequence> in the "
            "planning output. Every lesson must reference at least one objective. The payload "
            "contains estimated_total_learning_hours and required_scope with inclusive min/max "
            "module and lesson counts; satisfy those bounds and do not fall back to a fixed "
            "generic course shape. Classify every lesson with exactly one controlled lesson_type: "
            "foundation, concept, applied, practice, integration, assessment, or capstone. "
            "estimated_minutes and estimated_hours are advisory planning inputs; final workload "
            "minutes are allocated deterministically after planning. Use progression from "
            "foundation to application, integration, and evaluation when appropriate. The output shape is: "
            "{\"objectives\":[{\"statement\":\"...\",\"measurable_outcome\":\"...\",\"sequence\":1}],"
            "\"modules\":[{\"title\":\"...\",\"order\":1,\"objective_refs\":[\"objective-1\"],"
            "\"estimated_hours\":4,\"lessons\":[{\"title\":\"...\",\"order\":1,"
            "\"objective_refs\":[\"objective-1\"],\"estimated_minutes\":60,"
            "\"lesson_type\":\"skill_practice\"}]}],\"estimated_total_learning_hours\":4}."
        ),
    )
