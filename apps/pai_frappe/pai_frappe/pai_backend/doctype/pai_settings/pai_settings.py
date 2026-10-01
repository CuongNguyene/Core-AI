import base64
from binascii import Error as BinasciiError
from urllib.parse import urlsplit
from uuid import UUID

import frappe
from frappe.model.document import Document


_DEVELOPMENT_HTTP_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def _developer_mode_enabled():
	try:
		return bool(frappe.conf.get("developer_mode"))
	except RuntimeError:
		return False


class PAISettings(Document):
	"""Reject incomplete or malformed settings before the integration is enabled."""

	def validate(self):
		# Settings are deliberately configurable in stages while integration is
		# disabled. Once an individual value is present, validate it immediately:
		# the pre-enable health endpoint uses the URL and must not become a way to
		# call an arbitrary malformed/credential-bearing URL.
		if self.service_url:
			self._validate_service_url()
		if self.organization_id:
			self._validate_organization_id()
		if self.get_password("actor_private_key", raise_exception=False):
			self._validate_private_key()
		if self.timeout_seconds is not None:
			self._validate_timeout()

		if not self.enabled:
			return

		missing = [
			fieldname
			for fieldname in ("service_url", "organization_id", "actor_key_id")
			if not getattr(self, fieldname, None)
		]
		if not self.get_password("integration_api_key", raise_exception=False):
			missing.append("integration_api_key")
		if not self.get_password("actor_private_key", raise_exception=False):
			missing.append("actor_private_key")
		if missing:
			frappe.throw(
				"PAI integration cannot be enabled until these settings are completed: "
				+ ", ".join(missing)
			)


	def _validate_service_url(self):
		parsed = urlsplit(self.service_url)
		is_local_http = (
			parsed.scheme == "http"
			and getattr(self, "allow_insecure_local_url", False)
			and _developer_mode_enabled()
			and parsed.hostname in _DEVELOPMENT_HTTP_HOSTS
		)
		if (
			parsed.scheme != "https"
			and not is_local_http
			or not parsed.netloc
			or parsed.username
			or parsed.password
			or parsed.query
			or parsed.fragment
		):
			frappe.throw(
				"PAI Service URL must be an HTTPS base URL without credentials or query values. "
				"Developer mode may use HTTP only for localhost, a loopback address, "
				"or Docker Desktop's host gateway."
			)

	def _validate_organization_id(self):
		try:
			UUID(self.organization_id)
		except (TypeError, ValueError):
			frappe.throw("PAI Organization UUID is invalid.")

	def _validate_private_key(self):
		try:
			encoded = self.get_password("actor_private_key", raise_exception=False)
			key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
		except (BinasciiError, TypeError, ValueError):
			frappe.throw("PAI Actor Signing Private Key must be base64-encoded Ed25519 key material.")
		if len(key) != 32:
			frappe.throw("PAI Actor Signing Private Key must contain exactly 32 bytes.")

	def _validate_timeout(self):
		try:
			timeout_seconds = int(self.timeout_seconds or 30)
		except (TypeError, ValueError):
			frappe.throw("PAI timeout must be between 1 and 120 seconds.")
			return
		if not 1 <= timeout_seconds <= 120:
			frappe.throw("PAI timeout must be between 1 and 120 seconds.")
