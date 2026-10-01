from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lms.lms.learning_assignment import (
	SYNCABLE_ASSIGNMENT_STATUSES,
	_send_batch_course_sync_notifications,
	cancel_learning_assignment,
	create_learning_assignment,
	preview_batch_course_sync,
	resolve_learning_assignment_status,
)


def assignment(name="LASSIGN-001", status="Assigned"):
	return SimpleNamespace(
		name=name,
		learner="learner@example.com",
		target_type="Course",
		course="COURSE-001",
		batch=None,
		status=status,
		due_at=None,
		mandatory=1,
		items=[SimpleNamespace(course="COURSE-001", lms_enrollment="ENR-001", source_batch=None)],
		save=lambda **kwargs: None,
	)


class TestLearningAssignmentService(TestCase):
	@patch("lms.lms.learning_assignment._validate_course")
	@patch("lms.lms.learning_assignment.frappe")
	@patch("lms.lms.learning_assignment.assert_can_manage_learning_assignment_target")
	def test_batch_sync_preview_ignores_completed_assignments(
		self, assert_access, frappe_mock, validate_course
	):
		frappe_mock.db.exists.return_value = True
		frappe_mock.get_all.side_effect = [[], []]
		preview_batch_course_sync("BATCH-UAT", "COURSE-UAT")

		assignment_filters = frappe_mock.get_all.call_args_list[1].args[1]
		self.assertEqual(
			assignment_filters["status"], ["in", SYNCABLE_ASSIGNMENT_STATUSES]
		)

	@patch("lms.lms.learning_assignment.make_lms_notification_logs")
	@patch("lms.lms.learning_assignment._current_user", return_value="moderator@example.com")
	@patch("lms.lms.learning_assignment.frappe")
	@patch("lms.lms.learning_assignment._", side_effect=lambda value: value)
	def test_batch_course_sync_notifies_only_changed_learners(
		self, translate, frappe_mock, current_user, notify
	):
		frappe_mock.db.get_value.side_effect = ["Course UAT", "Batch UAT"]
		frappe_mock._dict.side_effect = lambda value: SimpleNamespace(**value)
		notified = _send_batch_course_sync_notifications(
			"BATCH-UAT", "COURSE-UAT", {"learner@example.com", "learner@example.com"}
		)

		self.assertEqual(notified, 1)
		notify.assert_called_once()
		notification, learners = notify.call_args.args
		self.assertEqual(learners, ["learner@example.com"])
		self.assertEqual(notification.document_type, "LMS Batch")
		self.assertEqual(notification.document_name, "BATCH-UAT")
		self.assertEqual(notification.link, "/courses/COURSE-UAT")
		self.assertEqual(notification.from_user, "moderator@example.com")

	@patch("lms.lms.learning_assignment.make_lms_notification_logs")
	def test_batch_course_sync_skips_notification_when_nothing_changed(self, notify):
		notified = _send_batch_course_sync_notifications("BATCH-UAT", "COURSE-UAT", [])

		self.assertEqual(notified, 0)
		notify.assert_not_called()

	@patch("lms.lms.learning_assignment.frappe.get_all")
	def test_status_is_derived_from_enrollment_progress_and_deadline(self, get_all):
		doc = assignment()
		doc.due_at = "2026-09-27 12:00:00"
		doc.progress = 0
		doc.completed_at = None
		doc.completed_late = 0
		doc.last_activity_at = None
		get_all.return_value = [
			SimpleNamespace(
				name="ENR-001",
				course="COURSE-001",
				progress=55,
				current_lesson="LESSON-001",
				modified="2026-09-26 12:00:00",
			)
		]

		state = resolve_learning_assignment_status(doc, now="2026-09-28 12:00:00")

		self.assertEqual(state["status"], "Overdue")
		self.assertEqual(state["progress"], 55)
		self.assertEqual(str(state["last_activity_at"]), "2026-09-26 12:00:00")

		get_all.return_value[0].progress = 100
		get_all.return_value[0].modified = "2026-09-28 13:00:00"
		completed = resolve_learning_assignment_status(doc, now="2026-09-28 14:00:00")

		self.assertEqual(completed["status"], "Completed")
		self.assertEqual(completed["completed_late"], 1)

	@patch("lms.lms.learning_assignment._send_learning_assignment_created_notification")
	@patch("lms.lms.learning_assignment.frappe.get_doc")
	@patch("lms.lms.learning_assignment.ensure_learning_enrollment")
	@patch("lms.lms.learning_assignment.find_active_learning_assignment", return_value=None)
	@patch("lms.lms.learning_assignment._find_idempotent_assignment", return_value=None)
	@patch("lms.lms.learning_assignment.assert_can_manage_learning_assignment_target")
	@patch("lms.lms.learning_assignment.get_target_courses", return_value=["COURSE-001"])
	@patch("lms.lms.learning_assignment._validate_learner")
	@patch("lms.lms.learning_assignment._current_user", return_value="moderator@example.com")
	@patch("lms.lms.learning_assignment.now_datetime", return_value="2026-09-28 09:00:00")
	def test_course_assignment_reuses_service_enrollment(
		self,
		now_datetime,
		current_user,
		validate_learner,
		get_target_courses,
		assert_access,
		find_by_key,
		find_active,
		ensure_enrollment,
		get_doc,
		notify_learner,
	):
		ensure_enrollment.return_value = (SimpleNamespace(name="ENR-001"), False)
		created = assignment()
		created.insert = lambda **kwargs: None
		get_doc.return_value = created

		result = create_learning_assignment(
			"learner@example.com",
			"Course",
			"COURSE-001",
			mandatory=1,
			idempotency_key="request-001",
		)

		self.assertEqual(result["name"], "LASSIGN-001")
		self.assertFalse(result["already_assigned"])
		ensure_enrollment.assert_called_once_with("learner@example.com", "COURSE-001")
		get_doc.assert_called_once()
		payload = get_doc.call_args.args[0]
		self.assertEqual(payload["items"][0]["lms_enrollment"], "ENR-001")
		self.assertEqual(payload["idempotency_key"], "request-001")
		notify_learner.assert_called_once_with(created)

	@patch("lms.lms.learning_assignment._send_learning_assignment_created_notification")
	@patch("lms.lms.learning_assignment.frappe.get_doc")
	@patch("lms.lms.learning_assignment.ensure_learning_enrollment")
	@patch("lms.lms.learning_assignment.ensure_learning_batch_enrollment")
	@patch("lms.lms.learning_assignment.find_active_learning_assignment", return_value=None)
	@patch("lms.lms.learning_assignment._find_idempotent_assignment", return_value=None)
	@patch("lms.lms.learning_assignment.assert_can_manage_learning_assignment_target")
	@patch("lms.lms.learning_assignment.get_target_courses", return_value=["COURSE-001", "COURSE-002"])
	@patch("lms.lms.learning_assignment._validate_learner")
	@patch("lms.lms.learning_assignment._current_user", return_value="moderator@example.com")
	@patch("lms.lms.learning_assignment.now_datetime", return_value="2026-09-28 09:00:00")
	def test_batch_assignment_ensures_membership_and_each_course_enrollment(
		self,
		now_datetime,
		current_user,
		validate_learner,
		get_target_courses,
		assert_access,
		find_by_key,
		find_active,
		ensure_batch_enrollment,
		ensure_enrollment,
		get_doc,
		notify_learner,
	):
		ensure_enrollment.side_effect = [
			(SimpleNamespace(name="ENR-001"), False),
			(SimpleNamespace(name="ENR-002"), True),
		]
		created = assignment()
		created.target_type = "Batch"
		created.course = None
		created.batch = "BATCH-001"
		created.items = [
			SimpleNamespace(course="COURSE-001", lms_enrollment="ENR-001", source_batch="BATCH-001"),
			SimpleNamespace(course="COURSE-002", lms_enrollment="ENR-002", source_batch="BATCH-001"),
		]
		created.insert = lambda **kwargs: None
		get_doc.return_value = created

		result = create_learning_assignment("learner@example.com", "Batch", "BATCH-001")

		self.assertFalse(result["already_assigned"])
		ensure_batch_enrollment.assert_called_once_with("learner@example.com", "BATCH-001")
		self.assertEqual(
			[call.args for call in ensure_enrollment.call_args_list],
			[("learner@example.com", "COURSE-001"), ("learner@example.com", "COURSE-002")],
		)
		payload = get_doc.call_args.args[0]
		self.assertEqual([item["source_batch"] for item in payload["items"]], ["BATCH-001", "BATCH-001"])
		notify_learner.assert_called_once_with(created)

	@patch("lms.lms.learning_assignment.frappe.get_doc")
	@patch("lms.lms.learning_assignment.find_active_learning_assignment", return_value="LASSIGN-001")
	@patch("lms.lms.learning_assignment._find_idempotent_assignment", return_value=None)
	@patch("lms.lms.learning_assignment.assert_can_manage_learning_assignment_target")
	@patch("lms.lms.learning_assignment.get_target_courses", return_value=["COURSE-001"])
	@patch("lms.lms.learning_assignment._validate_learner")
	@patch("lms.lms.learning_assignment._current_user", return_value="moderator@example.com")
	def test_duplicate_active_assignment_returns_existing(
		self,
		current_user,
		validate_learner,
		get_target_courses,
		assert_access,
		find_by_key,
		find_active,
		get_doc,
	):
		get_doc.return_value = assignment()

		result = create_learning_assignment("learner@example.com", "Course", "COURSE-001")

		self.assertTrue(result["already_assigned"])
		get_doc.assert_called_once_with("LMS Learning Assignment", "LASSIGN-001")

	@patch("lms.lms.learning_assignment.now_datetime", return_value="2026-09-28 09:00:00")
	@patch("lms.lms.learning_assignment.assert_can_manage_learning_assignment_target")
	@patch("lms.lms.learning_assignment.frappe.get_doc")
	@patch("lms.lms.learning_assignment._current_user", return_value="moderator@example.com")
	def test_cancel_keeps_assignment_record_and_sets_audit_fields(
		self, current_user, get_doc, assert_access, now_datetime
	):
		doc = assignment()
		get_doc.return_value = doc

		result = cancel_learning_assignment("LASSIGN-001", "Assigned to the wrong learner")

		self.assertEqual(result["status"], "Cancelled")
		self.assertEqual(doc.cancelled_by, "moderator@example.com")
		self.assertEqual(doc.cancelled_at, "2026-09-28 09:00:00")
		self.assertEqual(doc.cancel_reason, "Assigned to the wrong learner")
