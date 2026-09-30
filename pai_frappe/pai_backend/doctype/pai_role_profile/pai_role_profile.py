import frappe

from frappe.model.document import Document


class PAIRoleProfile(Document):
	def validate(self):
		if self.status in {"Provisional", "Active"} and not self.semantic_policy:
			frappe.throw("An approved role profile must pin a semantic policy.", frappe.ValidationError)
		if self.status in {"Provisional", "Active"} and not self.semantic_policy_version:
			frappe.throw("An approved role profile must pin a semantic policy version.", frappe.ValidationError)
