import frappe

from frappe.model.document import Document


class PAISemanticPolicy(Document):
	def validate(self):
		if self.status == "Active" and not self.domain_pack_checksum:
			frappe.throw("An active semantic policy requires a domain-pack checksum.", frappe.ValidationError)
