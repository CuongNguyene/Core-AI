"""Whitelisted APIs consumed by the LMS PAI Studio Vue pages.

The browser talks only to Frappe.  This module owns the authorization boundary,
the local audit record, and the server-to-server PAI call; it never returns PAI
credentials to the client.
"""

import json
import re

import frappe
from frappe.utils import now_datetime

from pai_frappe.client import PAIClient, PAIClientError
from pai_frappe.curriculum_materialization import (
	CurriculumMaterializationError,
	adapt_curriculum_plan,
	create_lms_draft,
	get_plan_source_hash,
)
from pai_frappe.materialization import get_generated_course, get_source_hash, materialize_course

_AUTHORING_ROLES = ("System Manager", "Moderator", "Instructor")
_ADMIN_ROLES = ("System Manager", "Moderator")
_EVIDENCE_ROLES = (*_AUTHORING_ROLES, "LMS Student")
_PAI_SETTINGS_FIELDS = (
	("service_url", "PAI Service URL"),
	("organization_id", "PAI Organization UUID"),
	("actor_key_id", "Actor Signing Key ID"),
)
_PAI_SECRET_FIELDS = (
	("integration_api_key", "PAI Integration API Key"),
	("actor_private_key", "Actor Signing Private Key"),
)
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"[A-Za-z0-9._:-]{16,128}")


def _require_authoring_access():
	if not _has_any_role(_AUTHORING_ROLES):
		frappe.throw("PAI Studio access is not permitted.", frappe.PermissionError)


def _require_evidence_access():
	if not _has_any_role(_EVIDENCE_ROLES):
		frappe.throw("PAI Evidence access is not permitted.", frappe.PermissionError)


def _is_admin():
	return _has_any_role(_ADMIN_ROLES)


def _require_admin_access():
	if not _is_admin():
		frappe.throw("PAI governance access is not permitted.", frappe.PermissionError)


def _has_any_role(required_roles):
	return bool(set(frappe.get_roles(frappe.session.user)).intersection(required_roles))


def _get_missing_pai_settings(settings):
	missing = [label for fieldname, label in _PAI_SETTINGS_FIELDS if not getattr(settings, fieldname, None)]
	missing.extend(
		label
		for fieldname, label in _PAI_SECRET_FIELDS
		if not settings.get_password(fieldname, raise_exception=False)
	)
	return missing


def _parse_payload(data):
	if isinstance(data, str):
		try:
			data = json.loads(data)
		except json.JSONDecodeError:
			frappe.throw("Invalid PAI authoring request.", frappe.ValidationError)
	if not isinstance(data, dict):
		frappe.throw("Invalid PAI authoring request.", frappe.ValidationError)
	brief = data.get("training_brief")
	if not isinstance(data.get("title"), str) or not data["title"].strip():
		frappe.throw("A course title is required.", frappe.ValidationError)
	if not isinstance(brief, dict) or not isinstance(brief.get("goal"), str) or not brief["goal"].strip():
		frappe.throw("A training goal is required.", frappe.ValidationError)
	for fieldname in ("learner_refs", "learning_need_refs", "objective_refs"):
		if fieldname in data and not isinstance(data[fieldname], list):
			frappe.throw(f"{fieldname} must be a list.", frappe.ValidationError)
	return data


def _normalize_idempotency_key(value):
	"""Accept an opaque, bounded browser retry key without treating it as input data."""
	if not isinstance(value, str) or not _IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
		frappe.throw("A valid authoring request retry key is required.", frappe.ValidationError)
	return value


def _get_or_create_authoring_request(data, idempotency_key):
	"""Persist a local create intent before calling PAI.

	The unique local key and the identical upstream ``Idempotency-Key`` make a
	retry recover the same PAI request if the LMS loses the response between the
	remote create and local audit update.
	"""
	existing_name = frappe.db.exists("PAI Request", {"idempotency_key": idempotency_key})
	if existing_name:
		doc = frappe.get_doc("PAI Request", existing_name)
		if doc.owner != frappe.session.user or doc.request_type != "Course Authoring":
			frappe.throw("PAI authoring request retry is not permitted.", frappe.PermissionError)
		return doc

	values = {
		"doctype": "PAI Request",
		"request_type": "Course Authoring",
		"status": "Creating",
		"title": data["title"],
		"idempotency_key": idempotency_key,
		"request_payload": json.dumps(_get_safe_request_summary(data), ensure_ascii=False),
	}
	try:
		return frappe.get_doc(values).insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		# A concurrent browser retry raced the first exists() check. Read the
		# winner and apply the same owner/type guard before reusing its key.
		doc = frappe.get_doc("PAI Request", {"idempotency_key": idempotency_key})
		if doc.owner != frappe.session.user or doc.request_type != "Course Authoring":
			frappe.throw("PAI authoring request retry is not permitted.", frappe.PermissionError)
		return doc


def _get_safe_request_summary(data):
	"""Return audit metadata without retaining an author prompt in Frappe.

	The full brief belongs to PAI.  Keeping the text locally would make the LMS
	database another store for potentially sensitive prompts, audience details,
	or author notes.  This summary supports support/audit correlation without
	copying that content across the boundary.
	"""
	brief = data.get("training_brief", {})
	return {
		"schema_version": "v1",
		"title": data["title"].strip(),
		"language": brief.get("language") or None,
		"learner_reference_count": len(data.get("learner_refs", [])),
		"learning_need_reference_count": len(data.get("learning_need_refs", [])),
		"objective_reference_count": len(data.get("objective_refs", [])),
		"has_duration_constraint": bool(brief.get("duration_constraint")),
		"has_completion_context": bool(brief.get("target_completion_context")),
		"desired_outcome_count": len(brief.get("desired_outcomes", [])),
		"prerequisite_count": len(brief.get("prerequisites", [])),
		"has_author_notes": bool(brief.get("notes")),
	}


