import frappe

from frappe import _
from frappe.model.document import Document


class LMSLearningAssignmentReminderLog(Document):
	def validate(self):
		if self.reminder_code not in {"D-7", "D-3", "D-1"}:
			frappe.throw(_("Invalid learning assignment reminder code."))
		self.reminder_key = f"{self.assignment}|{self.reminder_code}"
