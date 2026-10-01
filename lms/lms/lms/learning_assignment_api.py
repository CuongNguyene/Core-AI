"""Whitelisted Phase 1A Learning Assignment APIs."""

import frappe

from frappe import _

from lms.lms.learning_assignment import add_course_to_batch as _add_course_to_batch
from lms.lms.learning_assignment import cancel_learning_assignment as _cancel_learning_assignment
from lms.lms.learning_assignment import create_learning_assignment as _create_learning_assignment
from lms.lms.learning_assignment import get_target_courses
from lms.lms.learning_assignment import get_my_learning as _get_my_learning
from lms.lms.learning_assignment import preview_batch_course_sync as _preview_batch_course_sync
from lms.lms.learning_assignment import sync_batch_course_existing_learners as _sync_batch_course
from lms.lms.learning_assignment import (
	_is_system_manager,
	assert_can_manage_learning_assignment_target,
	can_manage_learning_assignment_target,
	get_learning_assignment_detail,
)
from lms.lms.utils import has_course_moderator_role


def _assert_learning_assignment_manager():
	"""Require a role that can manage at least one assignment target."""
	user = frappe.session.user
	if _is_system_manager(user) or has_course_moderator_role(user) or "Instructor" in frappe.get_roles(user):
		return user
	frappe.throw(_("You are not permitted to manage learning assignments."), frappe.PermissionError)


@frappe.whitelist()
def create_learning_assignment(
	learner,
	target_type,
	target,
	due_at=None,
	mandatory=1,
	note="",
	idempotency_key=None,
):
	return _create_learning_assignment(
		learner,
		target_type,
		target,
		due_at=due_at,
		mandatory=mandatory,
		note=note,
		idempotency_key=idempotency_key,
	)


@frappe.whitelist()
def cancel_learning_assignment(name, reason):
	return _cancel_learning_assignment(name, reason)


@frappe.whitelist()
def get_my_learning():
	"""Learner-only read model; the service always scopes records to the session user."""
	return _get_my_learning()


@frappe.whitelist()
def add_course_to_batch(batch, course):
	_assert_learning_assignment_manager()
	return _add_course_to_batch(batch, course)


@frappe.whitelist()
def preview_batch_course_sync(batch, course):
	return _preview_batch_course_sync(batch, course)


@frappe.whitelist()
def sync_batch_course_existing_learners(batch, course, confirm=0):
	return _sync_batch_course(batch, course, confirm)


@frappe.whitelist()
def get_learning_assignment_management_data():
	"""Read model for the admin assignment page; scope remains server-side."""
	user = _assert_learning_assignment_manager()
	moderator = _is_system_manager(user) or has_course_moderator_role(user)
	courses = frappe.get_all("LMS Course", {"published": 1}, ["name", "title"])
	if not moderator:
		courses = [course for course in courses if can_manage_learning_assignment_target("Course", course.name, user)]
	batches = frappe.get_all("LMS Batch", {"published": 1}, ["name", "title"])
	if not moderator:
		batches = [batch for batch in batches if can_manage_learning_assignment_target("Batch", batch.name, user)]
	rows = []
	for name in frappe.get_all("LMS Learning Assignment", pluck="name", order_by="assigned_on desc"):
		doc = frappe.get_doc("LMS Learning Assignment", name)
		target = doc.course if doc.target_type == "Course" else doc.batch
		if not can_manage_learning_assignment_target(doc.target_type, target, user):
			continue
		detail = get_learning_assignment_detail(doc)
		detail["learner"] = doc.learner
		detail["assigned_by"] = doc.assigned_by
		rows.append(detail)
	return {"courses": courses, "batches": batches, "assignments": rows}


@frappe.whitelist()
def search_assignable_learners(target_type, target, txt=""):
	"""Return a small, target-authorized set of active LMS learners for the picker."""
	user = _assert_learning_assignment_manager()
	get_target_courses(target_type, target)
	assert_can_manage_learning_assignment_target(target_type, target, user)

	query = f"%{(txt or '').strip()}%"
	learners = frappe.db.sql(
		"""
			SELECT DISTINCT user.name, user.full_name
			FROM `tabUser` AS user
			INNER JOIN `tabHas Role` AS role
				ON role.parent = user.name
				AND role.parenttype = 'User'
			WHERE user.enabled = 1
				AND user.name NOT IN ('Administrator', 'Guest')
				AND role.role = 'LMS Student'
				AND (user.name LIKE %(query)s OR user.full_name LIKE %(query)s)
			ORDER BY user.full_name ASC, user.name ASC
			LIMIT 20
		""",
		{"query": query},
		as_dict=True,
	)
	return [
		{
			"value": learner.name,
			"label": learner.full_name or learner.name,
			"description": learner.name,
		}
		for learner in learners
	]
