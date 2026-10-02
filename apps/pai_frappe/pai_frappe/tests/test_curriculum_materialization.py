from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from pai_frappe.curriculum_materialization import (
	CurriculumMaterializationError,
	adapt_curriculum_plan,
	create_lms_draft,
)
from pai_frappe.api import materialize_curriculum_plan

FrappeValidationError = frappe.ValidationError


def _throw(message, exception_class):
	raise exception_class(message)


def _plan(status="CONFIRMED"):
	return {
		"plan_ref": "curriculum-plan:confirmed-001",
		"version": 3,
		"status": status,
		"course_title": "Coaching fundamentals",
		"course_description": "A structured coaching curriculum.",
		"modules": [
			{
				"id": "module-2",
				"title": "Applied coaching",
				"order": 2,
				"objective_refs": ["objective-2"],
				"lessons": [
					{
						"id": "lesson-2b",
						"title": "Practice conversations",
						"order": 2,
						"objective_refs": ["objective-2"],
						"estimated_minutes": 45,
						"lesson_type": "PRACTICE",
					},
					{
						"id": "lesson-2a",
						"title": "Feedback models",
						"order": 1,
						"objective_refs": ["objective-2"],
						"estimated_minutes": 30,
						"lesson_type": "CONCEPT",
					},
				],
			},
			{
				"id": "module-1",
				"title": "Foundations",
				"order": 1,
				"objective_refs": ["objective-1"],
				"lessons": [
					{
						"id": "lesson-1",
						"title": "Listening basics",
						"order": 1,
						"objective_refs": ["objective-1"],
						"estimated_minutes": 20,
						"lesson_type": "FOUNDATION",
					},
				],
			},
		],
	}


class FakeDoc:
	_counter = 0

	def __init__(self, values):
		self.__dict__.update(values)
		self.name = values.get("name")
		self.chapters = []
		self.lessons = []

	def append(self, fieldname, values):
		getattr(self, fieldname).append(SimpleNamespace(**values))

	def insert(self, **kwargs):
		FakeDoc._counter += 1
		self.name = self.name or f"{self.doctype.replace(' ', '-')}-{FakeDoc._counter}"
		return self

	def save(self, **kwargs):
		return self

	def reload(self):
		return self


class TestCurriculumMaterializationAdapter(TestCase):
	def test_confirmed_plan_maps_course_modules_lessons_and_order(self):
		spec = adapt_curriculum_plan(_plan())

		self.assertEqual(spec.plan_ref, "curriculum-plan:confirmed-001")
		self.assertEqual(spec.version, 3)
		self.assertEqual(spec.title, "Coaching fundamentals")
		self.assertEqual([chapter.order for chapter in spec.chapters], [1, 2])
		self.assertEqual([chapter.title for chapter in spec.chapters], ["Foundations", "Applied coaching"])
		self.assertEqual(
			[lesson.title for lesson in spec.chapters[1].lessons],
			["Feedback models", "Practice conversations"],
		)

	def test_non_confirmed_plan_is_rejected(self):
		with self.assertRaises(CurriculumMaterializationError):
			adapt_curriculum_plan(_plan(status="READY_FOR_REVIEW"))

	def test_adapter_does_not_copy_metadata_into_lesson_content(self):
		spec = adapt_curriculum_plan(_plan())

		self.assertEqual(spec.description, "A structured coaching curriculum.")
		self.assertTrue(all(lesson.body == "" for chapter in spec.chapters for lesson in chapter.lessons))
		self.assertFalse(hasattr(spec.chapters[0].lessons[0], "objective_refs"))

	@patch("pai_frappe.curriculum_materialization.frappe.get_doc")
	def test_create_lms_draft_creates_unpublished_tree_without_model_call(self, get_doc):
		get_doc.side_effect = lambda values: FakeDoc(values)
		spec = adapt_curriculum_plan(_plan())

		result = create_lms_draft(spec, "instructor@example.com")

		course_values = get_doc.call_args_list[0].args[0]
		self.assertEqual(course_values["doctype"], "LMS Course")
		self.assertEqual(course_values["published"], 0)
		self.assertEqual(course_values["title"], "Coaching fundamentals")
		self.assertEqual(result["plan_ref"], spec.plan_ref)
		self.assertEqual(len(result["chapters"]), 2)
		self.assertEqual(len(result["lessons"]), 3)
		lesson_calls = [call.args[0] for call in get_doc.call_args_list if call.args[0].get("doctype") == "Course Lesson"]
		self.assertEqual([call["body"] for call in lesson_calls], ["", "", ""])