def _parse_brief_revision(data):
	"""Validate a bounded brief revision before forwarding it to PAI.

	The editable brief remains an authoring artifact in PAI. Frappe validates the
	shape only and deliberately does not persist the revision payload.
	"""
	if isinstance(data, str):
		try:
			data = json.loads(data)
		except json.JSONDecodeError:
			frappe.throw("Invalid PAI brief revision.", frappe.ValidationError)
	if not isinstance(data, dict):
		frappe.throw("Invalid PAI brief revision.", frappe.ValidationError)

	allowed_fields = {
		"training_goal",
		"desired_outcomes",
		"prerequisites",
		"constraints",
		"learning_horizon",
		"expected_learning_effort",
		"excluded_scope",
		"emphasis",
		"author_feedback",
	}
	if not data or set(data).difference(allowed_fields):
		frappe.throw("Invalid PAI brief revision.", frappe.ValidationError)

	list_fields = {"desired_outcomes", "prerequisites", "excluded_scope", "emphasis"}
	text_fields = {
		"training_goal",
		"learning_horizon",
		"expected_learning_effort",
		"author_feedback",
	}
	cleaned = {}
	for fieldname, value in data.items():
		if fieldname in text_fields:
			if not isinstance(value, str) or len(value.strip()) > 5000:
				frappe.throw("Invalid PAI brief revision.", frappe.ValidationError)
			cleaned[fieldname] = value.strip()
		elif fieldname in list_fields:
			if (
				not isinstance(value, list)
				or len(value) > 100
				or any(not isinstance(item, str) or not item.strip() or len(item.strip()) > 1000 for item in value)
			):
				frappe.throw("Invalid PAI brief revision.", frappe.ValidationError)
			cleaned[fieldname] = [item.strip() for item in value]
		else:
			if (
				not isinstance(value, dict)
				or len(value) > 50
				or any(
					not isinstance(key, str)
					or not isinstance(item, str)
					or len(key) > 200
					or len(item) > 1000
					for key, item in value.items()
				)
			):
				frappe.throw("Invalid PAI brief revision.", frappe.ValidationError)
			cleaned[fieldname] = value
	return cleaned


def _get_request(name):
	doc = frappe.get_doc("PAI Request", name)
	if doc.request_type != "Course Authoring":
		frappe.throw("This is not a course-authoring request.", frappe.ValidationError)
	if doc.owner != frappe.session.user and not _is_admin():
		frappe.throw("PAI request access is not permitted.", frappe.PermissionError)
	return doc


def _call_pai(method, path, *, payload=None, idempotency_key=None):
	try:
		return PAIClient().request(
			method,
			path,
			user=frappe.session.user,
			payload=payload,
			idempotency_key=idempotency_key,
		)
	except PAIClientError as exc:
		frappe.throw(str(exc), frappe.ValidationError)


def _sync_request_status(doc, pai_request):
	status = pai_request.get("status")
	if status and doc.status != status:
		doc.db_set("status", status, update_modified=False)
	correlation_id = _get_last_correlation_id()
	if correlation_id:
		doc.db_set("last_correlation_id", correlation_id, update_modified=False)


def _get_course_authoring_result(doc, result_ref):
	if not isinstance(result_ref, str) or not result_ref.strip():
		frappe.throw("A PAI course draft reference is required.", frappe.ValidationError)
	result = _call_pai("GET", f"/api/v1/course-authoring/results/{result_ref}")["data"]
	if result.get("course_authoring_request_ref") != doc.pai_request_id:
		frappe.throw("PAI course draft access is not permitted.", frappe.PermissionError)
	return result


def _resolve_course_instructor(request_doc, instructor=None):
	instructor = (instructor or request_doc.owner).strip() if isinstance(instructor or request_doc.owner, str) else ""
	if not instructor or not frappe.db.exists("User", instructor):
		frappe.throw("A valid LMS Instructor is required for course import.", frappe.ValidationError)
	if "Instructor" not in frappe.get_roles(instructor):
		frappe.throw("The selected LMS user does not have the Instructor role.", frappe.ValidationError)
	if instructor != request_doc.owner and not _is_admin():
		frappe.throw("Only a Moderator or System Manager can select another instructor.", frappe.PermissionError)
	return instructor


@frappe.whitelist()
def list_lms_instructors():
	"""Return enabled Instructor accounts for an administrator's import choice.

	The selected account is still revalidated by ``_resolve_course_instructor``
	at materialization time. This list is a UI convenience, not an authority
	boundary, and is intentionally unavailable to ordinary Instructors.
	"""
	_require_admin_access()
	instructors = frappe.get_all(
		"Has Role",
		filters={"role": "Instructor", "parenttype": "User"},
		pluck="parent",
	)
	if not instructors:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", instructors], "enabled": 1},
		fields=["name", "full_name", "email"],
		order_by="full_name asc, name asc",
	)


@frappe.whitelist()
def get_pai_studio_status():
	"""Return setup health without exposing service URLs or any secret."""
	_require_authoring_access()
	settings = frappe.get_single("PAI Settings")
	missing_settings = _get_missing_pai_settings(settings)
	return {
		"enabled": bool(settings.enabled),
		"service_configured": not missing_settings,
		"identity_configured": bool(
			frappe.db.exists(
				"PAI User Identity", {"user": frappe.session.user, "enabled": 1}
			)
		),
		"missing_configuration": missing_settings if _has_any_role(("System Manager",)) else [],
	}


