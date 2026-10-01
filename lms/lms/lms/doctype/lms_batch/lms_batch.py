# Copyright (c) 2022, Frappe and contributors
# For license information, please see license.txt

import base64
import json
from datetime import timedelta

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, format_datetime, get_datetime, get_time, getdate, nowdate

from lms.lms.doctype.lms_notification.lms_notification import make_lms_notification_logs
from lms.lms.utils import (
	ensure_instructor_role,
	get_assignment_details,
	get_lesson_index,
	get_lesson_url,
	get_quiz_details,
	render_notification_template,
	update_payment_record,
)


class LMSBatch(Document):
	def validate(self):
		self.validate_seats_left()
		self.validate_batch_end_date()
		self.validate_batch_time()
		self.validate_duplicate_courses()
		self.validate_payments_app()
		self.validate_amount_and_currency()
		self.validate_duplicate_assessments()
		self.validate_timetable()
		self.validate_evaluation_end_date()
		self.validate_instructors()

	def after_insert(self):
		self.notify_moderators_for_approval()

	def on_update(self):
		from lms.lms.learning_assignment import archive_removed_batch_assignment_items

		archive_removed_batch_assignment_items(self.name, [row.course for row in self.courses])
		if self.published and self.has_value_changed("published"):
			self.notify_instructors_of_publish()

	def validate_instructors(self):
		ensure_instructor_role([row.instructor for row in self.instructors])

	def notify_moderators_for_approval(self):
		"""Mirrors LMSCourse.notify_moderators_for_approval - a newly created
		batch sits unpublished until a Moderator publishes it, but nothing
		tells them one is waiting for review."""
		if self.published:
			return

		moderators = frappe.get_all("Has Role", {"role": "Moderator"}, pluck="parent")
		if self.owner in moderators:
			# The creator can publish it themselves, no approval needed.
			return
		if not moderators:
			return

		context = {
			"member_name": frappe.utils.get_fullname(self.owner),
			"title": self.title,
			"description": self.description,
			"url": frappe.utils.get_url(f"/batches/{self.name}/edit"),
		}
		default_subject = _("{0} created a new batch {1} that needs your approval").format(
			context["member_name"], self.title
		)
		subject, email_content = render_notification_template(
			"batch_approval_template", context, default_subject, self.description
		)

		notification = frappe._dict(
			{
				"subject": subject,
				"email_content": email_content,
				"document_type": self.doctype,
				"document_name": self.name,
				"for_user": self.owner,
				"from_user": self.owner,
				"type": "Alert",
				"link": f"/batches/{self.name}/edit",
			}
		)
		make_lms_notification_logs(notification, moderators)

	def notify_instructors_of_publish(self):
		"""Mirrors LMSCourse.notify_instructors_of_publish - once a Moderator
		publishes a batch, the instructors who created it aren't otherwise
		told it's now live."""
		instructors = frappe.get_all("Course Instructor", {"parent": self.name}, pluck="instructor")
		instructors = [instructor for instructor in instructors if instructor != frappe.session.user]
		if not instructors:
			return

		context = {
			"member_name": frappe.utils.get_fullname(frappe.session.user),
			"title": self.title,
			"description": self.description,
			"url": frappe.utils.get_url(f"/batches/details/{self.name}"),
		}
		default_subject = _("Your batch {0} has been approved and published").format(self.title)
		subject, email_content = render_notification_template(
			"batch_published_template", context, default_subject, self.description
		)

		notification = frappe._dict(
			{
				"subject": subject,
				"email_content": email_content,
				"document_type": self.doctype,
				"document_name": self.name,
				"for_user": self.owner,
				"from_user": frappe.session.user,
				"type": "Alert",
				"link": f"/batches/details/{self.name}",
			}
		)
		make_lms_notification_logs(notification, instructors)

	def validate_batch_end_date(self):
		if getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("Batch end date cannot be before the batch start date"))

	def validate_batch_time(self):
		if self.start_time and self.end_time:
			if get_time(self.start_time) >= get_time(self.end_time):
				frappe.throw(_("Batch start time cannot be greater than or equal to end time."))

	def validate_duplicate_courses(self):
		courses = [row.course for row in self.courses]
		duplicates = {course for course in courses if courses.count(course) > 1}
		if len(duplicates):
			title = frappe.db.get_value("LMS Course", next(iter(duplicates)), "title")
			frappe.throw(_("Course {0} has already been added to this batch.").format(frappe.bold(title)))

	def validate_payments_app(self):
		if self.paid_batch:
			installed_apps = frappe.get_installed_apps()
			if "payments" not in installed_apps:
				documentation_link = "https://docs.frappe.io/learning/setting-up-payment-gateway"
				frappe.throw(
					_(
						"Please install the Payments App to create a paid batch. Refer to the documentation for more details. {0}"
					).format(documentation_link)
				)

	def validate_amount_and_currency(self):
		if self.paid_batch and (not self.amount or not self.currency):
			frappe.throw(_("Amount and currency are required for paid batches."))

	def validate_duplicate_assessments(self):
		assessments = [row.assessment_name for row in self.assessment]
		for assessment in self.assessment:
			if assessments.count(assessment.assessment_name) > 1:
				title = frappe.db.get_value(assessment.assessment_type, assessment.assessment_name, "title")
				frappe.throw(
					_("Assessment {0} has already been added to this batch.").format(frappe.bold(title))
				)

	def validate_evaluation_end_date(self):
		if self.evaluation_end_date and getdate(self.evaluation_end_date) < getdate(self.end_date):
			frappe.throw(_("Evaluation end date cannot be less than the batch end date."))

	def validate_seats_left(self):
		if cint(self.seat_count) < 0:
			frappe.throw(_("Seat count cannot be negative."))

		students = frappe.db.count("LMS Batch Enrollment", {"batch": self.name})
		if cint(self.seat_count) and cint(self.seat_count) < students:
			frappe.throw(_("There are no seats available in this batch."))

	def validate_timetable(self):
		for schedule in self.timetable:
			if schedule.start_time and schedule.end_time:
				if get_time(schedule.start_time) > get_time(schedule.end_time) or get_time(
					schedule.start_time
				) == get_time(schedule.end_time):
					frappe.throw(
						_("Row #{0} Start time cannot be greater than or equal to end time.").format(
							schedule.idx
						)
					)

				if get_time(schedule.start_time) < get_time(self.start_time) or get_time(
					schedule.start_time
				) > get_time(self.end_time):
					frappe.throw(
						_("Row #{0} Start time cannot be outside the batch duration.").format(schedule.idx)
					)

				if get_time(schedule.end_time) < get_time(self.start_time) or get_time(
					schedule.end_time
				) > get_time(self.end_time):
					frappe.throw(
						_("Row #{0} End time cannot be outside the batch duration.").format(schedule.idx)
					)

			if getdate(schedule.date) < getdate(self.start_date) or getdate(schedule.date) > getdate(
				self.end_date
			):
				frappe.throw(_("Row #{0} Date cannot be outside the batch duration.").format(schedule.idx))

	def on_payment_authorized(self, payment_status):
		if payment_status in ["Authorized", "Completed"]:
			update_payment_record("LMS Batch", self.name)


