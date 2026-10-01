"""Optional integration with the "todo" (Worksuite) app: mirrors course
enrollments as Worksuite Tasks so training shows up in an employee's regular
task list ("Learn and Grow", not just "Learn"), logs studied time against
that task, and marks it complete when the course is finished.

Everything here is a soft dependency - if the "todo" app isn't installed on
this site, every function silently no-ops instead of raising, so lms keeps
working standalone. Calls into "todo" go through frappe.call/frappe.get_attr
rather than a Python import, so `import lms` never fails even if "todo" is
absent.
"""

import frappe
from frappe.utils import add_days, cint, getdate


def is_worksuite_installed():
	return "todo" in frappe.get_installed_apps()


def get_employee(user):
	return frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")


def create_learning_task(enrollment):
	"""Creates a Worksuite Task mirroring a new course enrollment, and stores
	its name back on the LMS Enrollment. No-ops if "todo" isn't installed or
	the member has no linked Employee record.
	"""
	if not is_worksuite_installed() or enrollment.worksuite_task:
		return

	employee = get_employee(enrollment.member)
	if not employee:
		return

	course_title = frappe.db.get_value("LMS Course", enrollment.course, "title") or enrollment.course

	# Deliberately left without a `project` - the todo app gates a set of
	# workflow-mode guards (Pilot / New Workflow) behind `if self.project`,
	# and those guards reference a custom_task_workflow_mode column that
	# isn't present in every deployment. Leaving `project` unset keeps
	# creation on the plain, ungated path.
	#
	# custom_assignee (Employee) alone does NOT make the task show up as
	# "assigned to me" anywhere in Worksuite - its personal task views,
	# notifications, overdue-accountability reminders, and the dashboard's
	# "prioritized tasks" widget all key off custom_assign_to (User) instead
	# (see todo/api/task.py get_prioritized_tasks, todo/notifications/*,
	# todo/overdue_accountability/send_plan.py). Without it, the task exists
	# in the database and reports correctly at the department level, but the
	# enrolled member themselves never sees it as their own.
	task = frappe.get_doc(
		{
			"doctype": "Task",
			"subject": f"Complete course: {course_title}",
			"custom_assignee": employee,
			"custom_assign_to": enrollment.member,
			"status": "Open",
			"exp_end_date": add_days(getdate(), 30),
		}
	)
	task.insert(ignore_permissions=True)

	frappe.db.set_value("LMS Enrollment", enrollment.name, "worksuite_task", task.name)


def log_learning_work(enrollment):
	"""Logs the member's total time spent on this course (from LMS Course
	Time Log) as a single Work Log Entry against the linked Worksuite Task.
	"""
	if not enrollment.worksuite_task:
		return

	total_seconds = frappe.db.sql(
		"""select sum(seconds_spent) from `tabLMS Course Time Log`
		where member=%s and course=%s""",
		(enrollment.member, enrollment.course),
	)[0][0] or 0

	hours_spent = round(cint(total_seconds) / 3600, 2)
	if hours_spent <= 0:
		return

	create_work_log = frappe.get_attr("todo.api.work_log.create_work_log")
	create_work_log(
		# "Work Log Entry.work_type" is a fixed Select (Work/Review/Meeting/
		# Blocked/Research) with no "Learning" option - Research is the
		# closest existing fit for self-directed study time.
		work_type="Research",
		description="Time spent studying via LMS",
		task=enrollment.worksuite_task,
		hours_spent=hours_spent,
		current_progress_pct=100,
	)


def complete_learning_task(enrollment):
	"""Logs accumulated study time and marks the linked Worksuite Task
	Completed once the course itself reaches 100% progress. Safe to call
	repeatedly - no-ops once the task is already marked complete.
	"""
	if not is_worksuite_installed() or not enrollment.worksuite_task:
		return

	if frappe.db.get_value("Task", enrollment.worksuite_task, "status") == "Completed":
		return

	try:
		log_learning_work(enrollment)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(), f"Failed to log Worksuite work for {enrollment.name}"
		)

	frappe.db.set_value(
		"Task",
		enrollment.worksuite_task,
		{"status": "Completed", "progress": 100},
	)