@frappe.whitelist()
def create_course_authoring_request(data, idempotency_key=None):
	"""Create a draft request in PAI and retain an auditable local reference."""
	_require_authoring_access()
	data = _parse_payload(data)
	idempotency_key = _normalize_idempotency_key(idempotency_key)
	doc = _get_or_create_authoring_request(data, idempotency_key)
	if doc.pai_request_id:
		return {"name": doc.name, "pai_request_id": doc.pai_request_id, "status": doc.status}
	result = _call_pai(
		"POST",
		"/api/v1/course-authoring/requests",
		payload={"schema_version": "v1", "data": data},
		idempotency_key=f"frappe:{idempotency_key}",
	)
	accepted = result["data"]
	if not isinstance(accepted.get("request_id"), str) or not accepted["request_id"]:
		frappe.throw("PAI service returned an invalid authoring request.", frappe.ValidationError)
	pai_request_id = accepted["request_id"]
	status = accepted.get("status", "DRAFT")
	doc.db_set("pai_request_id", pai_request_id, update_modified=False)
	doc.db_set("status", status, update_modified=False)
	doc.db_set("last_correlation_id", _get_last_correlation_id(), update_modified=False)
	return {"name": doc.name, "pai_request_id": pai_request_id, "status": status}


@frappe.whitelist()
def list_course_authoring_requests():
	"""List local requests. Instructors see only their own requests."""
	_require_authoring_access()
	filters = {"request_type": "Course Authoring"}
	if not _is_admin():
		filters["owner"] = frappe.session.user
	return frappe.get_all(
		"PAI Request",
		filters=filters,
		fields=["name", "title", "status", "pai_request_id", "owner", "creation", "modified"],
		order_by="modified desc",
		limit_page_length=100,
	)


@frappe.whitelist()
def get_course_authoring_request(name):
	_require_authoring_access()
	doc = _get_request(name)
	result = _call_pai("GET", f"/api/v1/course-authoring/requests/{doc.pai_request_id}")
	_sync_request_status(doc, result["data"])
	return {"request": doc.as_dict(), "pai": result["data"]}


@frappe.whitelist()
def list_authoring_brief_revisions(name):
	_require_authoring_access()
	doc = _get_request(name)
	return _call_pai("GET", f"/api/v1/course-authoring/requests/{doc.pai_request_id}/revisions")["data"]


@frappe.whitelist()
def clarify_authoring_brief(name):
	_require_authoring_access()
	doc = _get_request(name)
	return _call_pai(
		"POST",
		f"/api/v1/course-authoring/requests/{doc.pai_request_id}/clarify",
		idempotency_key=f"frappe:{frappe.generate_hash(length=24)}",
	)["data"]


@frappe.whitelist()
def revise_authoring_brief(name, data):
	"""Create a new PAI-owned brief revision for the local request owner."""
	_require_authoring_access()
	doc = _get_request(name)
	changes = _parse_brief_revision(data)
	return _call_pai(
		"POST",
		f"/api/v1/course-authoring/requests/{doc.pai_request_id}/revisions",
		payload={"schema_version": "v1", "data": changes},
		idempotency_key=f"frappe:{frappe.generate_hash(length=24)}",
	)["data"]


@frappe.whitelist()
def confirm_authoring_brief(name, revision_id):
	_require_authoring_access()
	doc = _get_request(name)
	if not isinstance(revision_id, str) or not revision_id:
		frappe.throw("An authoring brief revision is required.", frappe.ValidationError)
	return _call_pai(
		"POST",
		f"/api/v1/course-authoring/requests/{doc.pai_request_id}/revisions/{revision_id}/confirm",
	)["data"]


@frappe.whitelist()
def plan_course_authoring_request(name):
	_require_authoring_access()
	doc = _get_request(name)
	result = _call_pai(
		"POST",
		f"/api/v1/course-authoring/requests/{doc.pai_request_id}/plan",
		idempotency_key=f"frappe:{frappe.generate_hash(length=24)}",
	)
	return result["data"]


@frappe.whitelist()
def get_course_authoring_plan(name):
	_require_authoring_access()
	doc = _get_request(name)
	return _call_pai("GET", f"/api/v1/course-authoring/requests/{doc.pai_request_id}/plan")["data"]


@frappe.whitelist()
def list_curriculum_plans(name):
	_require_authoring_access()
	doc = _get_request(name)
	return _call_pai("GET", f"/api/v1/course-authoring/requests/{doc.pai_request_id}/curriculum-plans")["data"]


@frappe.whitelist()
def get_curriculum_plan(name, plan_id):
	_require_authoring_access()
	doc = _get_request(name)
	if not isinstance(plan_id, str) or not plan_id.strip():
		frappe.throw("A curriculum plan is required.", frappe.ValidationError)
	return _call_pai("GET", f"/api/v1/course-authoring/curriculum-plans/{plan_id}")["data"]


def _parse_curriculum_feedback(data):
	if isinstance(data, str):
		try:
			data = json.loads(data)
		except json.JSONDecodeError:
			frappe.throw("Invalid curriculum feedback.", frappe.ValidationError)
	if not isinstance(data, dict):
		frappe.throw("Invalid curriculum feedback.", frappe.ValidationError)
	return data


@frappe.whitelist()
def preview_curriculum_feedback(name, plan_id, feedback):
	_require_authoring_access()
	doc = _get_request(name)
	if not isinstance(plan_id, str) or not plan_id.strip():
		frappe.throw("A curriculum plan is required.", frappe.ValidationError)
	return _call_pai(
		"POST",
		f"/api/v1/course-authoring/curriculum-plans/{plan_id}/feedback/preview",
		payload={"feedback": _parse_curriculum_feedback(feedback)},
	)["data"]


