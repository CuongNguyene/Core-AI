import frappe

from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class LMSLearningAssignment(Document):
	"""A learning obligation that deliberately remains separate from enrollment."""

	def validate(self):
		self._validate_target()
		self._set_audit_defaults()
		self._validate_lifecycle()
		self._set_active_assignment_key()
		self._validate_items()

	def _validate_target(self):
		if self.target_type not in {"Course", "Batch"}:
			frappe.throw(_("Learning Assignment target must be a Course or Batch."))

		if self.target_type == "Course":
			if not self.course or self.batch:
				frappe.throw(_("A course assignment must have exactly one course target."))
		elif not self.batch or self.course:
			frappe.throw(_("A batch assignment must have exactly one batch target."))

	def _set_audit_defaults(self):
		if self.is_new():
			self.assigned_by = self.assigned_by or frappe.session.user
			self.assigned_on = self.assigned_on or now_datetime()
			self.status = self.status or "Assigned"

	def _validate_lifecycle(self):
		if self.status not in {"Assigned", "In Progress", "Completed", "Overdue", "Cancelled"}:
			frappe.throw(_("Invalid learning assignment status."))
		if self.status == "Cancelled":
			if not self.cancelled_by or not self.cancelled_at or not self.cancel_reason:
				frappe.throw(_("Cancelled assignments require an actor, time and reason."))
		elif self.cancelled_by or self.cancelled_at or self.cancel_reason:
			frappe.throw(_("Cancellation fields can only be set for a cancelled assignment."))
		if self.status == "Completed" and not self.completed_at:
			frappe.throw(_("Completed assignments require a completion time."))
		if self.status != "Completed" and self.completed_late:
			frappe.throw(_("Only completed assignments can be marked as completed late."))

	def _set_active_assignment_key(self):
		if self.status == "Cancelled":
			self.active_assignment_key = None
			return
		target = self.course if self.target_type == "Course" else self.batch
		self.active_assignment_key = f"{self.learner}|{self.target_type}|{target}"

	def _validate_items(self):
		if self.status == "Cancelled" and not self.items:
			return
		if not self.items:
			frappe.throw(_("A learning assignment requires at least one course item."))
		for item in self.items:
			if not item.course or not item.lms_enrollment:
				frappe.throw(_("Every learning assignment item requires a course and enrollment."))
			enrollment = frappe.db.get_value(
				"LMS Enrollment", item.lms_enrollment, ["member", "course"], as_dict=True
			)
			if not enrollment or enrollment.member != self.learner or enrollment.course != item.course:
				frappe.throw(_("Learning assignment item enrollment does not match its learner and course."))
			if self.target_type == "Course" and item.course != self.course:
				frappe.throw(_("A course assignment item must match the assignment course."))
			if self.target_type == "Batch" and item.source_batch != self.batch:
				frappe.throw(_("A batch assignment item must retain its source batch."))
