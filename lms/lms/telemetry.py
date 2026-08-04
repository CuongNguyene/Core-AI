import frappe
import frappe.utils.telemetry

POSTHOG_PROJECT_FIELD = "posthog_project_id"
POSTHOG_HOST_FIELD = "posthog_host"


@frappe.whitelist(allow_guest=True)
def get_posthog_settings():
	"""Backward-compatible wrapper for older LMS frontend callers.

	Frappe v16 replaced PostHog with Pulse. Prefer the core endpoint
	``frappe.utils.telemetry.pulse.client.boot_config`` for new code.
	"""
	from frappe.utils.telemetry.pulse.client import boot_config, is_enabled

	if not is_enabled():
		return {
			"posthog_project_id": None,
			"posthog_host": None,
			"enable_telemetry": False,
			"telemetry_site_age": frappe.utils.telemetry.site_age(),
		}

	cfg = boot_config()
	return {
		"posthog_project_id": cfg.get("key"),
		"posthog_host": cfg.get("host"),
		"enable_telemetry": bool(cfg.get("enabled")),
		"telemetry_site_age": cfg.get("site_age"),
		"pulse": cfg,
	}
