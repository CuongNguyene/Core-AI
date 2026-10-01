"""Phase 1C bulk assignment and compliance APIs.

The APIs deliberately reuse Learning Assignment services; they never insert an
LMS Enrollment directly.
"""

import json

import frappe

from frappe import _
from frappe.utils.xlsxutils import build_xlsx_response

from lms.lms.learning_assignment import (
	_is_system_manager,
	assert_can_manage_learning_assignment_target,
	create_learning_assignment,
	get_learning_assignment_detail,
	get_target_courses,
)
from lms.lms.utils import can_create_courses, has_course_moderator_role


def _parse_rows(rows):
	if isinstance(rows, str):
		try:
			rows = json.loads(rows)
		except json.JSONDecodeError:
			frappe.throw(_("Bulk assignment rows must be valid JSON."), frappe.ValidationError)
	if not isinstance(rows, list):
		frappe.throw(_("Bulk assignment rows must be a list."), frappe.ValidationError)
	return rows


def _validate_bulk_row(row, index):
	result = {"row": index, "ok": False, "learner": row.get("learner"), "errors": []}
	for key in ("learner", "target_type", "target"):
		if not row.get(key):
			result["errors"].append(_("Missing {0}.").format(key))
	if result["errors"]:
		return result
	try:
		get_target_courses(row["target_type"], row["target"])
		assert_can_manage_learning_assignment_target(row["target_type"], row["target"])
		if not frappe.db.get_value("User", row["learner"], "enabled"):
			raise frappe.ValidationError(_("Learner does not exist or is disabled."))
	except Exception as exc:
		result["errors"].append(str(exc))
		return result
	result["ok"] = True
	return result


@frappe.whitelist()
def preview_bulk_learning_assignments(rows):
	"""Validate every row without writing; row errors do not block other rows."""
	if not (_is_system_manager() or has_course_moderator_role()):
		frappe.throw(_("Only System Manager or Moderator can run bulk assignment."), frappe.PermissionError)
	results = [_validate_bulk_row(row, index + 1) for index, row in enumerate(_parse_rows(rows))]
	return {"rows": results, "valid": sum(row["ok"] for row in results), "invalid": sum(not row["ok"] for row in results)}


@frappe.whitelist()
def confirm_bulk_learning_assignments(rows):
	"""Process valid rows independently, retaining per-row success/failure results."""
	preview = preview_bulk_learning_assignments(rows)
	data = _parse_rows(rows)
	results = []
	for check, row in zip(preview["rows"], data):
		if not check["ok"]:
			results.append({**check, "status": "Failed"})
			continue
		try:
			assignment = create_learning_assignment(
				row["learner"], row["target_type"], row["target"], due_at=row.get("due_at"),
				mandatory=row.get("mandatory", 1), note=row.get("note", ""), source="Bulk",
				idempotency_key=row.get("idempotency_key"),
			)
			results.append({**check, "status": "Duplicate" if assignment["already_assigned"] else "Success", "assignment": assignment["name"]})
		except Exception as exc:
			results.append({**check, "status": "Failed", "errors": [str(exc)]})
	return {"rows": results, "success": sum(row["status"] == "Success" for row in results), "failed": sum(row["status"] == "Failed" for row in results)}


def _assert_compliance_scope(course=None):
	if _is_system_manager() or has_course_moderator_role():
		return
	if not course or not can_create_courses(course):
		frappe.throw(_("You are not permitted to view this compliance data."), frappe.PermissionError)


def get_learning_compliance_data(learner=None, course=None, batch=None, status=None):
	"""Shared server-side dataset for UI, XLSX and PDF export."""
	_assert_compliance_scope(course)
	filters = {}
	if learner:
		filters["learner"] = learner
	if course:
		filters["course"] = course
	if batch:
		filters["batch"] = batch
	rows = []
	for name in frappe.get_all("LMS Learning Assignment", filters=filters, pluck="name"):
		doc = frappe.get_doc("LMS Learning Assignment", name)
		detail = get_learning_assignment_detail(doc)
		if course and not any(item["course"] == course for item in detail["items"]):
			continue
		if status and detail["status"] != status:
			continue
		rows.append(detail)
	return {"rows": rows, "total": len(rows)}


@frappe.whitelist()
def get_learning_compliance(learner=None, course=None, batch=None, status=None):
	return get_learning_compliance_data(learner, course, batch, status)


@frappe.whitelist()
def export_learning_compliance_xlsx(learner=None, course=None, batch=None, status=None):
	data = get_learning_compliance_data(learner, course, batch, status)
	xlsx_rows = [["Learner", "Target", "Status", "Progress", "Due At", "Completed Late", "Last Activity"]]
	for row in data["rows"]:
		xlsx_rows.append([
			frappe.db.get_value("User", frappe.get_value("LMS Learning Assignment", row["name"], "learner"), "full_name"),
			row["target_title"], row["status"], row["progress"], row["due_at"], row["completed_late"], row["last_activity_at"],
		])
	build_xlsx_response(xlsx_rows, "Learning Compliance")
