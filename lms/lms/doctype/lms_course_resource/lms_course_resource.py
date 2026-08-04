# Copyright (c) 2026, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from lms.lms.utils import get_instructors


def can_manage_course_resource(course=None, batch=None):
	"""Only instructors of the given course/batch (or Moderators) may add or remove resources."""
	roles = frappe.get_roles()
	if "Moderator" in roles or "System Manager" in roles:
		return True

	if "Instructor" not in roles:
		return False

	if course and any(
		instructor.name == frappe.session.user for instructor in get_instructors("LMS Course", course)
	):
		return True

	if batch and any(
		instructor.name == frappe.session.user for instructor in get_instructors("LMS Batch", batch)
	):
		return True

	return False


class LMSCourseResource(Document):
	def validate(self):
		if not self.course and not self.batch:
			frappe.throw(frappe._("Please select either a course or a batch for this resource."))

	def before_insert(self):
		if not can_manage_course_resource(self.course, self.batch):
			frappe.throw(
				frappe._("You don't have permission to add resources here."), frappe.PermissionError
			)

	def on_trash(self):
		if not can_manage_course_resource(self.course, self.batch):
			frappe.throw(
				frappe._("You don't have permission to delete this resource."), frappe.PermissionError
			)


@frappe.whitelist()
def get_course_resources(course=None, batch=None):
	if not course and not batch:
		frappe.throw(frappe._("Please provide either a course or a batch."))

	filters = {}
	if course:
		filters["course"] = course
	if batch:
		filters["batch"] = batch

	return frappe.get_all(
		"LMS Course Resource",
		filters=filters,
		fields=["name", "title", "attachment", "course", "batch", "owner", "creation"],
		order_by="creation desc",
	)
