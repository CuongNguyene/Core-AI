import frappe


def execute():
	"""Collapse "Course Creator" and "Batch Evaluator" into a single "Instructor" role."""
	if not frappe.db.exists("Role", "Instructor"):
		frappe.get_doc({"doctype": "Role", "role_name": "Instructor", "desk_access": 0}).insert(
			ignore_permissions=True
		)

	for old_role in ("Course Creator", "Batch Evaluator"):
		if not frappe.db.exists("Role", old_role):
			continue

		holders = frappe.get_all("Has Role", {"role": old_role, "parenttype": "User"}, pluck="parent")
		for user in holders:
			if not frappe.db.exists("User", user):
				continue
			if not frappe.db.exists("Has Role", {"parent": user, "role": "Instructor"}):
				frappe.get_doc("User", user).add_roles("Instructor")

		frappe.db.delete("Has Role", {"role": old_role})
		frappe.delete_doc("Role", old_role, force=1, ignore_permissions=True)