@frappe.whitelist()
def revise_curriculum_plan(name, plan_id, feedback, rationale=None):
	_require_authoring_access()
	doc = _get_request(name)
	if not isinstance(plan_id, str) or not plan_id.strip():
		frappe.throw("A curriculum plan is required.", frappe.ValidationError)
	if rationale is not None and not isinstance(rationale, str):
		frappe.throw("Curriculum revision rationale must be text.", frappe.ValidationError)
	return _call_pai(
		"POST",
		f"/api/v1/course-authoring/curriculum-plans/{plan_id}/feedback",
		payload={
			"feedback": _parse_curriculum_feedback(feedback),
			"rationale": rationale.strip() if isinstance(rationale, str) and rationale.strip() else None,
		},
	)["data"]


@frappe.whitelist()
def review_course_authoring_plan(name, plan_id):
	_require_authoring_access()
	_get_request(name)
	if not isinstance(plan_id, str) or not plan_id:
		frappe.throw("A curriculum plan is required.", frappe.ValidationError)
	return _call_pai("POST", f"/api/v1/course-authoring/curriculum-plans/{plan_id}/review")["data"]


@frappe.whitelist()
def confirm_course_authoring_plan(name, plan_id):
	_require_authoring_access()
	_get_request(name)
	if not isinstance(plan_id, str) or not plan_id:
		frappe.throw("A curriculum plan is required.", frappe.ValidationError)
	return _call_pai("POST", f"/api/v1/course-authoring/curriculum-plans/{plan_id}/confirm")["data"]


@frappe.whitelist()
def generate_course_authoring_request(name):
	_require_authoring_access()
	doc = _get_request(name)
	return _call_pai(
		"POST",
		f"/api/v1/course-authoring/requests/{doc.pai_request_id}/generate",
		idempotency_key=f"frappe:{frappe.generate_hash(length=24)}",
	)["data"]


@frappe.whitelist()
def get_course_generation_progress(name):
	_require_authoring_access()
	doc = _get_request(name)
	return _call_pai("GET", f"/api/v1/course-authoring/requests/{doc.pai_request_id}/generation")["data"]


@frappe.whitelist()
def retry_course_generation(name):
	"""Retry only failed lessons in the latest durable PAI generation plan."""
	_require_authoring_access()
	doc = _get_request(name)
	return _call_pai(
		"POST",
		f"/api/v1/course-authoring/requests/{doc.pai_request_id}/generation/retry",
		idempotency_key=f"frappe:{frappe.generate_hash(length=24)}",
	)["data"]


@frappe.whitelist()
def list_course_authoring_results(name):
	_require_authoring_access()
	doc = _get_request(name)
	return _call_pai("GET", f"/api/v1/course-authoring/requests/{doc.pai_request_id}/results")["data"]


@frappe.whitelist()
def get_course_authoring_result(name, result_ref):
	"""Read one PAI draft only after binding it to the local authoring request."""
	_require_authoring_access()
	doc = _get_request(name)
	return _get_course_authoring_result(doc, result_ref)


@frappe.whitelist()
def approve_course_authoring_result(name, result_ref):
	_require_authoring_access()
	doc = _get_request(name)
	_get_course_authoring_result(doc, result_ref)
	return _call_pai("POST", f"/api/v1/course-authoring/results/{result_ref}/approve")["data"]


@frappe.whitelist()
def mark_course_authoring_result_ready(name, result_ref):
	"""Keep the human PAI review gate explicit before any LMS import."""
	_require_authoring_access()
	doc = _get_request(name)
	_get_course_authoring_result(doc, result_ref)
	return _call_pai(
		"POST", f"/api/v1/course-authoring/results/{result_ref}/ready-for-materialization"
	)["data"]


@frappe.whitelist()
def materialize_course_authoring_result(name, result_ref, instructor=None):
	"""Create one unpublished LMS Course from a reviewed PAI result.

	This endpoint deliberately does not publish, enroll learners, create quizzes,
	or change an existing course. A PAI result can only map to one LMS course.
	"""
	_require_authoring_access()
	request_doc = _get_request(name)
	result = _get_course_authoring_result(request_doc, result_ref)

	existing_name = frappe.db.exists("PAI Course Import", {"result_ref": result_ref})
	if existing_name:
		import_doc = frappe.get_doc("PAI Course Import", existing_name)
		if import_doc.pai_request != request_doc.name:
			frappe.throw("PAI course draft access is not permitted.", frappe.PermissionError)
		if import_doc.status == "Imported":
			return {
				"import_name": import_doc.name,
				"status": import_doc.status,
				"lms_course": import_doc.lms_course,
				"already_imported": True,
			}
		if import_doc.status == "Importing":
			frappe.throw("This PAI draft is already being imported. Refresh its status before retrying.", frappe.ValidationError)
	else:
		try:
			import_doc = frappe.get_doc(
				{
					"doctype": "PAI Course Import",
					"pai_request": request_doc.name,
					"result_ref": result_ref,
					"result_version": result.get("version", 1),
					"result_status": result.get("status"),
					"status": "Pending",
				}
			).insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			# The unique result_ref index is the concurrency guard. A concurrent
			# request may have created it after the initial exists() check.
			import_doc = frappe.get_doc("PAI Course Import", {"result_ref": result_ref})
			if import_doc.pai_request != request_doc.name:
				frappe.throw("PAI course draft access is not permitted.", frappe.PermissionError)
			if import_doc.status == "Imported":
				return {
					"import_name": import_doc.name,
					"status": import_doc.status,
					"lms_course": import_doc.lms_course,
					"already_imported": True,
				}
			frappe.throw("This PAI draft is already being imported. Refresh its status before retrying.", frappe.ValidationError)

	try:
		generated_course = get_generated_course(result)
		source_hash = get_source_hash(generated_course)
		if import_doc.source_hash and import_doc.source_hash != source_hash:
			frappe.throw("The PAI result changed; import its latest reviewed version instead.", frappe.ValidationError)
		import_doc.db_set("source_hash", source_hash, update_modified=False)
	except Exception as exc:
		import_doc.db_set("status", "Failed", update_modified=False)
		import_doc.db_set("error_code", "PAI_DRAFT_INVALID", update_modified=False)
		import_doc.db_set(
			"error_message", "The reviewed PAI draft could not be validated for LMS import.", update_modified=False
		)
		raise frappe.ValidationError("The reviewed PAI draft cannot be imported. Review the PAI draft and retry.") from exc

	resolved_instructor = _resolve_course_instructor(request_doc, instructor)
	import_doc.db_set("status", "Importing", update_modified=False)
	savepoint = f"pai_course_import_{frappe.generate_hash(length=12)}"
	frappe.db.savepoint(savepoint)
	try:
		course = materialize_course(import_doc, generated_course, resolved_instructor)
		frappe.db.release_savepoint(savepoint)
	except Exception as exc:
		frappe.db.rollback(save_point=savepoint)
		import_doc.db_set("status", "Failed", update_modified=False)
		import_doc.db_set("error_code", "LMS_MATERIALIZATION_FAILED", update_modified=False)
		import_doc.db_set(
			"error_message", "The LMS draft could not be created. Correct the reviewed draft and retry.",
			update_modified=False,
		)
		raise frappe.ValidationError("The LMS draft could not be created. Review the import record and retry.") from exc
	return {
		"import_name": import_doc.name,
		"status": "Imported",
		"lms_course": course.name,
		"already_imported": False,
	}


