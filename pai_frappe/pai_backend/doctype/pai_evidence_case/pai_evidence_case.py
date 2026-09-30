"""Local audit projection for sensitive PAI evidence, never the raw document."""

import frappe

from frappe.model.document import Document


class PAIEvidenceCase(Document):
	def validate(self):
		if self.status in {"Uploaded", "Extracting", "Pending Review", "Accepted", "Needs Revision", "Rejected"}:
			if not self.pai_document_ref:
				frappe.throw("A PAI document reference is required after upload.", frappe.ValidationError)
		if self.status in {"Pending Review", "Accepted", "Needs Revision", "Rejected"}:
			if not self.extraction_profile_ref:
				frappe.throw("An extraction profile is required for review.", frappe.ValidationError)
