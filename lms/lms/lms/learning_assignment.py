"""Domain service for Learning Assignment.

Assignments represent mandatory learning obligations.  Enrollment remains the
single source for course access and progress, so this module only reuses or
creates the existing enrollment records.
"""

import frappe

from frappe import _
from frappe.utils import cint, date_diff, flt, format_datetime, get_datetime, getdate, now_datetime

from lms.lms.doctype.lms_notification.lms_notification import make_lms_notification_logs
from lms.lms.utils import can_create_courses, has_course_moderator_role


ACTIVE_STATUS = "Assigned"
CANCELLED_STATUS = "Cancelled"
TARGET_TYPES = {"Course", "Batch"}
LEARNING_STATUSES = {"Assigned", "In Progress", "Completed", "Overdue", "Cancelled"}
REMINDER_DAYS = {7: "D-7", 3: "D-3", 1: "D-1"}
SYNCABLE_ASSIGNMENT_STATUSES = {"Assigned", "In Progress", "Overdue"}


def _current_user():
	return frappe.session.user


def _is_system_manager(user=None):
	user = user or _current_user()
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def _validate_learner(learner):
	if not learner or not frappe.db.exists("User", learner):
		frappe.throw(_("A valid learner is required."), frappe.ValidationError)
	if not frappe.db.get_value("User", learner, "enabled"):
		frappe.throw(_("The selected learner is disabled."), frappe.ValidationError)
	if learner in {"Administrator", "Guest"} or "LMS Student" not in frappe.get_roles(learner):
		frappe.throw(_("The selected user is not an active LMS learner."), frappe.ValidationError)


def _validate_course(course):
	if not course or not frappe.db.exists("LMS Course", course):
		frappe.throw(_("A valid course is required."), frappe.ValidationError)
	if not frappe.db.get_value("LMS Course", course, "published"):
		frappe.throw(_("Only published courses can be assigned."), frappe.ValidationError)


def get_target_courses(target_type, target):
	if target_type not in TARGET_TYPES:
		frappe.throw(_("Learning Assignment target must be a Course or Batch."), frappe.ValidationError)
	if target_type == "Course":
		_validate_course(target)
		return [target]

	if not target or not frappe.db.exists("LMS Batch", target):
		frappe.throw(_("A valid batch is required."), frappe.ValidationError)
	if not frappe.db.get_value("LMS Batch", target, "published"):
		frappe.throw(_("Only published batches can be assigned."), frappe.ValidationError)
	courses = frappe.get_all("Batch Course", {"parent": target}, pluck="course", order_by="idx asc")
	if not courses:
		frappe.throw(_("A batch must contain at least one course before it can be assigned."))
	for course in courses:
		_validate_course(course)
	return courses


def can_manage_learning_assignment_target(target_type, target, user=None):
	"""Return whether a user may assign every course represented by a target."""
	user = user or _current_user()
	if _is_system_manager(user) or has_course_moderator_role(user):
		return True
	if target_type == "Course":
		return bool(can_create_courses(target, user))
	if target_type == "Batch":
		courses = frappe.get_all("Batch Course", {"parent": target}, pluck="course")
		return bool(courses) and all(can_create_courses(course, user) for course in courses)
	return False


def assert_can_manage_learning_assignment_target(target_type, target, user=None):
	if not can_manage_learning_assignment_target(target_type, target, user):
		frappe.throw(_("You are not permitted to manage this learning assignment target."), frappe.PermissionError)


def add_course_to_batch(batch, course):
	"""Add a published course to a Batch with the same scoped authorization as assignment sync."""
	if not batch or not frappe.db.exists("LMS Batch", batch):
		frappe.throw(_("A valid batch is required."), frappe.ValidationError)
	_validate_course(course)

	user = _current_user()
	if not (_is_system_manager(user) or has_course_moderator_role(user)):
		batch_courses = frappe.get_all("Batch Course", {"parent": batch}, pluck="course")
		if not all(can_create_courses(batch_course, user) for batch_course in [*batch_courses, course]):
			frappe.throw(_("You are not permitted to add this course to the batch."), frappe.PermissionError)

	if frappe.db.exists("Batch Course", {"parent": batch, "course": course}):
		frappe.throw(_("This course is already part of the batch."), frappe.ValidationError)

	batch_course = frappe.get_doc(
		{
			"doctype": "Batch Course",
			"parent": batch,
			"parenttype": "LMS Batch",
			"parentfield": "courses",
			"course": course,
		}
	)
	batch_course.insert(ignore_permissions=True)
	return {"name": batch_course.name, "batch": batch, "course": course}


