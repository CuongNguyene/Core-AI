# Copyright (c) 2026, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe.desk.doctype.notification_settings.notification_settings import (
	is_email_notifications_enabled,
	is_notifications_enabled,
)
from frappe.model.document import Document


class LMSNotification(Document):
	def after_insert(self):
		frappe.publish_realtime("publish_lms_notifications", user=self.for_user, after_commit=True)
		self.send_mobile_push()
		self.send_email()

	def send_mobile_push(self):
		"""Pushes to the CT ERP mobile app via the same Firebase integration
		Helpdesk uses (ctg_custom's Notification CTERP). ctg_custom is a
		bench-specific app, not an LMS dependency, so this must never break
		notification creation on sites where it isn't installed."""
		if "ctg_custom" not in frappe.get_installed_apps():
			return

		try:
			from ctg_custom.ctg_custom.doctype.notification_cterp.notification_cterp import (
				send_notification_user,
			)

			send_notification_user(
				user=self.for_user,
				title=frappe.utils.strip_html(self.subject or "LMS")[:140],
				content=frappe.utils.strip_html(self.subject or ""),
				content_show=frappe.utils.strip_html(self.subject or ""),
				doctype=self.document_type or "LMS Notification",
				doctype_name=self.document_name or "",
			)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(), f"Failed to push CTERP notification for {self.for_user}"
			)

	def send_email(self):
		if not is_notifications_enabled(self.for_user) or not is_email_notifications_enabled(self.for_user):
			return

		user_email = frappe.db.get_value("User", self.for_user, "email")
		if not user_email:
			return

		try:
			frappe.sendmail(
				recipients=[user_email],
				subject=frappe.utils.strip_html(self.subject or "New notification"),
				message=self.email_content or self.subject or "",
				reference_doctype=self.doctype,
				reference_name=self.name,
				now=False,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Failed to email LMS Notification to {self.for_user}")


def get_permission_query_conditions(user):
	user = user or frappe.session.user
	if user == "Administrator":
		return

	return f"""(`tabLMS Notification`.for_user = {frappe.db.escape(user)})"""


def make_lms_notification_logs(doc, users):
	"""Creates an LMS Notification for each user. Mirrors the shape of
	frappe.desk.doctype.notification_log.notification_log.make_notification_logs,
	but writes to LMS's own doctype so unrelated site-wide notifications
	(from other apps writing to the shared Notification Log) never show up
	in the LMS notification inbox.
	"""
	users = users if isinstance(users, (list, tuple)) else [users]
	user_names = frappe.db.get_values("User", {"enabled": 1, "email": ("in", users)}, "name", pluck=True)

	for user in user_names:
		notification = frappe.new_doc("LMS Notification")
		notification.update(doc)
		notification.for_user = user
		notification.insert(ignore_permissions=True)