def _curriculum_import_response(import_doc, *, already_materialized, tree=None):
	tree = tree or _get_lms_draft_tree(import_doc.lms_course)
	return {
		"import_name": import_doc.name,
		"source_plan_ref": import_doc.source_plan_ref,
		"source_plan_version": import_doc.source_plan_version,
		"status": import_doc.status,
		"lms_course": import_doc.lms_course,
		"chapters": tree["chapters"],
		"lessons": tree["lessons"],
		"already_materialized": already_materialized,
	}


def _get_lms_draft_tree(course_name):
	chapters = frappe.get_all(
		"Course Chapter",
		filters={"course": course_name},
		fields=["name", "title"],
		order_by="creation asc",
	)
	lessons = frappe.get_all(
		"Course Lesson",
		filters={"course": course_name},
		fields=["name", "title", "chapter"],
		order_by="creation asc",
	)
	return {"chapters": chapters, "lessons": lessons}


@frappe.whitelist()
def materialize_curriculum_plan(name, plan_id, instructor=None):
	"""Materialize one confirmed canonical CurriculumPlan into an LMS draft.

	The browser supplies only the local request and exact plan references. The
	plan body is fetched from Core-AI with the authenticated server-side bridge;
	this endpoint never accepts an arbitrary curriculum payload and never calls
	any publish operation.
	"""
	_require_authoring_access()
	request_doc = _get_request(name)
	if not isinstance(plan_id, str) or not plan_id.strip():
		frappe.throw("A CurriculumPlan reference is required.", frappe.ValidationError)

	plan = _call_pai("GET", f"/api/v1/course-authoring/curriculum-plans/{plan_id}")["data"]
	if plan.get("plan_ref") != plan_id:
		frappe.throw("CurriculumPlan reference does not match the requested plan.", frappe.ValidationError)
	if plan.get("authoring_request_ref") != request_doc.pai_request_id:
		frappe.throw("CurriculumPlan access is not permitted.", frappe.PermissionError)
	try:
		spec = adapt_curriculum_plan(plan)
	except CurriculumMaterializationError as exc:
		frappe.throw(str(exc), frappe.ValidationError)

	existing_name = frappe.db.exists("PAI Course Import", {"source_plan_ref": spec.plan_ref})
	if existing_name:
		import_doc = frappe.get_doc("PAI Course Import", existing_name)
		if import_doc.pai_request != request_doc.name:
			frappe.throw("CurriculumPlan access is not permitted.", frappe.PermissionError)
		if import_doc.status == "Imported":
			return _curriculum_import_response(import_doc, already_materialized=True)
		if import_doc.status == "Importing":
			frappe.throw("This CurriculumPlan is already being materialized. Refresh its status before retrying.", frappe.ValidationError)
	else:
		try:
			import_doc = frappe.get_doc(
				{
					"doctype": "PAI Course Import",
					"pai_request": request_doc.name,
					"source_type": "Curriculum Plan",
					"source_plan_ref": spec.plan_ref,
					"source_plan_version": spec.version,
					"result_status": plan.get("status"),
					"status": "Pending",
				}
			).insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			import_doc = frappe.get_doc("PAI Course Import", {"source_plan_ref": spec.plan_ref})
			if import_doc.pai_request != request_doc.name:
				frappe.throw("CurriculumPlan access is not permitted.", frappe.PermissionError)
			if import_doc.status == "Imported":
				return _curriculum_import_response(import_doc, already_materialized=True)
			frappe.throw("This CurriculumPlan is already being materialized. Refresh its status before retrying.", frappe.ValidationError)

	resolved_instructor = _resolve_course_instructor(request_doc, instructor)
	import_doc.db_set("source_hash", get_plan_source_hash(plan), update_modified=False)
	import_doc.db_set("status", "Importing", update_modified=False)
	savepoint = f"pai_curriculum_materialization_{frappe.generate_hash(length=12)}"
	frappe.db.savepoint(savepoint)
	try:
		tree = create_lms_draft(spec, resolved_instructor)
		import_doc.db_set("lms_course", tree["course"]["name"], update_modified=False)
		import_doc.db_set("status", "Imported", update_modified=False)
		import_doc.db_set("imported_by", frappe.session.user, update_modified=False)
		import_doc.db_set("imported_on", now_datetime(), update_modified=False)
		import_doc.db_set("error_code", "", update_modified=False)
		import_doc.db_set("error_message", "", update_modified=False)
		frappe.db.release_savepoint(savepoint)
	except Exception as exc:
		frappe.db.rollback(save_point=savepoint)
		import_doc.db_set("status", "Failed", update_modified=False)
		import_doc.db_set("error_code", "LMS_CURRICULUM_MATERIALIZATION_FAILED", update_modified=False)
		import_doc.db_set(
			"error_message",
			"The LMS curriculum draft could not be created. Correct the confirmed plan and retry.",
			update_modified=False,
		)
		raise frappe.ValidationError("The LMS curriculum draft could not be created. Review the import record and retry.") from exc
	return _curriculum_import_response(import_doc, already_materialized=False, tree=tree)