def ensure_learning_enrollment(learner, course, require_published=True):
	"""Reuse the current course enrollment or create one without a new model."""
	_validate_learner(learner)
	if require_published:
		_validate_course(course)
	elif not course or not frappe.db.exists("LMS Course", course):
		frappe.throw(_("A valid course is required."), frappe.ValidationError)
	existing = frappe.db.exists("LMS Enrollment", {"member": learner, "course": course})
	if existing:
		return frappe.get_doc("LMS Enrollment", existing), False

	enrollment = frappe.get_doc(
		{
			"doctype": "LMS Enrollment",
			"member": learner,
			"course": course,
			"member_type": "Student",
			"role": "Member",
		}
	)
	enrollment.insert(ignore_permissions=True)
	return enrollment, True


def ensure_learning_batch_enrollment(learner, batch):
	"""Reuse or create current Batch membership, preserving its existing hook behavior."""
	existing = frappe.db.exists("LMS Batch Enrollment", {"member": learner, "batch": batch})
	if existing:
		return frappe.get_doc("LMS Batch Enrollment", existing), False

	batch_enrollment = frappe.get_doc(
		{
			"doctype": "LMS Batch Enrollment",
			"member": learner,
			"batch": batch,
		}
	)
	batch_enrollment.insert(ignore_permissions=True)
	return batch_enrollment, True


def _target_filters(learner, target_type, target):
	filters = {"learner": learner, "target_type": target_type, "status": ["!=", CANCELLED_STATUS]}
	filters["course" if target_type == "Course" else "batch"] = target
	return filters


def find_active_learning_assignment(learner, target_type, target):
	return frappe.db.exists("LMS Learning Assignment", _target_filters(learner, target_type, target))


def _find_idempotent_assignment(assigned_by, idempotency_key):
	if not idempotency_key:
		return None
	return frappe.db.exists(
		"LMS Learning Assignment",
		{"assigned_by": assigned_by, "idempotency_key": idempotency_key},
	)


def _assignment_response(assignment, *, already_assigned=False):
	return {
		"name": assignment.name,
		"learner": assignment.learner,
		"target_type": assignment.target_type,
		"target": assignment.course if assignment.target_type == "Course" else assignment.batch,
		"status": assignment.status,
		"items": [
			{"course": item.course, "lms_enrollment": item.lms_enrollment, "source_batch": item.source_batch}
			for item in assignment.items
		],
		"already_assigned": already_assigned,
	}


def _get_assignment_enrollments(assignment):
	enrollment_names = [item.lms_enrollment for item in assignment.items if item.lms_enrollment]
	if not enrollment_names:
		return {}
	return {
		enrollment.name: enrollment
		for enrollment in frappe.get_all(
			"LMS Enrollment",
			filters={"name": ["in", enrollment_names]},
			fields=["name", "course", "progress", "current_lesson", "modified"],
		)
	}


