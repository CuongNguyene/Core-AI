import os

import frappe
from frappe import _


def execute():
	frappe.reload_doc("email", "doctype", "email_template")
	frappe.reload_doc("lms", "doctype", "lms_settings")
	base_path = frappe.get_app_path("lms", "templates", "emails")

	templates = [
		{
			"name": _("Course Approval Request Template"),
			"file": "course_approval_request.html",
			"subject": _("{{ member_name }} created a new course {{ title }} that needs your approval"),
			"setting_fieldname": "course_approval_template",
		},
		{
			"name": _("Course Published Template"),
			"file": "course_published.html",
			"subject": _("Your course {{ title }} has been approved and published"),
			"setting_fieldname": "course_published_template",
		},
		{
			"name": _("Batch Approval Request Template"),
			"file": "batch_approval_request.html",
			"subject": _("{{ member_name }} created a new batch {{ title }} that needs your approval"),
			"setting_fieldname": "batch_approval_template",
		},
		{
			"name": _("Batch Published Template"),
			"file": "batch_published.html",
			"subject": _("Your batch {{ title }} has been approved and published"),
			"setting_fieldname": "batch_published_template",
		},
	]

	for template in templates:
		if frappe.db.get_single_value("LMS Settings", template["setting_fieldname"]):
			continue

		if not frappe.db.exists("Email Template", template["name"]):
			response = frappe.read_file(os.path.join(base_path, template["file"]))
			frappe.get_doc(
				{
					"doctype": "Email Template",
					"name": template["name"],
					"response": response,
					"subject": template["subject"],
					"is_lms_template": 1,
					"owner": frappe.session.user,
				}
			).insert(ignore_permissions=True)

		frappe.db.set_single_value("LMS Settings", template["setting_fieldname"], template["name"])