@frappe.whitelist()
def create_live_class(
	batch_name,
	title,
	duration,
	date,
	time,
	timezone,
	auto_recording,
	provider="Zoom",
	zoom_account=None,
	teams_account=None,
	description=None,
):
	if provider == "Microsoft Teams":
		return create_teams_live_class(
			teams_account, batch_name, title, duration, date, time, description
		)

	payload = {
		"topic": title,
		"start_time": format_datetime(f"{date} {time}", "yyyy-MM-ddTHH:mm:ssZ"),
		"duration": duration,
		"agenda": description,
		"private_meeting": True,
		"auto_recording": "none" if auto_recording == "No Recording" else auto_recording.lower(),
		"timezone": timezone,
	}
	headers = {
		"Authorization": "Bearer " + authenticate(zoom_account),
		"content-type": "application/json",
	}
	response = requests.post(
		"https://api.zoom.us/v2/users/me/meetings", headers=headers, data=json.dumps(payload)
	)

	if response.status_code == 201:
		data = json.loads(response.text)
		payload.update(
			{
				"doctype": "LMS Live Class",
				"provider": "Zoom",
				"start_url": data.get("start_url"),
				"join_url": data.get("join_url"),
				"meeting_id": data.get("id"),
				"uuid": data.get("uuid"),
				"title": title,
				"host": frappe.session.user,
				"date": date,
				"time": time,
				"batch_name": batch_name,
				"password": data.get("password"),
				"description": description,
				"auto_recording": auto_recording,
				"zoom_account": zoom_account,
			}
		)
		class_details = frappe.get_doc(payload)
		class_details.save()
		return class_details
	else:
		frappe.throw(_("Error creating live class. Please try again. {0}").format(response.text))


def authenticate(zoom_account):
	zoom = frappe.get_doc("LMS Zoom Settings", zoom_account)
	if not zoom.enabled:
		frappe.throw(_("Please enable the zoom account to use this feature."))

	authenticate_url = (
		f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={zoom.account_id}"
	)

	headers = {
		"Authorization": "Basic "
		+ base64.b64encode(
			bytes(
				zoom.client_id + ":" + zoom.get_password(fieldname="client_secret", raise_exception=False),
				encoding="utf8",
			)
		).decode()
	}
	response = requests.request("POST", authenticate_url, headers=headers)
	return response.json()["access_token"]


def create_teams_live_class(teams_account, batch_name, title, duration, date, time, description=None):
	data = create_teams_meeting(teams_account, title, date, time, duration)

	class_details = frappe.get_doc(
		{
			"doctype": "LMS Live Class",
			"provider": "Microsoft Teams",
			"start_url": data.get("joinWebUrl"),
			"join_url": data.get("joinWebUrl"),
			"teams_meeting_id": data.get("id"),
			"title": title,
			"host": frappe.session.user,
			"date": date,
			"time": time,
			"duration": duration,
			"batch_name": batch_name,
			"description": description,
			"teams_account": teams_account,
		}
	)
	class_details.save()
	return class_details


