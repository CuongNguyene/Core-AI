import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Email Template": [
				{
					"fieldname": "is_lms_template",
					"fieldtype": "Check",
					"label": "Is LMS Template",
					"insert_after": "response",
					"default": "0",
					"hidden": 1,
					"print_hide": 1,
				}
			]
		}
	)

	template_names = set()

	for name in [
		_("Mentor Request Creation Template"),
		_("Mentor Request Status Update Template"),
	]:
		if frappe.db.exists("Email Template", name):
			template_names.add(name)

	settings_fields = [
		"mentor_request_creation",
		"mentor_request_status_update",
		"batch_confirmation_template",
		"certification_template",
		"payment_reminder_template",
	]
	for fieldname in settings_fields:
		value = frappe.db.get_single_value("LMS Settings", fieldname)
		if value and frappe.db.exists("Email Template", value):
			template_names.add(value)

	for name in template_names:
		frappe.db.set_value("Email Template", name, "is_lms_template", 1)
