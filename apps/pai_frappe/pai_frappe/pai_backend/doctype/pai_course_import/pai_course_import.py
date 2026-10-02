import frappe

from frappe.model.document import Document


class PAICourseImport(Document):
	"""Immutable provenance record for a reviewed PAI draft imported into LMS."""

	def validate(self):
		if self.source_type == "Curriculum Plan" and not self.source_plan_ref:
			frappe.throw("A CurriculumPlan reference is required.", frappe.ValidationError)
		if self.source_type != "Curriculum Plan" and not self.result_ref:
			frappe.throw("A PAI result reference is required.", frappe.ValidationError)
		if self.status == "Imported" and not self.lms_course:
			frappe.throw("An imported PAI course must reference an LMS Course.", frappe.ValidationError)
