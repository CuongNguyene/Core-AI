"""Server-side client for the isolated PAI FastAPI service."""

import base64
import json
from binascii import Error as BinasciiError
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import frappe
import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class PAIClientError(frappe.ValidationError):
	pass


class PAIClient:
	"""Calls PAI without ever exposing PAI credentials to the browser."""

	def __init__(self, require_enabled=True):
		settings = frappe.get_single("PAI Settings")
		if require_enabled and not settings.enabled:
			raise PAIClientError("PAI integration is disabled.")
		integration_api_key = settings.get_password("integration_api_key", raise_exception=False)
		if not settings.service_url or (require_enabled and not integration_api_key):
			raise PAIClientError("PAI Settings is incomplete.")
		self.settings = settings
		self.integration_api_key = integration_api_key

	def request(self, method, path, *, user, payload=None, idempotency_key=None):
		headers = self._headers(user)
		self._remember_correlation_id(headers.get("X-Request-ID") or str(uuid4()))
		headers["X-Request-ID"] = self.last_request_id
		if idempotency_key:
			headers["Idempotency-Key"] = idempotency_key
		try:
			response = requests.request(
				method,
				f"{self.settings.service_url.rstrip('/')}{path}",
				headers=headers,
				json=payload,
				timeout=self.settings.timeout_seconds or 30,
				allow_redirects=False,
			)
		except requests.RequestException as exc:
			raise PAIClientError("PAI service is unavailable.") from exc
		if not response.ok:
			# Do not surface an untrusted upstream body through a whitelisted
			# endpoint.  PAI logs and the request ID are the correlation path for
			# detailed diagnosis; LMS users get a bounded, safe error instead.
			raise PAIClientError("PAI service rejected the request.")

		try:
			response_payload = response.json()
		except (TypeError, ValueError) as exc:
			raise PAIClientError("PAI service returned an invalid response.") from exc

		if (
			not isinstance(response_payload, dict)
			or response_payload.get("schema_version") != "v1"
			or "data" not in response_payload
		):
			raise PAIClientError("PAI service returned an invalid response.")
		return response_payload

	def check_readiness(self):
		"""Check the private PAI readiness endpoint without exposing service details."""
		if not self.settings.service_url:
			raise PAIClientError("PAI Settings is incomplete.")
		self._remember_correlation_id(str(uuid4()))
		try:
			response = requests.get(
				f"{self.settings.service_url.rstrip('/')}/health/ready",
				headers={"X-Request-ID": self.last_request_id},
				timeout=self.settings.timeout_seconds or 30,
				allow_redirects=False,
			)
		except requests.RequestException as exc:
			raise PAIClientError("PAI service is unavailable.") from exc
		if not response.ok:
			raise PAIClientError("PAI service is not ready.")
		return True

	def _remember_correlation_id(self, request_id):
		"""Retain a trace ID when running in Frappe, without coupling unit tests to a request."""
		self.last_request_id = request_id
		try:
			frappe.flags.pai_last_correlation_id = request_id
		except RuntimeError:
			# `PAIClient` is also exercised outside a Frappe HTTP/job context.
			pass

	def _headers(self, user):
		identity = frappe.db.get_value(
			"PAI User Identity", {"user": user, "enabled": 1}, ["pai_actor_id"], as_dict=True
		)
		if not identity:
			raise PAIClientError("PAI identity is not configured for this user.")
		try:
			actor_id = UUID(identity.pai_actor_id)
			organization_id = UUID(self.settings.organization_id)
			encoded_key = self.settings.get_password("actor_private_key", raise_exception=False)
			private_key = Ed25519PrivateKey.from_private_bytes(
				base64.urlsafe_b64decode(encoded_key + "=" * (-len(encoded_key) % 4))
			)
		except (BinasciiError, TypeError, ValueError) as exc:
			raise PAIClientError("PAI signing configuration is invalid.") from exc
		now = datetime.now(UTC)
		payload = {
			"actor_reference": str(actor_id),
			"expires_at": (now + timedelta(seconds=60)).isoformat().replace("+00:00", "Z"),
			"issued_at": now.isoformat().replace("+00:00", "Z"),
			"issuer": "lms",
			"nonce": str(uuid4()),
			"organization_reference": str(organization_id),
			"version": "v1",
		}
		canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
		encoded = base64.urlsafe_b64encode(canonical).rstrip(b"=").decode()
		signature = base64.urlsafe_b64encode(private_key.sign(canonical)).rstrip(b"=").decode()
		return {
			"Authorization": f"Bearer {self.integration_api_key}",
			"Content-Type": "application/json",
			"X-PAI-Actor-Context": encoded,
			"X-PAI-Actor-Context-Key-Id": self.settings.actor_key_id,
			"X-PAI-Actor-Context-Signature": f"ed25519:{signature}",
			"X-Request-ID": str(uuid4()),
		}
