# Copyright (c) 2024, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class LMSProgram(Document):
	def validate(self):
		self.validate_program_courses()
		self.validate_program_members()
		self.update_count()
		self.restrict_instructor_publish()

	def after_insert(self):
		if not _is_moderator():
			_notify_moderators_new_program(self)

	def restrict_instructor_publish(self):
		if _is_moderator():
			return
		if self.published:
			self.published = 0

	def validate_program_courses(self):
		courses = [row.course for row in self.program_courses]
		duplicates = {course for course in courses if courses.count(course) > 1}
		if len(duplicates):
			frappe.throw(
				_("Course {0} has already been added to this batch.").format(
					frappe.bold(next(iter(duplicates)))
				)
			)

	def validate_program_members(self):
		members = [row.member for row in self.program_members]
		duplicates = {member for member in members if members.count(member) > 1}
		if len(duplicates):
			frappe.throw(
				_("Member {0} has already been added to this batch.").format(
					frappe.bold(next(iter(duplicates)))
				)
			)

	def update_count(self):
		course_count = len(self.program_courses)
		member_count = len(self.program_members)

		if self.course_count != course_count:
			self.course_count = course_count

		if self.member_count != member_count:
			self.member_count = member_count


def _is_moderator(user=None):
	user = user or frappe.session.user
	return (
		user == "Administrator"
		or "System Manager" in frappe.get_roles(user)
		or frappe.db.get_value("Has Role", {"parent": user, "role": "Moderator"}, "name")
	)


def _notify_moderators_new_program(program):
	from lms.lms.doctype.lms_notification.lms_notification import make_lms_notification_logs

	creator_name = frappe.db.get_value("User", program.owner, "full_name") or program.owner
	moderators = frappe.get_all("Has Role", {"role": "Moderator"}, pluck="parent")
	if not moderators:
		return

	notification = frappe._dict(
		{
			"subject": _("{0} created a new Program '{1}' pending your review").format(
				creator_name, program.title
			),
			"email_content": _(
				"{0} has created a new Program <b>{1}</b>. Please review and publish it."
			).format(creator_name, program.title),
			"document_type": "LMS Program",
			"document_name": program.name,
			"from_user": program.owner,
			"type": "Alert",
			"link": f"/lms/programs",
		}
	)
	make_lms_notification_logs(notification, moderators)

