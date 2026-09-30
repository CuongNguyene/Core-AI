import frappe

from frappe.model.document import Document


class PAICapabilityAnalysis(Document):
	def validate(self):
		if self.status in {"Ready", "Reviewed"} and not self.source_profile_ref:
			frappe.throw("A reviewed capability analysis requires an accepted source profile reference.", frappe.ValidationError)
		if self.status in {"Ready", "Reviewed"} and not self.target_role_profile:
			frappe.throw("A reviewed capability analysis requires a target role profile.", frappe.ValidationError)
