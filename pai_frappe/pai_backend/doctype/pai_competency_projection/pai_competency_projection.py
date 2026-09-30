import frappe

from frappe.model.document import Document


class PAICompetencyProjection(Document):
	def validate(self):
		if self.status == "Verified":
			frappe.throw("Verified competency can only be set by the signed PAI verification integration.", frappe.PermissionError)