class TestCurriculumMaterializationAPI(TestCase):
	def _import_doc(self, status="Pending"):
		doc = MagicMock(
			name="PAI-IMPORT-001",
			pai_request="PAI-REQUEST-001",
			source_plan_ref="curriculum-plan:confirmed-001",
			source_plan_version=3,
			status=status,
			lms_course="LMS-COURSE-001" if status == "Imported" else None,
		)
		def db_set(fieldname, value, **kwargs):
			setattr(doc, fieldname, value)
		doc.db_set = MagicMock(side_effect=db_set)
		doc.insert.return_value = doc
		return doc

	@patch("pai_frappe.api.create_lms_draft")
	@patch("pai_frappe.api._resolve_course_instructor", return_value="instructor@example.com")
	@patch("pai_frappe.api.get_plan_source_hash", return_value="plan-hash")
	@patch("pai_frappe.api._get_request")
	@patch("pai_frappe.api._require_authoring_access")
	@patch("pai_frappe.api._call_pai")
	def test_confirmed_plan_materializes_through_server_side_bridge(
		self, call_pai, require_access, get_request, get_hash, resolve_instructor, create_draft
	):
		request_doc = SimpleNamespace(name="PAI-REQUEST-001", pai_request_id="pai-request-001")
		import_doc = self._import_doc()
		plan = _plan()
		plan["authoring_request_ref"] = "pai-request-001"
		call_pai.return_value = {"data": plan}
		get_request.return_value = request_doc
		create_draft.return_value = {
			"plan_ref": plan["plan_ref"],
			"version": plan["version"],
			"course": {"name": "LMS-COURSE-001", "published": 0},
			"chapters": [{"name": "CHP-001", "title": "Foundations", "order": 1}],
			"lessons": [{"name": "LES-001", "title": "Listening basics", "order": 1}],
		}

		with patch("pai_frappe.api.frappe") as frappe_mock, patch("pai_frappe.api.now_datetime", return_value=None):
			frappe_mock.ValidationError = FrappeValidationError
			frappe_mock.DuplicateEntryError = frappe.DuplicateEntryError
			frappe_mock.db.exists.return_value = None
			frappe_mock.get_doc.return_value = import_doc
			frappe_mock.generate_hash.return_value = "savepoint"
			response = materialize_curriculum_plan.__wrapped__("PAI-REQUEST-001", plan["plan_ref"])

		self.assertEqual(response["lms_course"], "LMS-COURSE-001")
		self.assertFalse(response["already_materialized"])
		self.assertEqual(response["source_plan_ref"], plan["plan_ref"])
		call_pai.assert_called_once_with(
			"GET", "/api/v1/course-authoring/curriculum-plans/curriculum-plan:confirmed-001"
		)
		create_draft.assert_called_once()
		self.assertEqual(import_doc.db_set.call_args_list[0].args[:2], ("source_hash", "plan-hash"))
		frappe_mock.db.exists.assert_called_once_with("PAI Course Import", {"source_plan_ref": plan["plan_ref"]})

	@patch("pai_frappe.api._get_lms_draft_tree", return_value={"chapters": [], "lessons": []})
	@patch("pai_frappe.api._get_request")
	@patch("pai_frappe.api._require_authoring_access")
	@patch("pai_frappe.api._call_pai")
	def test_repeated_materialization_returns_existing_linkage_without_duplicate(
		self, call_pai, require_access, get_request, get_tree
	):
		plan = _plan()
		plan["authoring_request_ref"] = "pai-request-001"
		call_pai.return_value = {"data": plan}
		get_request.return_value = SimpleNamespace(name="PAI-REQUEST-001", pai_request_id="pai-request-001")
		import_doc = self._import_doc(status="Imported")

		with patch("pai_frappe.api.frappe") as frappe_mock:
			frappe_mock.ValidationError = FrappeValidationError
			frappe_mock.db.exists.return_value = "PAI-IMPORT-001"
			frappe_mock.get_doc.return_value = import_doc
			response = materialize_curriculum_plan.__wrapped__("PAI-REQUEST-001", plan["plan_ref"])

		self.assertTrue(response["already_materialized"])
		self.assertEqual(response["lms_course"], "LMS-COURSE-001")
		get_tree.assert_called_once_with("LMS-COURSE-001")

	@patch("pai_frappe.api._require_authoring_access")
	@patch("pai_frappe.api._get_request")
	@patch("pai_frappe.api._call_pai")
	def test_non_confirmed_plan_is_rejected_before_import_record_creation(
		self, call_pai, get_request, require_access
	):
		plan = _plan(status="READY_FOR_REVIEW")
		plan["authoring_request_ref"] = "pai-request-001"
		call_pai.return_value = {"data": plan}
		get_request.return_value = SimpleNamespace(name="PAI-REQUEST-001", pai_request_id="pai-request-001")

		with patch("pai_frappe.api.frappe") as frappe_mock:
			frappe_mock.ValidationError = FrappeValidationError
			frappe_mock.throw.side_effect = _throw
			with self.assertRaises(FrappeValidationError):
				materialize_curriculum_plan.__wrapped__("PAI-REQUEST-001", plan["plan_ref"])
			frappe_mock.db.exists.assert_not_called()

	@patch("pai_frappe.api._require_authoring_access")
	@patch("pai_frappe.api._get_request")
	@patch("pai_frappe.api._call_pai")
	def test_plan_from_another_authoring_request_is_rejected(
		self, call_pai, get_request, require_access
	):
		plan = _plan()
		plan["authoring_request_ref"] = "pai-request-other"
		call_pai.return_value = {"data": plan}
		get_request.return_value = SimpleNamespace(name="PAI-REQUEST-001", pai_request_id="pai-request-001")

		with patch("pai_frappe.api.frappe") as frappe_mock:
			frappe_mock.PermissionError = frappe.PermissionError
			frappe_mock.throw.side_effect = _throw
			with self.assertRaises(frappe.PermissionError):
				materialize_curriculum_plan.__wrapped__("PAI-REQUEST-001", plan["plan_ref"])

	@patch("pai_frappe.api.create_lms_draft", side_effect=RuntimeError("mid-tree failure"))
	@patch("pai_frappe.api._resolve_course_instructor", return_value="instructor@example.com")
	@patch("pai_frappe.api._get_request")
	@patch("pai_frappe.api._require_authoring_access")
	@patch("pai_frappe.api._call_pai")
	def test_mid_tree_failure_rolls_back_savepoint_and_marks_import_failed(
		self, call_pai, require_access, get_request, resolve_instructor, create_draft
	):
		plan = _plan()
		plan["authoring_request_ref"] = "pai-request-001"
		call_pai.return_value = {"data": plan}
		get_request.return_value = SimpleNamespace(name="PAI-REQUEST-001", pai_request_id="pai-request-001")
		import_doc = self._import_doc()

		with patch("pai_frappe.api.frappe") as frappe_mock, patch("pai_frappe.api.now_datetime", return_value=None):
			frappe_mock.ValidationError = FrappeValidationError
			frappe_mock.DuplicateEntryError = frappe.DuplicateEntryError
			frappe_mock.db.exists.return_value = None
			frappe_mock.get_doc.return_value = import_doc
			frappe_mock.generate_hash.return_value = "savepoint"
			with self.assertRaises(FrappeValidationError):
				materialize_curriculum_plan.__wrapped__("PAI-REQUEST-001", plan["plan_ref"])

			frappe_mock.db.rollback.assert_called_once()
			self.assertTrue(frappe_mock.db.rollback.call_args.kwargs["save_point"].startswith("pai_curriculum_materialization_"))
		self.assertIn(("status", "Failed"), [call.args[:2] for call in import_doc.db_set.call_args_list])
