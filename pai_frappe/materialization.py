"""Safe, review-first materialization of a PAI course draft into LMS documents."""

import hashlib
import json

import frappe
from frappe.utils import now_datetime, strip_html

READY_FOR_MATERIALIZATION = "READY_FOR_MATERIALIZATION"
MAX_MODULES = 50
MAX_LESSONS_PER_MODULE = 100
MAX_SECTIONS_PER_LESSON = 100
MAX_TEXT_LENGTH = 50000


def get_generated_course(result):
	if result.get("status") != READY_FOR_MATERIALIZATION:
		frappe.throw(
			"Only a PAI draft marked READY_FOR_MATERIALIZATION can be imported.",
			frappe.ValidationError,
		)
	generated_course = result.get("generated_course")
	if not isinstance(generated_course, dict):
		frappe.throw("The PAI result does not contain a course draft.", frappe.ValidationError)
	if not isinstance(generated_course.get("course"), dict) or not _valid_text(generated_course["course"].get("title")):
		frappe.throw("The PAI course draft is missing its course title.", frappe.ValidationError)
	if not isinstance(generated_course.get("modules"), list) or not generated_course["modules"]:
		frappe.throw("The PAI course draft is missing course modules.", frappe.ValidationError)
	if len(generated_course["modules"]) > MAX_MODULES:
		frappe.throw("The PAI course draft has too many modules.", frappe.ValidationError)
	module_orders = set()
	for module in generated_course["modules"]:
		if not isinstance(module, dict) or not _valid_text(module.get("title")):
			frappe.throw("Every PAI module must have a title.", frappe.ValidationError)
		_validate_order(module, module_orders, "module")
		lessons = module.get("lessons")
		if not isinstance(lessons, list) or not lessons or len(lessons) > MAX_LESSONS_PER_MODULE:
			frappe.throw("Every PAI module must contain lessons.", frappe.ValidationError)
		lesson_orders = set()
		for lesson in lessons:
			if not isinstance(lesson, dict) or not _valid_text(lesson.get("title")):
				frappe.throw("Every PAI lesson must have a title.", frappe.ValidationError)
			_validate_order(lesson, lesson_orders, "lesson")
			sections = lesson.get("sections")
			if not isinstance(sections, list) or not sections or len(sections) > MAX_SECTIONS_PER_LESSON:
				frappe.throw("Every PAI lesson must contain sections.", frappe.ValidationError)
			section_orders = set()
			for section in sections:
				if not isinstance(section, dict):
					frappe.throw("Every PAI lesson section must be structured data.", frappe.ValidationError)
				_validate_order(section, section_orders, "lesson section")
				for fieldname in ("title", "content"):
					if fieldname in section and not _valid_text(section[fieldname], allow_empty=True):
						frappe.throw("PAI lesson section text is invalid.", frappe.ValidationError)
				for fieldname in ("steps", "success_criteria"):
					if fieldname in section and (
						not isinstance(section[fieldname], list)
						or len(section[fieldname]) > 100
						or any(not _valid_text(item) for item in section[fieldname])
					):
						frappe.throw("PAI lesson section list content is invalid.", frappe.ValidationError)
	return generated_course


def get_source_hash(generated_course):
	payload = json.dumps(generated_course, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
	return hashlib.sha256(payload.encode()).hexdigest()


def render_lesson_body(sections):
	"""Render PAI's structured sections as plain Markdown, never import model HTML."""
	blocks = []
	for section in sorted(sections, key=lambda item: item["order"]):
		title = _safe_text(section.get("title"))
		content = _safe_text(section.get("content"))
		if title:
			blocks.append(f"## {title}")
		if content:
			blocks.append(content)
		steps = [_safe_text(item) for item in section.get("steps", []) if _safe_text(item)]
		if steps:
			blocks.append("### Steps\n" + "\n".join(f"- {item}" for item in steps))
		success_criteria = [
			_safe_text(item) for item in section.get("success_criteria", []) if _safe_text(item)
		]
		if success_criteria:
			blocks.append("### Success criteria\n" + "\n".join(f"- {item}" for item in success_criteria))
	return "\n\n".join(blocks).strip()


def materialize_course(import_doc, generated_course, instructor):
	"""Create an unpublished LMS course tree in the current transaction."""
	course_data = generated_course["course"]
	description = _safe_text(course_data.get("description")) or "PAI generated course draft."
	course = frappe.get_doc(
		{
			"doctype": "LMS Course",
			"title": _safe_text(course_data["title"]),
			"short_introduction": description[:1000],
			"description": description,
			"published": 0,
			"instructors": [{"instructor": instructor}],
		}
	)
	course.insert(ignore_permissions=True)

	for module in sorted(generated_course["modules"], key=lambda item: item["order"]):
		chapter = frappe.get_doc(
			{
				"doctype": "Course Chapter",
				"title": _safe_text(module.get("title")) or "Untitled module",
				"course": course.name,
			}
		)
		chapter.insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Chapter Reference",
				"chapter": chapter.name,
				"idx": module["order"],
				"parent": course.name,
				"parenttype": "LMS Course",
				"parentfield": "chapters",
			}
		).insert(ignore_permissions=True)

		for lesson_data in sorted(module["lessons"], key=lambda item: item["order"]):
			lesson = frappe.get_doc(
				{
					"doctype": "Course Lesson",
					"title": _safe_text(lesson_data.get("title")) or "Untitled lesson",
					"chapter": chapter.name,
					"course": course.name,
					"body": render_lesson_body(lesson_data.get("sections", [])),
				}
			)
			lesson.insert(ignore_permissions=True)
			frappe.get_doc(
				{
					"doctype": "Lesson Reference",
					"lesson": lesson.name,
					"idx": lesson_data["order"],
					"parent": chapter.name,
					"parenttype": "Course Chapter",
					"parentfield": "lessons",
				}
			).insert(ignore_permissions=True)

	import_doc.db_set("lms_course", course.name, update_modified=False)
	import_doc.db_set("status", "Imported", update_modified=False)
	import_doc.db_set("imported_by", frappe.session.user, update_modified=False)
	import_doc.db_set("imported_on", now_datetime(), update_modified=False)
	import_doc.db_set("error_code", "", update_modified=False)
	import_doc.db_set("error_message", "", update_modified=False)
	return course


def _safe_text(value):
	"""Keep generated content as text, not an LMS content-plugin instruction.

	`LessonContent` recognizes ``{{ Quiz }}``, ``{{ Embed }}`` and related
	markers before rendering Markdown.  A generated section is not allowed to
	create those executable/embed blocks implicitly, so neutralize the delimiters
	while preserving the visible text for the instructor to review.
	"""
	text = strip_html(str(value or ""))
	return text.replace("{{", "{\u200b{").replace("}}", "}\u200b}").replace("javascript:", "").strip()


def _valid_text(value, *, allow_empty=False):
	return isinstance(value, str) and len(value) <= MAX_TEXT_LENGTH and (allow_empty or bool(_safe_text(value)))


def _validate_order(item, seen_orders, item_label):
	order = item.get("order")
	if isinstance(order, bool) or not isinstance(order, int) or not 1 <= order <= 10000:
		frappe.throw(f"Every PAI {item_label} must have a valid order.", frappe.ValidationError)
	if order in seen_orders:
		frappe.throw(f"PAI {item_label} order values must be unique.", frappe.ValidationError)
	seen_orders.add(order)
