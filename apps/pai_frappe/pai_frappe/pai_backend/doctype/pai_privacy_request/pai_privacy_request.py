import frappe

from frappe.model.document import Document


class PAIPrivacyRequest(Document):
	def validate(self):
		if self.status in {"Completed", "Failed"} and not getattr(
			frappe.flags, "from_pai_privacy_integration", False
		):
			frappe.throw(
				"Privacy completion can only be recorded by the signed PAI privacy integration.",
				frappe.PermissionError,
			)
