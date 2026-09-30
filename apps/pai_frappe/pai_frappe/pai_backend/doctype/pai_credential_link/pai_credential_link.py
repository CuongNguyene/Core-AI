import frappe

from frappe.model.document import Document


class PAICredentialLink(Document):
	def validate(self):
		if self.status == "Issued" and not getattr(frappe.flags, "from_pai_credential_integration", False):
			frappe.throw(
				"Issued credentials can only be recorded by the signed PAI credential integration.",
				frappe.PermissionError,
			)
		if self.status == "Issued" and not self.pai_credential_ref:
			frappe.throw("An issued credential must have a PAI credential reference.", frappe.ValidationError)
		if self.status == "Issued" and not self.lms_certificate:
			frappe.throw("An issued credential must link its LMS Certificate artifact.", frappe.ValidationError)
