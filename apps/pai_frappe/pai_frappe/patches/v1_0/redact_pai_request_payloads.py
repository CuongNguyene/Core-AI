"""Remove copied authoring prompts from existing local PAI audit records."""

import json

import frappe


def execute():
	for record in frappe.get_all(
		"PAI Request",
		fields=["name", "title", "request_type", "request_payload"],
		limit_page_length=0,
	):
		payload = _safe_summary(record)
		frappe.db.set_value(
			"PAI Request",
			record.name,
			"request_payload",
			json.dumps(payload, ensure_ascii=False),
			update_modified=False,
		)


def _safe_summary(record):
	return {
		"schema_version": "v1",
		"title": record.title,
		"request_type": record.request_type,
		"legacy_payload_redacted": bool(record.request_payload),
	}
