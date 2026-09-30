import frappe

from frappe.model.document import Document


class PAILearningPath(Document):
	def validate(self):
		if self.status == "Active" and not self.source_capability_analysis:
			frappe.throw("An active learning path requires a reviewed capability analysis.", frappe.ValidationError)
