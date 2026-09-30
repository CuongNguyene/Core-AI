import frappe
from frappe.model.document import Document


class PAIRequest(Document):
	def validate(self):
		# The local record is intentionally written before PAI is called so an
		# interrupted create can be retried with the same idempotency key. All
		# completed authoring records must still carry their remote PAI reference.
		if (
			self.request_type == "Course Authoring"
			and self.status != "Creating"
			and not self.pai_request_id
		):
			frappe.throw("A completed PAI authoring request must reference PAI.", frappe.ValidationError)
