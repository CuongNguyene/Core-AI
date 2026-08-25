import frappe


def execute():
	if not frappe.db.table_exists("LMS Course") or not frappe.db.has_column(
		"LMS Course", "duration"
	):
		return

	column = frappe.db.sql("SHOW COLUMNS FROM `tabLMS Course` LIKE 'duration'", as_dict=True)
	if column and "int" not in column[0].get("Type", "").lower():
		# Pre-existing untracked column (no matching Custom Field/Property Setter,
		# not in git history) whose leftover data isn't int-castable under strict
		# SQL mode, so the schema sync to the new `duration` Int field fails with
		# "Data truncated for column 'duration'". Drop it here, pre_model_sync,
		# so sync_all() below re-adds it cleanly as Int.
		frappe.db.sql_ddl("ALTER TABLE `tabLMS Course` DROP COLUMN `duration`")
