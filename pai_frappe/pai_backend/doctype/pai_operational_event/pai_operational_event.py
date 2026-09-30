from frappe.model.document import Document


class PAIOperationalEvent(Document):
	"""Safe local projection of PAI operational/audit signals.

	The schema intentionally provides only identifiers and redacted summaries. Raw
	request bodies, evidence, prompts, tokens and secret values have no field here.
	"""
