"""Deterministic mapping from a confirmed CurriculumPlan to LMS draft documents."""

from dataclasses import dataclass
import hashlib
import json

import frappe


class CurriculumMaterializationError(ValueError):
	"""Raised when a CurriculumPlan cannot be safely materialized."""


@dataclass(frozen=True)
class CurriculumLessonDraftSpec:
	title: str
	order: int
	body: str = ""


@dataclass(frozen=True)
class CurriculumChapterDraftSpec:
	title: str
	order: int
	lessons: tuple[CurriculumLessonDraftSpec, ...]


@dataclass(frozen=True)
class CurriculumCourseDraftSpec:
	plan_ref: str
	version: int
	title: str
	description: str
	chapters: tuple[CurriculumChapterDraftSpec, ...]


def adapt_curriculum_plan(plan):
	"""Convert the canonical plan projection into an LMS-only draft spec.

	The adapter intentionally drops objective references, lesson type, duration,
	and planning metadata because the current LMS DocTypes have no canonical
	fields for them. It also leaves lesson bodies empty: CURR-02C creates the
	structural draft only and never fabricates instructional content.
	"""
	if not isinstance(plan, dict):
		raise CurriculumMaterializationError("The CurriculumPlan response is invalid.")
	if plan.get("status") != "CONFIRMED":
		raise CurriculumMaterializationError("Only a confirmed CurriculumPlan can be materialized.")

	plan_ref = _text(plan.get("plan_ref"))
	title = _text(plan.get("course_title"))
	description = _text(plan.get("course_description"))
	version = plan.get("version")
	if not plan_ref or not title or not description or isinstance(version, bool) or not isinstance(version, int) or version < 1:
		raise CurriculumMaterializationError("The confirmed CurriculumPlan is missing required course fields.")

	modules = plan.get("modules")
	if not isinstance(modules, list) or not modules:
		raise CurriculumMaterializationError("The confirmed CurriculumPlan has no modules.")

	chapters = []
	module_orders = set()
	for module in sorted(modules, key=lambda item: item.get("order", 0) if isinstance(item, dict) else 0):
		if not isinstance(module, dict):
			raise CurriculumMaterializationError("Every curriculum module must be structured data.")
		order = _positive_order(module.get("order"), "module")
		if order in module_orders:
			raise CurriculumMaterializationError("Curriculum module order values must be unique.")
		module_orders.add(order)
		module_title = _text(module.get("title"))
		lessons = module.get("lessons")
		if not module_title or not isinstance(lessons, list) or not lessons:
			raise CurriculumMaterializationError("Every curriculum module must have a title and lessons.")

		lesson_orders = set()
		lesson_specs = []
		for lesson in sorted(lessons, key=lambda item: item.get("order", 0) if isinstance(item, dict) else 0):
			if not isinstance(lesson, dict):
				raise CurriculumMaterializationError("Every curriculum lesson must be structured data.")
			lesson_order = _positive_order(lesson.get("order"), "lesson")
			if lesson_order in lesson_orders:
				raise CurriculumMaterializationError("Curriculum lesson order values must be unique within a module.")
			lesson_orders.add(lesson_order)
			lesson_title = _text(lesson.get("title"))
			if not lesson_title:
				raise CurriculumMaterializationError("Every curriculum lesson must have a title.")
			lesson_specs.append(CurriculumLessonDraftSpec(title=lesson_title, order=lesson_order))
		chapters.append(
			CurriculumChapterDraftSpec(
				title=module_title,
				order=order,
				lessons=tuple(lesson_specs),
			)
		)

	return CurriculumCourseDraftSpec(
		plan_ref=plan_ref,
		version=version,
		title=title,
		description=description,
		chapters=tuple(chapters),
	)


def create_lms_draft(spec, instructor):
	"""Create an unpublished LMS Course tree from an adapted spec.

	The caller owns the surrounding transaction/savepoint. No model, PAI write,
	or publish operation is performed here.
	"""
	course = frappe.get_doc(
		{
			"doctype": "LMS Course",
			"title": spec.title,
			"short_introduction": spec.description[:1000],
			"description": spec.description,
			"published": 0,
			"instructors": [{"instructor": instructor}],
		}
	)
	course.insert(ignore_permissions=True)

	chapter_refs = []
	lesson_refs = []
	for chapter_spec in spec.chapters:
		chapter = frappe.get_doc(
			{
				"doctype": "Course Chapter",
				"title": chapter_spec.title,
				"course": course.name,
			}
		)
		chapter.insert(ignore_permissions=True)
		chapter_refs.append({"name": chapter.name, "title": chapter_spec.title, "order": chapter_spec.order})

		for lesson_spec in chapter_spec.lessons:
			lesson = frappe.get_doc(
				{
					"doctype": "Course Lesson",
					"title": lesson_spec.title,
					"chapter": chapter.name,
					"course": course.name,
					"body": lesson_spec.body,
				}
			)
			lesson.insert(ignore_permissions=True)
			chapter.append("lessons", {"lesson": lesson.name})
			lesson_refs.append(
				{
					"name": lesson.name,
					"title": lesson_spec.title,
					"order": lesson_spec.order,
					"chapter": chapter.name,
				}
			)
			chapter.save(ignore_permissions=True)

	# Chapter hooks update LMS Course statistics. Reload after the tree is
	# created so the final child-table save uses the current document timestamp.
	course.reload()
	for chapter_ref in chapter_refs:
		course.append("chapters", {"chapter": chapter_ref["name"]})
	course.save(ignore_permissions=True)

	return {
		"plan_ref": spec.plan_ref,
		"version": spec.version,
		"course": {"name": course.name, "title": spec.title, "published": 0},
		"chapters": chapter_refs,
		"lessons": lesson_refs,
	}


def get_plan_source_hash(plan):
	payload = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
	return hashlib.sha256(payload.encode()).hexdigest()


def _text(value):
	return value.strip() if isinstance(value, str) else ""


def _positive_order(value, label):
	if isinstance(value, bool) or not isinstance(value, int) or value < 1:
		raise CurriculumMaterializationError(f"Every curriculum {label} must have a positive order.")
	return value
