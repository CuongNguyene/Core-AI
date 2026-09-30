import frappe

from frappe.model.document import Document


class PAICourseImport(Document):
	"""Immutable provenance record for a reviewed PAI draft imported into LMS."""

	def validate(self):
		if self.status == "Imported" and not self.lms_course:
			frappe.throw("An imported PAI course must reference an LMS Course.", frappe.ValidationError)
