from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from pai_frappe.api import (
	_get_missing_pai_settings,
	_get_request,
	_get_safe_request_summary,
	_normalize_idempotency_key,
	_parse_brief_revision,
	create_course_authoring_request,
)
from pai_frappe.client import PAIClient, PAIClientError
from pai_frappe.pai_backend.doctype.pai_request.pai_request import PAIRequest
from pai_frappe.pai_backend.doctype.pai_user_identity.pai_user_identity import PAIUserIdentity


class TestPAIClient(TestCase):
	@patch("pai_frappe.client.requests.request")
	def test_request_does_not_follow_redirects(self, request):
		client = object.__new__(PAIClient)
		client.settings = SimpleNamespace(service_url="https://pai.example.test", timeout_seconds=30)
		client._headers = lambda user: {"Authorization": "Bearer test"}
		response = SimpleNamespace(ok=True, json=lambda: {"schema_version": "v1", "data": {}})
		request.return_value = response

		client.request("GET", "/api/v1/health", user="test@example.com")

		self.assertFalse(request.call_args.kwargs["allow_redirects"])
		self.assertTrue(client.last_request_id)

	@patch("pai_frappe.client.requests.request")
	def test_request_rejects_invalid_success_response(self, request):
		client = object.__new__(PAIClient)
		client.settings = SimpleNamespace(service_url="https://pai.example.test", timeout_seconds=30)
		client._headers = lambda user: {"Authorization": "Bearer test"}
		request.return_value = SimpleNamespace(ok=True, json=lambda: {"data": {}})

		with self.assertRaisesRegex(PAIClientError, "invalid response"):
			client.request("GET", "/api/v1/health", user="test@example.com")

	@patch("pai_frappe.client.requests.request")
	def test_request_does_not_expose_untrusted_error_body(self, request):
		client = object.__new__(PAIClient)
		client.settings = SimpleNamespace(service_url="https://pai.example.test", timeout_seconds=30)
		client._headers = lambda user: {"Authorization": "Bearer test"}
		request.return_value = SimpleNamespace(
			ok=False,
			json=lambda: {"error": {"message": "upstream secret should not leak"}},
		)

		with self.assertRaisesRegex(PAIClientError, "PAI service rejected the request") as error:
			client.request("GET", "/api/v1/health", user="test@example.com")

		self.assertNotIn("upstream secret", str(error.exception))

	@patch("pai_frappe.client.requests.get")
	def test_readiness_check_does_not_follow_redirects(self, request):
		client = object.__new__(PAIClient)
		client.settings = SimpleNamespace(service_url="https://pai.example.test", timeout_seconds=30)
		request.return_value = SimpleNamespace(ok=True)

		self.assertTrue(client.check_readiness())
		self.assertFalse(request.call_args.kwargs["allow_redirects"])
		self.assertEqual(request.call_args.kwargs["headers"]["X-Request-ID"], client.last_request_id)

	@patch("pai_frappe.pai_backend.doctype.pai_settings.pai_settings.frappe.throw")
	def test_settings_rejects_non_https_service_url(self, throw):
		from pai_frappe.pai_backend.doctype.pai_settings.pai_settings import PAISettings

		PAISettings._validate_service_url(SimpleNamespace(service_url="http://pai.example.test"))

		throw.assert_called_once_with(
			"PAI Service URL must be an HTTPS base URL without credentials or query values. "
			"Developer mode may use HTTP only for localhost, a loopback address, "
			"or Docker Desktop's host gateway."
		)

	def test_settings_accepts_loopback_http_only_in_developer_mode(self):
		from pai_frappe.pai_backend.doctype.pai_settings.pai_settings import PAISettings

		settings = SimpleNamespace(
			service_url="http://127.0.0.1:18000",
			allow_insecure_local_url=True,
		)
		with patch(
			"pai_frappe.pai_backend.doctype.pai_settings.pai_settings._developer_mode_enabled",
			return_value=True,
		), patch("pai_frappe.pai_backend.doctype.pai_settings.pai_settings.frappe.throw") as throw:
			PAISettings._validate_service_url(settings)

		throw.assert_not_called()

	def test_settings_accepts_docker_host_http_only_in_developer_mode(self):
		from pai_frappe.pai_backend.doctype.pai_settings.pai_settings import PAISettings

		settings = SimpleNamespace(
			service_url="http://host.docker.internal:18000",
			allow_insecure_local_url=True,
		)
		with patch(
			"pai_frappe.pai_backend.doctype.pai_settings.pai_settings._developer_mode_enabled",
			return_value=True,
		), patch("pai_frappe.pai_backend.doctype.pai_settings.pai_settings.frappe.throw") as throw:
			PAISettings._validate_service_url(settings)

		throw.assert_not_called()

	@patch("pai_frappe.pai_backend.doctype.pai_settings.pai_settings.frappe.throw")
	def test_disabled_settings_still_reject_an_invalid_service_url(self, throw):
		from pai_frappe.pai_backend.doctype.pai_settings.pai_settings import PAISettings

		settings = SimpleNamespace(
			enabled=False,
			service_url="http://pai.example.test",
			allow_insecure_local_url=False,
			organization_id="",
			timeout_seconds=30,
			get_password=lambda fieldname, **kwargs: "",
		)
		settings._validate_service_url = lambda: PAISettings._validate_service_url(settings)
		settings._validate_organization_id = lambda: PAISettings._validate_organization_id(settings)
		settings._validate_private_key = lambda: PAISettings._validate_private_key(settings)
		settings._validate_timeout = lambda: PAISettings._validate_timeout(settings)

		PAISettings.validate(settings)

		throw.assert_called_once_with(
			"PAI Service URL must be an HTTPS base URL without credentials or query values. "
			"Developer mode may use HTTP only for localhost, a loopback address, "
			"or Docker Desktop's host gateway."
		)

	@patch("pai_frappe.pai_backend.doctype.pai_settings.pai_settings.frappe.throw")
	def test_settings_rejects_non_numeric_timeout_without_a_server_error(self, throw):
		from pai_frappe.pai_backend.doctype.pai_settings.pai_settings import PAISettings

		PAISettings._validate_timeout(SimpleNamespace(timeout_seconds="not-a-number"))

		throw.assert_called_once_with("PAI timeout must be between 1 and 120 seconds.")

	@patch("pai_frappe.pai_backend.doctype.pai_user_identity.pai_user_identity.frappe.throw")
	def test_identity_rejects_invalid_actor_uuid(self, throw):
		PAIUserIdentity.validate(SimpleNamespace(pai_actor_id="not-a-uuid"))

		throw.assert_called_once_with("PAI Actor UUID is invalid.")

	def test_readiness_requires_every_signing_setting(self):
		settings = SimpleNamespace(
			service_url="https://pai.example.test",
			organization_id="",
			actor_key_id="",
			get_password=lambda fieldname, **kwargs: "key"
			if fieldname == "integration_api_key"
			else "",
		)
		self.assertEqual(
			_get_missing_pai_settings(settings),
			[
				"PAI Organization UUID",
				"Actor Signing Key ID",
				"Actor Signing Private Key",
			],
		)

	def test_safe_request_summary_excludes_authoring_prompt_and_notes(self):
		data = {
			"title": "Secure authoring",
			"learner_refs": ["learner-1"],
			"learning_need_refs": ["need-1"],
			"objective_refs": ["objective-1"],
			"training_brief": {
				"goal": "Sensitive business objective",
				"language": "vi",
				"notes": "Internal strategy details",
				"desired_outcomes": ["Outcome"],
			},
		}

		summary = _get_safe_request_summary(data)

		self.assertEqual(summary["title"], "Secure authoring")
		self.assertEqual(summary["language"], "vi")
		self.assertEqual(summary["learner_reference_count"], 1)
		self.assertEqual(summary["desired_outcome_count"], 1)
		self.assertTrue(summary["has_author_notes"])
		self.assertNotIn("goal", summary)
		self.assertNotIn("Sensitive business objective", str(summary))
		self.assertNotIn("Internal strategy details", str(summary))

	def test_authoring_request_retry_key_is_bounded_and_opaque(self):
		self.assertEqual(
			_normalize_idempotency_key("f9b0b211-4da6-4e89-849b-a3d566c9ae67"),
			"f9b0b211-4da6-4e89-849b-a3d566c9ae67",
		)

	@patch("pai_frappe.api.frappe.throw")
	def test_authoring_request_rejects_invalid_retry_key(self, throw):
		_normalize_idempotency_key("short")

		throw.assert_called_once_with(
			"A valid authoring request retry key is required.", frappe.ValidationError
		)

	@patch("pai_frappe.api._get_last_correlation_id", return_value="correlation-001")
	@patch("pai_frappe.api._call_pai")
	@patch("pai_frappe.api._get_or_create_authoring_request")
	@patch("pai_frappe.api._normalize_idempotency_key", return_value="retry-key-000000")
	@patch("pai_frappe.api._parse_payload")
	@patch("pai_frappe.api._require_authoring_access")
	def test_create_authoring_request_reuses_the_same_retry_key_on_pai_call(
		self,
		require_access,
		parse_payload,
		normalize_key,
		get_or_create,
		call_pai,
		get_correlation,
	):
		data = {"title": "Secure course", "training_brief": {"goal": "Learn safely"}}
		parse_payload.return_value = data
		doc = MagicMock(name="PAI-REQUEST-001", pai_request_id="")
		doc.name = "PAI-REQUEST-001"
		doc.pai_request_id = ""
		get_or_create.return_value = doc
		call_pai.return_value = {"data": {"request_id": "pai-request-001", "status": "DRAFT"}}

		response = create_course_authoring_request.__wrapped__(data, "retry-key-000000")

		self.assertEqual(response["pai_request_id"], "pai-request-001")
		call_pai.assert_called_once_with(
			"POST",
			"/api/v1/course-authoring/requests",
			payload={"schema_version": "v1", "data": data},
			idempotency_key="frappe:retry-key-000000",
		)
		doc.db_set.assert_any_call("pai_request_id", "pai-request-001", update_modified=False)
		doc.db_set.assert_any_call("status", "DRAFT", update_modified=False)
		doc.db_set.assert_any_call("last_correlation_id", "correlation-001", update_modified=False)
		require_access.assert_called_once()
		normalize_key.assert_called_once_with("retry-key-000000")

	@patch("pai_frappe.pai_backend.doctype.pai_request.pai_request.frappe.throw")
	def test_completed_authoring_request_requires_remote_reference(self, throw):
		PAIRequest.validate(
			SimpleNamespace(request_type="Course Authoring", status="DRAFT", pai_request_id="")
		)

		throw.assert_called_once_with(
			"A completed PAI authoring request must reference PAI.", frappe.ValidationError
		)

	def test_brief_revision_accepts_only_supported_bounded_fields(self):
		changes = _parse_brief_revision(
			{
				"training_goal": " Improve team coaching ",
				"desired_outcomes": ["Give feedback"],
				"prerequisites": [],
			}
		)

		self.assertEqual(changes["training_goal"], "Improve team coaching")
		self.assertEqual(changes["desired_outcomes"], ["Give feedback"])

	@patch("pai_frappe.api.frappe.throw")
	def test_brief_revision_rejects_unknown_fields(self, throw):
		_parse_brief_revision({"unsafe": "value"})

		throw.assert_called_with("Invalid PAI brief revision.", frappe.ValidationError)


	@patch("pai_frappe.api._is_admin", return_value=False)
	@patch("pai_frappe.api.frappe.throw")
	@patch("pai_frappe.api.frappe.get_doc")
	def test_instructor_cannot_read_another_authors_request(self, get_doc, throw, is_admin):
		get_doc.return_value = SimpleNamespace(
			request_type="Course Authoring", owner="other.instructor@example.com"
		)
		with patch("pai_frappe.api.frappe.session", SimpleNamespace(user="instructor@example.com")):
			_get_request("PAI-REQUEST-0001")

		throw.assert_called_once_with("PAI request access is not permitted.", frappe.PermissionError)