def authenticate_teams(teams_account):
	teams = frappe.get_doc("LMS Teams Settings", teams_account)
	if not teams.enabled:
		frappe.throw(_("Please enable the Teams account to use this feature."))

	token_url = f"https://login.microsoftonline.com/{teams.tenant_id}/oauth2/v2.0/token"
	data = {
		"grant_type": "client_credentials",
		"client_id": teams.client_id,
		"client_secret": teams.get_password(fieldname="client_secret", raise_exception=False),
		"scope": "https://graph.microsoft.com/.default",
	}
	response = requests.post(token_url, data=data)
	if response.status_code != 200:
		frappe.throw(
			_("Error authenticating with Microsoft Teams. Please check the account settings.")
		)
	return response.json()["access_token"]


def create_teams_meeting(teams_account, title, date, time, duration, description=None):
	teams = frappe.get_doc("LMS Teams Settings", teams_account)
	start = get_datetime(f"{date} {time}")
	end = start + timedelta(minutes=cint(duration))

	payload = {
		"subject": title,
		"startDateTime": start.isoformat(),
		"endDateTime": end.isoformat(),
	}
	headers = {
		"Authorization": "Bearer " + authenticate_teams(teams_account),
		"Content-Type": "application/json",
	}
	# Graph API online meetings are created against the organizer's user id;
	# "member" on LMS Teams Settings must be the organizer's Entra ID user (email/UPN).
	response = requests.post(
		f"https://graph.microsoft.com/v1.0/users/{teams.member}/onlineMeetings",
		headers=headers,
		data=json.dumps(payload),
	)

	if response.status_code != 201:
		frappe.throw(_("Error creating live class. Please try again. {0}").format(response.text))
	return response.json()


@frappe.whitelist()
def get_batch_timetable(batch):
	timetable = frappe.get_all(
		"LMS Batch Timetable",
		filters={"parent": batch},
		fields=[
			"reference_doctype",
			"reference_docname",
			"date",
			"start_time",
			"end_time",
			"milestone",
			"name",
			"idx",
			"parent",
		],
		order_by="date",
	)

	show_live_class = frappe.db.get_value("LMS Batch", batch, "show_live_class")
	if show_live_class:
		live_classes = get_live_classes(batch)
		timetable.extend(live_classes)

	timetable = get_timetable_details(timetable)
	return timetable


def get_live_classes(batch):
	live_classes = frappe.get_all(
		"LMS Live Class",
		{"batch_name": batch},
		["name", "title", "date", "time as start_time", "duration", "join_url as url"],
		order_by="date",
	)
	for class_ in live_classes:
		class_.end_time = class_.start_time + timedelta(minutes=class_.duration)
		class_.reference_doctype = "LMS Live Class"
		class_.reference_docname = class_.name
		class_.icon = "icon-call"

	return live_classes


def get_timetable_details(timetable):
	for entry in timetable:
		entry.title = frappe.db.get_value(entry.reference_doctype, entry.reference_docname, "title")
		assessment = frappe._dict({"assessment_name": entry.reference_docname})

		if entry.reference_doctype == "Course Lesson":
			course = frappe.db.get_value(entry.reference_doctype, entry.reference_docname, "course")
			entry.url = get_lesson_url(course, get_lesson_index(entry.reference_docname))

			entry.completed = (
				True
				if frappe.db.exists(
					"LMS Course Progress",
					{
						"lesson": entry.reference_docname,
						"member": frappe.session.user,
						"status": "Complete",
					},
				)
				else False
			)

		elif entry.reference_doctype == "LMS Quiz":
			entry.url = "/quizzes"
			details = get_quiz_details(assessment, frappe.session.user)
			entry.update(details)

		elif entry.reference_doctype == "LMS Assignment":
			details = get_assignment_details(assessment, frappe.session.user)
			entry.update(details)

	timetable = sorted(timetable, key=lambda k: k["date"])
	return timetable


def send_batch_start_reminder():
	batches = frappe.get_all(
		"LMS Batch",
		{"start_date": add_days(nowdate(), 1), "published": 1},
		["name", "title", "start_date", "start_time", "medium"],
	)

	for batch in batches:
		students = frappe.get_all("LMS Batch Enrollment", {"batch": batch.name}, ["member", "member_name"])
		for student in students:
			send_mail(batch, student)


def send_mail(batch, student):
	subject = _("Your batch {0} is starting tomorrow").format(batch.title)
	template = "batch_start_reminder"

	args = {
		"student_name": student.member_name,
		"title": batch.title,
		"start_date": batch.start_date,
		"start_time": batch.start_time,
		"medium": batch.medium,
		"name": batch.name,
	}

	frappe.sendmail(
		recipients=student.member,
		subject=subject,
		template=template,
		args=args,
		header=[_(f"Batch Start Reminder: {batch.title}"), "orange"],
	)
