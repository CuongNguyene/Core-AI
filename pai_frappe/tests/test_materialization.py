from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import ANY, patch

import frappe

from pai_frappe.api import (
	_get_course_authoring_result,
	approve_course_authoring_result,
	get_course_authoring_result,
	list_lms_instructors,
	mark_course_authoring_result_ready,
	materialize_course_authoring_result,
	revise_authoring_brief,
)
from pai_frappe.materialization import (
	get_generated_course,
	get_source_hash,
	render_lesson_body,
)


def _result(status="READY_FOR_MATERIALIZATION"):
	return {
		"id": "result-001",
		"course_authoring_request_ref": "pai-request-001",
		"status": status,
		"generated_course": {
			"course": {"title": "Safe course", "description": "Course description"},
			"modules": [
				{
					"title": "Module 1",
					"order": 1,
					"lessons": [
						{
							"title": "Lesson 1",
							"order": 1,
							"sections": [{"title": "Introduction", "content": "Hello", "order": 1}],
						}
					],
				}
			],
		},
	}


def _raise_validation_error(message, exception_class):
	raise exception_class(message)


class TestCourseMaterialization(TestCase):
	def test_generated_course_is_deterministically_hashed(self):
		course = get_generated_course(_result())

		self.assertEqual(get_source_hash(course), get_source_hash(course))

	def test_generated_course_rejects_duplicate_module_order(self):
		result = _result()
		duplicate = _result()["generated_course"]["modules"][0]
		result["generated_course"]["modules"].append(duplicate)

		with patch("pai_frappe.materialization.frappe.throw", side_effect=_raise_validation_error):
			with self.assertRaises(frappe.ValidationError):
				get_generated_course(result)

	def test_generated_course_rejects_unstructured_lesson_section(self):
		result = _result()
		result["generated_course"]["modules"][0]["lessons"][0]["sections"] = ["not a section"]

		with patch("pai_frappe.materialization.frappe.throw", side_effect=_raise_validation_error):
			with self.assertRaises(frappe.ValidationError):
				get_generated_course(result)

	def test_generated_course_rejects_scalar_section_steps(self):
		result = _result()
		result["generated_course"]["modules"][0]["lessons"][0]["sections"][0]["steps"] = "not a list"

		with patch("pai_frappe.materialization.frappe.throw", side_effect=_raise_validation_error):
			with self.assertRaises(frappe.ValidationError):
				get_generated_course(result)

	def test_generated_course_rejects_non_positive_lesson_order(self):
		result = _result()
		result["generated_course"]["modules"][0]["lessons"][0]["order"] = 0

		with patch("pai_frappe.materialization.frappe.throw", side_effect=_raise_validation_error):
			with self.assertRaises(frappe.ValidationError):
				get_generated_course(result)

	def test_lesson_body_strips_html_and_keeps_structure(self):
		body = render_lesson_body(
			[
				{
					"title": "<b>Practice</b>",
					"content": "<script>alert(1)</script>Read this",
					"steps": ["First step"],
					"success_criteria": ["Complete the task"],
					"order": 1,
				}
			]
		)

		self.assertIn("## Practice", body)
		self.assertIn("### Steps", body)
		self.assertNotIn("<script>", body)

	def test_lesson_body_neutralizes_lms_embed_markers(self):
		body = render_lesson_body(
			[
				{
					"title": "Safety",
					"content": '{{ Embed ("https://untrusted.example") }}',
					"order": 1,
				}
			]
		)

		self.assertNotIn("{{ Embed", body)
		self.assertIn("{\u200b{ Embed", body)

	@patch("pai_frappe.materialization.frappe.throw")
	def test_generated_course_requires_ready_review_state(self, throw):
		get_generated_course(_result(status="APPROVED"))

		throw.assert_called_once_with(
			"Only a PAI draft marked READY_FOR_MATERIALIZATION can be imported.",
			frappe.ValidationError,
		)

	@patch("pai_frappe.api.frappe.get_all")
	@patch("pai_frappe.api._require_admin_access")
	def test_list_lms_instructors_is_admin_only_and_returns_enabled_users(self, require_admin, get_all):
		get_all.side_effect = [
			["instructor-a@example.com"],
			[
				{
					"name": "instructor-a@example.com",
					"full_name": "Instructor A",
					"email": "instructor-a@example.com",
				}
			],
		]

		instructors = list_lms_instructors.__wrapped__()

		self.assertEqual(instructors[0]["name"], "instructor-a@example.com")
		require_admin.assert_called_once()
		self.assertEqual(get_all.call_args_list[0].args[0], "Has Role")
		self.assertEqual(get_all.call_args_list[1].args[0], "User")

	@patch("pai_frappe.api._call_pai")
	def test_result_must_belong_to_local_request(self, call_pai):
		call_pai.return_value = {"data": _result()}
		doc = SimpleNamespace(pai_request_id="pai-request-001")

		result = _get_course_authoring_result(doc, "result-001")

		self.assertEqual(result["id"], "result-001")
		call_pai.assert_called_once_with("GET", "/api/v1/course-authoring/results/result-001")

	@patch("pai_frappe.api.frappe.throw")
	@patch("pai_frappe.api._call_pai")
	def test_result_from_another_request_is_rejected(self, call_pai, throw):
		call_pai.return_value = {"data": _result()}
		doc = SimpleNamespace(pai_request_id="pai-request-other")

		_get_course_authoring_result(doc, "result-001")

		throw.assert_called_once_with("PAI course draft access is not permitted.", frappe.PermissionError)

	@patch("pai_frappe.api._get_course_authoring_result")
	@patch("pai_frappe.api._get_request")
	@patch("pai_frappe.api._require_authoring_access")
	def test_get_result_endpoint_uses_bound_local_request(self, require_access, get_request, get_result):
		doc = SimpleNamespace(name="PAI-REQUEST-001")
		result = _result()
		get_request.return_value = doc
		get_result.return_value = result

		self.assertEqual(get_course_authoring_result.__wrapped__("PAI-REQUEST-001", "result-001"), result)
		require_access.assert_called_once()
		get_result.assert_called_once_with(doc, "result-001")

	@patch("pai_frappe.api._call_pai")
	@patch("pai_frappe.api._get_course_authoring_result")
	@patch("pai_frappe.api._get_request")
	@patch("pai_frappe.api._require_authoring_access")
	def test_approve_result_endpoint_calls_pai_after_ownership_check(
		self, require_access, get_request, get_result, call_pai
	):
		get_request.return_value = SimpleNamespace(name="PAI-REQUEST-001")
		call_pai.return_value = {"data": {"status": "APPROVED"}}

		result = approve_course_authoring_result.__wrapped__("PAI-REQUEST-001", "result-001")

		self.assertEqual(result["status"], "APPROVED")
		get_result.assert_called_once_with(get_request.return_value, "result-001")
		call_pai.assert_called_once_with("POST", "/api/v1/course-authoring/results/result-001/approve")

	@patch("pai_frappe.api._call_pai")
	@patch("pai_frappe.api._get_course_authoring_result")
	@patch("pai_frappe.api._get_request")
	@patch("pai_frappe.api._require_authoring_access")
	def test_ready_endpoint_calls_pai_after_ownership_check(
		self, require_access, get_request, get_result, call_pai
	):
		get_request.return_value = SimpleNamespace(name="PAI-REQUEST-001")
		call_pai.return_value = {"data": {"status": "READY_FOR_MATERIALIZATION"}}

		result = mark_course_authoring_result_ready.__wrapped__("PAI-REQUEST-001", "result-001")

		self.assertEqual(result["status"], "READY_FOR_MATERIALIZATION")
		get_result.assert_called_once_with(get_request.return_value, "result-001")
		call_pai.assert_called_once_with(
			"POST", "/api/v1/course-authoring/results/result-001/ready-for-materialization"
		)

	@patch("pai_frappe.api._call_pai")
	@patch("pai_frappe.api._get_request")
	@patch("pai_frappe.api._require_authoring_access")
	def test_revise_brief_sends_a_new_pai_owned_revision(
		self, require_access, get_request, call_pai
	):
		get_request.return_value = SimpleNamespace(pai_request_id="pai-request-001")
		call_pai.return_value = {"data": {"id": "revision-002", "status": "DRAFT"}}

		response = revise_authoring_brief.__wrapped__(
			"PAI-REQUEST-001",
			{"training_goal": "Improve coaching", "desired_outcomes": ["Give feedback"]},
		)

		self.assertEqual(response["id"], "revision-002")
		require_access.assert_called_once()
		call_pai.assert_called_once_with(
			"POST",
			"/api/v1/course-authoring/requests/pai-request-001/revisions",
			payload={
				"schema_version": "v1",
				"data": {"training_goal": "Improve coaching", "desired_outcomes": ["Give feedback"]},
			},
			idempotency_key=ANY,
		)

	@patch("pai_frappe.api.frappe")
	@patch("pai_frappe.api.get_source_hash", return_value="source-hash")
	@patch("pai_frappe.api.get_generated_course")
	@patch("pai_frappe.api._get_course_authoring_result")
	@patch("pai_frappe.api._get_request")
	@patch("pai_frappe.api._require_authoring_access")
	def test_materialize_endpoint_is_idempotent_for_an_imported_result(
		self,
		require_access,
		get_request,
		get_result,
		get_generated,
		get_hash,
		frappe_mock,
	):
		get_request.return_value = SimpleNamespace(name="PAI-REQUEST-001")
		get_result.return_value = _result()
		get_generated.return_value = _result()["generated_course"]
		frappe_mock.db.exists.return_value = "PAI-IMPORT-001"
		frappe_mock.get_doc.return_value = SimpleNamespace(
			name="PAI-IMPORT-001",
			pai_request="PAI-REQUEST-001",
			status="Imported",
			lms_course="LMS-COURSE-001",
		)

		response = materialize_course_authoring_result.__wrapped__("PAI-REQUEST-001", "result-001")

		self.assertTrue(response["already_imported"])
		self.assertEqual(response["lms_course"], "LMS-COURSE-001")