def resolve_learning_assignment_status(assignment, now=None):
	"""Derive assignment state exclusively from its existing course enrollments."""
	if isinstance(assignment, str):
		assignment = frappe.get_doc("LMS Learning Assignment", assignment)
	if assignment.status == CANCELLED_STATUS:
		return {
			"status": CANCELLED_STATUS,
			"progress": flt(assignment.progress),
			"completed_at": assignment.completed_at,
			"completed_late": cint(assignment.completed_late),
			"last_activity_at": assignment.last_activity_at,
		}

	now = get_datetime(now or now_datetime())
	enrollments = _get_assignment_enrollments(assignment)
	progresses = []
	activity_dates = []
	completion_dates = []
	for item in assignment.items:
		enrollment = enrollments.get(item.lms_enrollment)
		progress = flt(enrollment.progress) if enrollment else 0
		progresses.append(progress)
		if enrollment and progress > 0 and enrollment.modified:
			activity_dates.append(get_datetime(enrollment.modified))
		if enrollment and progress >= 100 and enrollment.modified:
			completion_dates.append(get_datetime(enrollment.modified))

	progress = round(sum(progresses) / len(progresses), 2) if progresses else 0
	all_completed = bool(progresses) and all(value >= 100 for value in progresses)
	last_activity_at = max(activity_dates) if activity_dates else None
	if all_completed:
		completed_at = max(completion_dates) if completion_dates else now
		due_at = get_datetime(assignment.due_at) if assignment.due_at else None
		return {
			"status": "Completed",
			"progress": progress,
			"completed_at": completed_at,
			"completed_late": cint(bool(due_at and completed_at > due_at)),
			"last_activity_at": last_activity_at,
		}

	due_at = get_datetime(assignment.due_at) if assignment.due_at else None
	status = "Overdue" if due_at and now > due_at else "In Progress" if progress > 0 else ACTIVE_STATUS
	return {
		"status": status,
		"progress": progress,
		"completed_at": None,
		"completed_late": 0,
		"last_activity_at": last_activity_at,
	}


def reconcile_learning_assignment(assignment, now=None):
	"""Persist derived values only when a state change has occurred."""
	if isinstance(assignment, str):
		assignment = frappe.get_doc("LMS Learning Assignment", assignment)
	state = resolve_learning_assignment_status(assignment, now)
	changed = False
	for field, value in state.items():
		current_value = getattr(assignment, field, None)
		if field in {"completed_at", "last_activity_at"}:
			is_changed = (get_datetime(current_value) if current_value else None) != (
				get_datetime(value) if value else None
			)
		elif field == "completed_late":
			is_changed = cint(current_value) != cint(value)
		else:
			is_changed = current_value != value
		if is_changed:
			setattr(assignment, field, value)
			changed = True
	if changed:
		assignment.save(ignore_permissions=True)
	return assignment, state


def get_learning_assignment_detail(assignment, now=None):
	"""Serialize a learner-safe view. The caller controls which learner is queried."""
	if isinstance(assignment, str):
		assignment = frappe.get_doc("LMS Learning Assignment", assignment)
	state = resolve_learning_assignment_status(assignment, now)
	enrollments = _get_assignment_enrollments(assignment)
	courses = {
		course.name: course
		for course in frappe.get_all(
			"LMS Course",
			filters={"name": ["in", [item.course for item in assignment.items]]},
			fields=["name", "title", "image", "short_introduction"],
		)
	}
	items = []
	for item in assignment.items:
		enrollment = enrollments.get(item.lms_enrollment)
		course = courses.get(item.course, {})
		lesson_number = None
		if enrollment and enrollment.current_lesson:
			from lms.lms.utils import get_lesson_index

			lesson_number = get_lesson_index(enrollment.current_lesson)
		items.append(
			{
				"course": item.course,
				"course_title": course.get("title") or item.course,
				"course_image": course.get("image"),
				"short_introduction": course.get("short_introduction"),
				"progress": flt(enrollment.progress) if enrollment else 0,
				"last_activity_at": enrollment.modified if enrollment and flt(enrollment.progress) > 0 else None,
				"continue_lesson": lesson_number,
			}
		)

	target = assignment.course if assignment.target_type == "Course" else assignment.batch
	target_title = frappe.db.get_value(
		"LMS Course" if assignment.target_type == "Course" else "LMS Batch", target, "title"
	)
	return {
		"name": assignment.name,
		"target_type": assignment.target_type,
		"target": target,
		"target_title": target_title or target,
		"mandatory": cint(assignment.mandatory),
		"due_at": assignment.due_at,
		"note": assignment.note,
		"assigned_on": assignment.assigned_on,
		"status": state["status"],
		"progress": state["progress"],
		"completed_at": state["completed_at"],
		"completed_late": state["completed_late"],
		"last_activity_at": state["last_activity_at"],
		"items": items,
	}


