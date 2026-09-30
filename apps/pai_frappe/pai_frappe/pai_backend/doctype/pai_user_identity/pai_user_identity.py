from uuid import UUID

import frappe
from frappe.model.document import Document


class PAIUserIdentity(Document):
	def validate(self):
		try:
			UUID(self.pai_actor_id)
		except (TypeError, ValueError):
			frappe.throw("PAI Actor UUID is invalid.")
