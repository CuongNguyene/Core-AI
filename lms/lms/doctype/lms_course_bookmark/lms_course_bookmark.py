# Copyright (c) 2026, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LMSCourseBookmark(Document):
	pass


@frappe.whitelist()
def toggle_bookmark(course):
	filters = {"course": course, "member": frappe.session.user}
	existing = frappe.db.exists("LMS Course Bookmark", filters)

	if existing:
		frappe.delete_doc("LMS Course Bookmark", existing, ignore_permissions=True)
		return False

	frappe.get_doc({"doctype": "LMS Course Bookmark", **filters}).insert(ignore_permissions=True)
	return True