def get_my_learning():
	"""Return only the session learner's obligations, grouped by backend-derived state."""
	groups = {status: [] for status in LEARNING_STATUSES}
	if frappe.session.user == "Guest":
		return {"groups": groups, "summary": {status: 0 for status in LEARNING_STATUSES}}

	assignments = frappe.get_all(
		"LMS Learning Assignment",
		filters={"learner": frappe.session.user},
		pluck="name",
		order_by="due_at asc, assigned_on desc",
	)
	for name in assignments:
		detail = get_learning_assignment_detail(name)
		groups[detail["status"]].append(detail)
	return {"groups": groups, "summary": {status: len(items) for status, items in groups.items()}}


def _get_reminder_target_title(assignment):
	target = assignment.course if assignment.target_type == "Course" else assignment.batch
	return frappe.db.get_value(
		"LMS Course" if assignment.target_type == "Course" else "LMS Batch", target, "title"
	) or target


def _get_learning_assignment_target_link(assignment):
	"""Return an LMS SPA-relative route; the router owns the /lms base path."""
	if assignment.target_type == "Course":
		return f"/courses/{assignment.course}"
	return f"/batches/{assignment.batch}"


def _send_learning_assignment_created_notification(assignment):
	"""Notify the learner once when a new obligation is created.

	The caller invokes this only after the Assignment insert succeeds; repeated
	idempotent requests return the existing Assignment and do not notify again.
	"""
	title = _get_reminder_target_title(assignment)
	deadline = format_datetime(assignment.due_at) if assignment.due_at else _("No deadline")
	content = _("You have been assigned {0}. Deadline: {1}.").format(title, deadline)
	if cint(assignment.mandatory):
		content = "{} {}".format(content, _("This learning is mandatory."))
	notification = frappe._dict(
		{
			"subject": _("New learning assignment: {0}").format(title),
			"email_content": content,
			"document_type": "LMS Learning Assignment",
			"document_name": assignment.name,
			"from_user": assignment.assigned_by,
			"type": "Alert",
			"link": _get_learning_assignment_target_link(assignment),
		}
	)
	try:
		make_lms_notification_logs(notification, assignment.learner)
		return True
	except Exception:
		# Notification delivery must not roll back a valid learning obligation.
		frappe.log_error(frappe.get_traceback(), "Learning Assignment created notification failed")
		return False


def _send_learning_assignment_reminder(assignment, reminder_code, now):
	reminder_key = f"{assignment.name}|{reminder_code}"
	if frappe.db.exists("LMS Learning Assignment Reminder Log", {"reminder_key": reminder_key}):
		return False
	reminder = frappe.get_doc(
		{
			"doctype": "LMS Learning Assignment Reminder Log",
			"assignment": assignment.name,
			"reminder_code": reminder_code,
			"sent_at": now,
		}
	)
	try:
		reminder.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		return False

	try:
		title = _get_reminder_target_title(assignment)
		notification = frappe._dict(
			{
				"subject": _("Learning due in {0}: {1}").format(reminder_code[2:], title),
				"email_content": _("Your learning assignment is due on {0}.").format(assignment.due_at),
				"document_type": "LMS Learning Assignment",
				"document_name": assignment.name,
				"from_user": assignment.assigned_by,
				"type": "Alert",
				"link": _get_learning_assignment_target_link(assignment),
			}
		)
		make_lms_notification_logs(notification, assignment.learner)
		reminder.notification = frappe.db.get_value(
			"LMS Notification",
			{"for_user": assignment.learner, "document_name": assignment.name},
			"name",
			order_by="creation desc",
		)
		reminder.save(ignore_permissions=True)
		return True
	except Exception:
		frappe.delete_doc(reminder.doctype, reminder.name, ignore_permissions=True)
		raise