@frappe.whitelist()
def create_evidence_case(document_kind, subject_user=None):
	"""Create local, raw-data-free evidence tracking before a PAI upload starts."""
	_require_evidence_access()
	if document_kind not in {"CV", "JD"}:
		frappe.throw("Document kind must be CV or JD.", frappe.ValidationError)
	subject_user = subject_user or frappe.session.user
	if subject_user != frappe.session.user and not _is_admin():
		frappe.throw("You can only create evidence cases for yourself.", frappe.PermissionError)
	if not frappe.db.exists("User", subject_user):
		frappe.throw("The evidence subject does not exist.", frappe.ValidationError)
	case = frappe.get_doc(
		{
			"doctype": "PAI Evidence Case",
			"subject_user": subject_user,
			"document_kind": document_kind,
			"status": "Draft",
			"submitted_by": frappe.session.user,
		}
	).insert(ignore_permissions=True)
	return {"name": case.name, "status": case.status, "subject_user": case.subject_user}


@frappe.whitelist()
def list_evidence_cases(subject_user=None):
	"""Return references and lifecycle state only; never raw source or extracted evidence."""
	_require_evidence_access()
	filters = {}
	if not _is_admin():
		filters["owner"] = frappe.session.user
	if subject_user:
		if subject_user != frappe.session.user and not _is_admin():
			frappe.throw("PAI Evidence access is not permitted.", frappe.PermissionError)
		filters["subject_user"] = subject_user
	return frappe.get_all(
		"PAI Evidence Case",
		filters=filters,
		fields=[
			"name",
			"subject_user",
			"document_kind",
			"status",
			"extraction_profile_ref",
			"profile_version",
			"safe_summary",
			"creation",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=100,
	)


@frappe.whitelist()
def create_semantic_policy(policy_id, policy_version, description, domain_pack_id, domain_pack_version, domain_pack_checksum):
	_require_admin_access()
	values = [policy_id, policy_version, description, domain_pack_id, domain_pack_version, domain_pack_checksum]
	if not all(isinstance(value, str) and value.strip() for value in values):
		frappe.throw("All semantic policy fields are required.", frappe.ValidationError)
	if frappe.db.exists("PAI Semantic Policy", {"policy_id": policy_id, "policy_version": policy_version}):
		frappe.throw("This semantic policy version already exists.", frappe.ValidationError)
	policy = frappe.get_doc({"doctype": "PAI Semantic Policy", "policy_id": policy_id.strip(), "policy_version": policy_version.strip(), "description": description.strip(), "domain_pack_id": domain_pack_id.strip(), "domain_pack_version": domain_pack_version.strip(), "domain_pack_checksum": domain_pack_checksum.strip(), "created_by": frappe.session.user}).insert(ignore_permissions=True)
	return {"name": policy.name, "status": policy.status}


@frappe.whitelist()
def list_semantic_policies():
	_require_authoring_access()
	filters = {} if _is_admin() else {"owner": frappe.session.user}
	return frappe.get_all("PAI Semantic Policy", filters=filters, fields=["name", "policy_id", "policy_version", "status", "description", "domain_pack_id", "domain_pack_version", "modified"], order_by="modified desc", limit_page_length=100)


@frappe.whitelist()
def activate_semantic_policy(name):
	_require_admin_access()
	policy = frappe.get_doc("PAI Semantic Policy", name)
	policy.db_set("status", "Active", update_modified=False)
	policy.db_set("reviewed_by", frappe.session.user, update_modified=False)
	policy.db_set("activated_on", now_datetime(), update_modified=False)
	return {"name": policy.name, "status": "Active"}


@frappe.whitelist()
def create_role_profile(title, requirements_summary="", semantic_policy=None):
	_require_authoring_access()
	if not isinstance(title, str) or not title.strip():
		frappe.throw("A role profile title is required.", frappe.ValidationError)
	values = {"doctype": "PAI Role Profile", "title": title.strip(), "requirements_summary": (requirements_summary or "").strip(), "owner_user": frappe.session.user}
	if semantic_policy:
		policy = frappe.get_doc("PAI Semantic Policy", semantic_policy)
		values.update({"semantic_policy": policy.name, "semantic_policy_version": policy.policy_version})
	profile = frappe.get_doc(values).insert(ignore_permissions=True)
	return {"name": profile.name, "status": profile.status}


@frappe.whitelist()
def list_role_profiles():
	_require_authoring_access()
	filters = {} if _is_admin() else {"owner": frappe.session.user}
	return frappe.get_all("PAI Role Profile", filters=filters, fields=["name", "title", "profile_version", "status", "semantic_policy", "semantic_policy_version", "quality_gate_status", "modified"], order_by="modified desc", limit_page_length=100)


@frappe.whitelist()
def review_role_profile(name, status, approval_note=""):
	_require_admin_access()
	if status not in {"In Review", "Needs Revision", "Provisional", "Active"}:
		frappe.throw("Invalid role profile review status.", frappe.ValidationError)
	profile = frappe.get_doc("PAI Role Profile", name)
	if status in {"Provisional", "Active"} and not profile.semantic_policy:
		frappe.throw("Pin a semantic policy before approving a role profile.", frappe.ValidationError)
	profile.db_set("status", status, update_modified=False)
	profile.db_set("reviewed_by", frappe.session.user, update_modified=False)
	profile.db_set("reviewed_on", now_datetime(), update_modified=False)
	profile.db_set("approval_note", (approval_note or "").strip(), update_modified=False)
	return {"name": profile.name, "status": status}


@frappe.whitelist()
def create_capability_analysis(subject_user=None, target_role_profile=None):
	_require_evidence_access()
	subject_user = subject_user or frappe.session.user
	if subject_user != frappe.session.user and not _is_admin():
		frappe.throw("You can only create an analysis for yourself.", frappe.PermissionError)
	if not target_role_profile:
		frappe.throw("A target role profile is required.", frappe.ValidationError)
	role_profile = frappe.get_doc("PAI Role Profile", target_role_profile)
	analysis = frappe.get_doc({"doctype":"PAI Capability Analysis","subject_user":subject_user,"target_role_profile":role_profile.name,"target_role_profile_version":role_profile.profile_version,"status":"Draft"}).insert(ignore_permissions=True)
	return {"name":analysis.name,"status":analysis.status}


@frappe.whitelist()
def list_capability_analyses():
	_require_evidence_access()
	filters = {} if _is_admin() else {"owner": frappe.session.user}
	return frappe.get_all("PAI Capability Analysis", filters=filters, fields=["name","subject_user","status","target_role_profile","gap_count","high_priority_gap_count","safe_summary","modified"], order_by="modified desc", limit_page_length=100)


@frappe.whitelist()
def list_assessment_reviews():
	_require_evidence_access()
	filters = {} if _is_admin() else {"owner": frappe.session.user}
	return frappe.get_all("PAI Assessment Review", filters=filters, fields=["name", "subject_user", "status", "score_projection", "rubric_version", "modified"], order_by="modified desc", limit_page_length=100)


@frappe.whitelist()
def list_competency_projections():
	_require_evidence_access()
	filters = {} if _is_admin() else {"owner": frappe.session.user}
	return frappe.get_all("PAI Competency Projection", filters=filters, fields=["name", "subject_user", "competency_id", "level", "status", "valid_until", "modified"], order_by="modified desc", limit_page_length=100)


@frappe.whitelist()
def create_learning_path(title, development_goal, source_capability_analysis=None, target_completion_date=None):
	_require_evidence_access()
	if not isinstance(title, str) or not title.strip() or not isinstance(development_goal, str) or not development_goal.strip():
		frappe.throw("Learning path title and development goal are required.", frappe.ValidationError)
	path = frappe.get_doc({"doctype":"PAI Learning Path","title":title.strip(),"subject_user":frappe.session.user,"development_goal":development_goal.strip(),"source_capability_analysis":source_capability_analysis,"target_completion_date":target_completion_date,"status":"Draft"}).insert(ignore_permissions=True)
	return {"name":path.name,"status":path.status}


@frappe.whitelist()
def list_learning_paths():
	_require_evidence_access()
	filters = {} if _is_admin() else {"owner": frappe.session.user}
	return frappe.get_all("PAI Learning Path", filters=filters, fields=["name","title","path_version","status","lms_program","target_completion_date","modified"], order_by="modified desc", limit_page_length=100)


@frappe.whitelist()
def create_credential_request(credential_type, subject_user=None):
	_require_evidence_access()
	if credential_type not in {"Competency", "Completion", "Learning Achievement"}:
		frappe.throw("Invalid credential type.", frappe.ValidationError)
	subject_user = subject_user or frappe.session.user
	if subject_user != frappe.session.user and not _is_admin():
		frappe.throw("You can only request a credential for yourself.", frappe.PermissionError)
	link = frappe.get_doc({"doctype":"PAI Credential Link","subject_user":subject_user,"credential_type":credential_type,"status":"Requested","requested_by":frappe.session.user}).insert(ignore_permissions=True)
	return {"name":link.name,"status":link.status}


@frappe.whitelist()
def list_credential_links():
	_require_evidence_access()
	filters = {} if _is_admin() else {"owner": frappe.session.user}
	return frappe.get_all("PAI Credential Link", filters=filters, fields=["name","subject_user","credential_type","status","pai_credential_ref","lms_certificate","valid_until","modified"], order_by="modified desc", limit_page_length=100)


@frappe.whitelist()
def review_credential_request(name, status, status_reason=""):
	"""Allow an administrator to approve or reject a request before PAI issuance.

	Issuance, revocation and expiry remain integration-only lifecycle events.  This
	keeps a local review action from becoming a way to mint a certificate.
	"""
	_require_admin_access()
	if status not in {"Approved", "Rejected"}:
		frappe.throw("A credential request can only be approved or rejected here.", frappe.ValidationError)
	link = frappe.get_doc("PAI Credential Link", name)
	if link.status != "Requested":
		frappe.throw("Only requested credentials can be reviewed.", frappe.ValidationError)
	link.db_set("status", status, update_modified=False)
	link.db_set("approved_by", frappe.session.user, update_modified=False)
	link.db_set("status_reason", (status_reason or "").strip(), update_modified=False)
	return {"name": link.name, "status": status}


@frappe.whitelist()
def record_operational_event(
	event_type,
	severity,
	safe_summary,
	source_system="Frappe",
	correlation_id="",
	entity_reference="",
):
	"""Record a redacted operational signal without exposing PAI internals."""
	_require_admin_access()
	if event_type not in {"Audit", "Health", "Retry", "Dead Letter Queue", "Recovery", "Retention", "Deletion"}:
		frappe.throw("Invalid operational event type.", frappe.ValidationError)
	if severity not in {"Info", "Warning", "Error", "Critical"}:
		frappe.throw("Invalid operational event severity.", frappe.ValidationError)
	if source_system not in {"Frappe", "PAI"}:
		frappe.throw("Invalid operational event source.", frappe.ValidationError)
	if not isinstance(safe_summary, str) or not safe_summary.strip():
		frappe.throw("A redacted operational summary is required.", frappe.ValidationError)
	event = frappe.get_doc(
		{
			"doctype": "PAI Operational Event",
			"event_type": event_type,
			"source_system": source_system,
			"severity": severity,
			"status": "Recorded",
			"occurred_on": now_datetime(),
			"correlation_id": (correlation_id or "").strip(),
			"entity_reference": (entity_reference or "").strip(),
			"safe_summary": safe_summary.strip(),
		}
	).insert(ignore_permissions=True)
	return {"name": event.name, "status": event.status}


@frappe.whitelist()
def list_operational_events():
	_require_admin_access()
	return frappe.get_all(
		"PAI Operational Event",
		fields=["name", "event_type", "source_system", "severity", "status", "occurred_on", "correlation_id", "safe_summary", "modified"],
		order_by="occurred_on desc",
		limit_page_length=100,
	)


@frappe.whitelist()
def resolve_operational_event(name, remediation_summary=""):
	_require_admin_access()
	event = frappe.get_doc("PAI Operational Event", name)
	if event.status == "Resolved":
		return {"name": event.name, "status": event.status}
	event.db_set("status", "Resolved", update_modified=False)
	event.db_set("remediation_summary", (remediation_summary or "").strip(), update_modified=False)
	event.db_set("resolved_by", frappe.session.user, update_modified=False)
	event.db_set("resolved_on", now_datetime(), update_modified=False)
	return {"name": event.name, "status": "Resolved"}


@frappe.whitelist()
def create_privacy_request(request_type, subject_user=None, safe_scope_summary=""):
	_require_evidence_access()
	if request_type not in {"Retention Review", "Deletion"}:
		frappe.throw("Invalid privacy request type.", frappe.ValidationError)
	subject_user = subject_user or frappe.session.user
	if subject_user != frappe.session.user and not _is_admin():
		frappe.throw("You can only request privacy action for yourself.", frappe.PermissionError)
	request = frappe.get_doc(
		{
			"doctype": "PAI Privacy Request",
			"subject_user": subject_user,
			"request_type": request_type,
			"status": "Requested",
			"requested_on": now_datetime(),
			"requested_by": frappe.session.user,
			"safe_scope_summary": (safe_scope_summary or "").strip(),
		}
	).insert(ignore_permissions=True)
	return {"name": request.name, "status": request.status}


@frappe.whitelist()
def list_privacy_requests():
	_require_evidence_access()
	filters = {} if _is_admin() else {"owner": frappe.session.user}
	return frappe.get_all(
		"PAI Privacy Request",
		filters=filters,
		fields=["name", "subject_user", "request_type", "status", "requested_on", "pai_request_ref", "modified"],
		order_by="requested_on desc",
		limit_page_length=100,
	)


@frappe.whitelist()
def review_privacy_request(name, status, outcome_summary=""):
	"""Accept or reject a local request; PAI alone later records completion."""
	_require_admin_access()
	if status not in {"Accepted", "Rejected"}:
		frappe.throw("A privacy request can only be accepted or rejected here.", frappe.ValidationError)
	request = frappe.get_doc("PAI Privacy Request", name)
	if request.status != "Requested":
		frappe.throw("Only requested privacy actions can be reviewed.", frappe.ValidationError)
	request.db_set("status", status, update_modified=False)
	request.db_set("outcome_summary", (outcome_summary or "").strip(), update_modified=False)
	request.db_set("reviewed_by", frappe.session.user, update_modified=False)
	request.db_set("reviewed_on", now_datetime(), update_modified=False)
	return {"name": request.name, "status": status}


@frappe.whitelist()
def check_pai_runtime_health():
	"""Check PAI readiness and record only a local, redacted health signal."""
	_require_admin_access()
	settings = frappe.get_single("PAI Settings")
	if not settings.service_url:
		frappe.throw("PAI Service URL is not configured.", frappe.ValidationError)
	severity = "Info"
	summary = "PAI runtime readiness check passed."
	try:
		PAIClient(require_enabled=False).check_readiness()
	except PAIClientError as exc:
		severity = "Error"
		summary = str(exc)
	event = frappe.get_doc(
		{
			"doctype": "PAI Operational Event",
			"event_type": "Health",
			"source_system": "PAI",
			"severity": severity,
			"status": "Recorded" if severity == "Info" else "Failed",
			"occurred_on": now_datetime(),
			"correlation_id": _get_last_correlation_id(),
			"safe_summary": summary,
		}
	).insert(ignore_permissions=True)
	return {"ready": severity == "Info", "event": event.name}


def _get_last_correlation_id():
	try:
		return getattr(frappe.flags, "pai_last_correlation_id", "")
	except RuntimeError:
		return ""