def _send_batch_course_sync_notifications(batch, course, learners):
	"""Notify learners only when Batch course sync changed their learning."""
	learners = sorted(set(learners))
	if not learners:
		return 0

	course_title = frappe.db.get_value("LMS Course", course, "title") or course
	batch_title = frappe.db.get_value("LMS Batch", batch, "title") or batch
	notification = frappe._dict(
		{
			"subject": _("New course added to {0}").format(batch_title),
			"email_content": _("{0} has been added to your learning in {1}.").format(
				course_title, batch_title
			),
			"document_type": "LMS Batch",
			"document_name": batch,
			"from_user": _current_user(),
			"type": "Alert",
			"link": f"/courses/{course}",
		}
	)
	try:
		make_lms_notification_logs(notification, learners)
		return len(learners)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Batch course sync notification failed")
		return 0


def reconcile_learning_assignments_and_send_reminders():
	"""Daily scheduler entry point for statuses and D-7/D-3/D-1 reminders."""
	now = get_datetime(now_datetime())
	assignments = frappe.get_all(
		"LMS Learning Assignment", filters={"status": ["!=", CANCELLED_STATUS]}, pluck="name"
	)
	for name in assignments:
		try:
			assignment, state = reconcile_learning_assignment(name, now)
			if state["status"] not in {ACTIVE_STATUS, "In Progress"} or not assignment.due_at:
				continue
			days_remaining = date_diff(getdate(assignment.due_at), getdate(now))
			reminder_code = REMINDER_DAYS.get(days_remaining)
			if reminder_code:
				_send_learning_assignment_reminder(assignment, reminder_code, now)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Learning Assignment reconciliation failed: {name}")


def create_learning_assignment(
	learner,
	target_type,
	target,
	*,
	due_at=None,
	mandatory=True,
	note="",
	source="Manual",
	idempotency_key=None,
):
	"""Create one Course or Batch obligation and materialize its course items."""
	_validate_learner(learner)
	courses = get_target_courses(target_type, target)
	assert_can_manage_learning_assignment_target(target_type, target)

	if source not in {"Manual", "Bulk", "Rule", "Batch Sync"}:
		frappe.throw(_("Invalid learning assignment source."), frappe.ValidationError)
	idempotency_key = (idempotency_key or "").strip() or None
	existing_by_key = _find_idempotent_assignment(_current_user(), idempotency_key)
	if existing_by_key:
		assignment = frappe.get_doc("LMS Learning Assignment", existing_by_key)
		if assignment.learner != learner or assignment.target_type != target_type:
			frappe.throw(_("Idempotency key belongs to another learning assignment."), frappe.ValidationError)
		assignment_target = assignment.course if target_type == "Course" else assignment.batch
		if assignment_target != target:
			frappe.throw(_("Idempotency key belongs to another learning assignment."), frappe.ValidationError)
		return _assignment_response(assignment, already_assigned=True)

	existing = find_active_learning_assignment(learner, target_type, target)
	if existing:
		return _assignment_response(frappe.get_doc("LMS Learning Assignment", existing), already_assigned=True)

	if target_type == "Batch":
		ensure_learning_batch_enrollment(learner, target)

	items = []
	for course in courses:
		enrollment, _created = ensure_learning_enrollment(learner, course)
		items.append(
			{
				"course": course,
				"lms_enrollment": enrollment.name,
				"source_batch": target if target_type == "Batch" else None,
			}
		)

	assignment = frappe.get_doc(
		{
			"doctype": "LMS Learning Assignment",
			"learner": learner,
			"target_type": target_type,
			"course": target if target_type == "Course" else None,
			"batch": target if target_type == "Batch" else None,
			"mandatory": cint(mandatory),
			"due_at": due_at or None,
			"note": (note or "").strip(),
			"source": source,
			"status": ACTIVE_STATUS,
			"assigned_by": _current_user(),
			"assigned_on": now_datetime(),
			"idempotency_key": idempotency_key,
			"items": items,
		}
	)
	try:
		assignment.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		existing = find_active_learning_assignment(learner, target_type, target)
		if not existing:
			raise
		return _assignment_response(frappe.get_doc("LMS Learning Assignment", existing), already_assigned=True)
	_send_learning_assignment_created_notification(assignment)
	return _assignment_response(assignment)


def cancel_learning_assignment(name, reason):
	assignment = frappe.get_doc("LMS Learning Assignment", name)
	target = assignment.course if assignment.target_type == "Course" else assignment.batch
	assert_can_manage_learning_assignment_target(assignment.target_type, target)
	if assignment.status == CANCELLED_STATUS:
		return _assignment_response(assignment)
	if not isinstance(reason, str) or not reason.strip():
		frappe.throw(_("A cancellation reason is required."), frappe.ValidationError)
	assignment.status = CANCELLED_STATUS
	assignment.cancelled_by = _current_user()
	assignment.cancelled_at = now_datetime()
	assignment.cancel_reason = reason.strip()
	assignment.save(ignore_permissions=True)
	return _assignment_response(assignment)


def preview_batch_course_sync(batch, course):
	"""Preview explicit enrollment work when a course is added to an existing Batch."""
	assert_can_manage_learning_assignment_target("Batch", batch)
	if not frappe.db.exists("Batch Course", {"parent": batch, "course": course}):
		frappe.throw(_("The course is not part of this batch."), frappe.ValidationError)
	_validate_course(course)
	members = frappe.get_all("LMS Batch Enrollment", {"batch": batch}, pluck="member")
	missing = [
		member
		for member in members
		if not frappe.db.exists("LMS Enrollment", {"member": member, "course": course})
	]
	assignments = frappe.get_all(
		"LMS Learning Assignment",
		{"batch": batch, "status": ["in", SYNCABLE_ASSIGNMENT_STATUSES]},
		pluck="name",
	)
	return {
		"batch": batch,
		"course": course,
		"existing_members": len(members),
		"learners_requiring_enrollment": len(missing),
		"learners": missing,
		"active_batch_assignments": len(assignments),
		"requires_explicit_confirmation": True,
	}


def sync_batch_course_existing_learners(batch, course, confirm=False):
	"""Explicitly sync one Batch course; never called from Batch validate hooks."""
	if not cint(confirm):
		frappe.throw(_("Confirm Batch sync before creating enrollments."), frappe.ValidationError)
	preview = preview_batch_course_sync(batch, course)
	created_enrollments = 0
	created_items = 0
	changed_learners = set()
	for learner in preview["learners"]:
		_enrollment, created = ensure_learning_enrollment(learner, course)
		created_enrollments += cint(created)
		if created:
			changed_learners.add(learner)

	for assignment_name in frappe.get_all(
		"LMS Learning Assignment",
		{"batch": batch, "status": ["in", SYNCABLE_ASSIGNMENT_STATUSES]},
		pluck="name",
	):
		assignment = frappe.get_doc("LMS Learning Assignment", assignment_name)
		if frappe.db.exists(
			"LMS Learning Assignment Item", {"parent": assignment.name, "course": course, "archived": 0}
		):
			continue
		enrollment, _created = ensure_learning_enrollment(assignment.learner, course)
		assignment.append(
			"items",
			{"course": course, "lms_enrollment": enrollment.name, "source_batch": batch, "archived": 0},
		)
		assignment.save(ignore_permissions=True)
		created_items += 1
		changed_learners.add(assignment.learner)

	notified_learners = _send_batch_course_sync_notifications(batch, course, changed_learners)
	return {
		**preview,
		"synced": True,
		"created_enrollments": created_enrollments,
		"created_items": created_items,
		"notified_learners": notified_learners,
	}


def archive_removed_batch_assignment_items(batch, current_courses):
	"""Keep history if a Batch loses a course; never delete enrollment/progress."""
	current_courses = set(current_courses)
	items = frappe.get_all(
		"LMS Learning Assignment Item",
		filters={"source_batch": batch, "archived": 0},
		fields=["name", "course"],
	)
	for item in items:
		if item.course not in current_courses:
			frappe.db.set_value(
				"LMS Learning Assignment Item", item.name, {"archived": 1, "archived_at": now_datetime()}
			)
