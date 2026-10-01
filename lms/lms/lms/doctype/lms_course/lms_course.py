# Copyright (c) 2021, Frappe and contributors
# For license information, please see license.txt

import json
import random

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from lms.lms.doctype.lms_notification.lms_notification import make_lms_notification_logs
from lms.lms.utils import ensure_instructor_role, get_chapters, render_notification_template

from ...utils import update_payment_record, validate_image


class LMSCourse(Document):
	def validate(self):
		self.validate_published()
		self.validate_instructors()
		self.validate_video_link()
		self.validate_status()
		self.validate_payments_app()
		self.validate_certification()
		self.validate_amount_and_currency()
		self.image = validate_image(self.image)
		self.validate_card_gradient()

	def after_insert(self):
		self.notify_moderators_for_approval()

	def validate_published(self):
		if self.published and not self.published_on:
			self.published_on = today()

	def validate_instructors(self):
		if self.is_new() and not self.instructors:
			frappe.get_doc(
				{
					"doctype": "Course Instructor",
					"instructor": self.owner,
					"parent": self.name,
					"parentfield": "instructors",
					"parenttype": "LMS Course",
				}
			).save(ignore_permissions=True)

		ensure_instructor_role([row.instructor for row in self.instructors])

	def validate_video_link(self):
		if self.video_link and "/" in self.video_link:
			self.video_link = self.video_link.split("/")[-1]

	def validate_status(self):
		if self.published:
			self.status = "Approved"

	def validate_payments_app(self):
		if self.paid_course:
			installed_apps = frappe.get_installed_apps()
			if "payments" not in installed_apps:
				documentation_link = "https://docs.frappe.io/learning/setting-up-payment-gateway"
				frappe.throw(
					_(
						"Please install the Payments App to create a paid course. Refer to the documentation for more details. {0}"
					).format(documentation_link)
				)

	def validate_certification(self):
		if self.enable_certification and self.paid_certificate:
			frappe.throw(_("A course cannot have both paid certificate and certificate of completion."))

		if self.paid_certificate and not self.evaluator:
			frappe.throw(_("Evaluator is required for paid certificates."))

		if self.paid_certificate and not self.timezone:
			frappe.throw(_("Timezone is required for paid certificates."))

	def validate_amount_and_currency(self):
		if self.paid_course and (cint(self.course_price) < 0 or not self.currency):
			frappe.throw(_("Amount and currency are required for paid courses."))

		if self.paid_certificate and (cint(self.course_price) <= 0 or not self.currency):
			frappe.throw(_("Amount and currency are required for paid certificates."))

	def validate_card_gradient(self):
		if not self.image and not self.card_gradient:
			colors = [
				"Red",
				"Blue",
				"Green",
				"Yellow",
				"Orange",
				"Pink",
				"Amber",
				"Violet",
				"Cyan",
				"Teal",
				"Gray",
				"Purple",
			]
			self.card_gradient = random.choice(colors)

	def on_update(self):
		if not self.upcoming and self.has_value_changed("upcoming"):
			self.send_email_to_interested_users()
		if self.published and self.has_value_changed("published"):
			self.notify_instructors_of_publish()

	def notify_moderators_for_approval(self):
		"""A newly created course sits unpublished until a Moderator publishes
		it (only Moderators can toggle "published" from the UI). Nothing else
		tells them a course is waiting, so a Moderator has to stumble onto it
		under Courses > Unpublished."""
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
			"description": self.short_introduction,
			"url": frappe.utils.get_url(f"/courses/{self.name}/edit"),
		}
		default_subject = _("{0} created a new course {1} that needs your approval").format(
			context["member_name"], self.title
		)
		subject, email_content = render_notification_template(
			"course_approval_template", context, default_subject, self.short_introduction
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
				"link": f"/courses/{self.name}/edit",
			}
		)
		make_lms_notification_logs(notification, moderators)

	def notify_instructors_of_publish(self):
		"""Mirrors notify_moderators_for_approval in the other direction: once
		a Moderator publishes a course, the instructors who created it aren't
		otherwise told it's now live."""
		instructors = frappe.get_all("Course Instructor", {"parent": self.name}, pluck="instructor")
		instructors = [instructor for instructor in instructors if instructor != frappe.session.user]
		if not instructors:
			return

		context = {
			"member_name": frappe.utils.get_fullname(frappe.session.user),
			"title": self.title,
			"description": self.short_introduction,
			"url": frappe.utils.get_url(f"/courses/{self.name}"),
		}
		default_subject = _("Your course {0} has been approved and published").format(self.title)
		subject, email_content = render_notification_template(
			"course_published_template", context, default_subject, self.short_introduction
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
				"link": f"/courses/{self.name}",
			}
		)
		make_lms_notification_logs(notification, instructors)

	def on_payment_authorized(self, payment_status):
		if payment_status in ["Authorized", "Completed"]:
			update_payment_record("LMS Course", self.name)

	def send_email_to_interested_users(self):
		interested_users = frappe.get_all("LMS Course Interest", {"course": self.name}, ["name", "user"])
		subject = self.title + " is available!"
		args = {
			"title": self.title,
			"course_link": f"/lms/courses/{self.name}",
			"app_name": frappe.db.get_single_value("System Settings", "app_name"),
			"site_url": frappe.utils.get_url(),
		}

		for user in interested_users:
			args["first_name"] = frappe.db.get_value("User", user.user, "first_name")
			email_args = frappe._dict(
				recipients=user.user,
				subject=subject,
				header=[subject, "green"],
				template="lms_course_interest",
				args=args,
				now=True,
			)
			frappe.enqueue(method=frappe.sendmail, queue="short", timeout=300, is_async=True, **email_args)
			frappe.db.set_value("LMS Course Interest", user.name, "email_sent", True)

	def __repr__(self):
		return f"<Course#{self.name}>"

	def has_mentor(self, email):
		"""Checks if this course has a mentor with given email."""
		if not email or email == "Guest":
			return False

		mapping = frappe.get_all("LMS Course Mentor Mapping", {"course": self.name, "mentor": email})
		return mapping != []

	def add_mentor(self, email):
		"""Adds a new mentor to the course."""
		if not email:
			raise ValueError("Invalid email")
		if email == "Guest":
			raise ValueError("Guest user can not be added as a mentor")

		# given user is already a mentor
		if self.has_mentor(email):
			return

		doc = frappe.get_doc({"doctype": "LMS Course Mentor Mapping", "course": self.name, "mentor": email})
		doc.insert()

	def get_student_batch(self, email):
		"""Returns the batch the given student is part of.

		Returns None if the student is not part of any batch.
		"""
		if not email:
			return

		batch_name = frappe.get_value(
			doctype="LMS Enrollment",
			filters={"course": self.name, "member_type": "Student", "member": email},
			fieldname="batch_old",
		)
		return batch_name and frappe.get_doc("LMS Batch Old", batch_name)

	def get_batches(self, mentor=None):
		batches = frappe.get_all("LMS Batch Old", {"course": self.name})
		if mentor:
			# TODO: optimize this
			memberships = frappe.db.get_all("LMS Enrollment", {"member": mentor}, ["batch_old"])
			batch_names = {m.batch_old for m in memberships}
			return [b for b in batches if b.name in batch_names]

	def get_cohorts(self):
		return frappe.get_all(
			"Cohort",
			{"course": self.name},
			["name", "slug", "title", "begin_date", "end_date"],
			order_by="creation",
		)

	def get_cohort(self, cohort_slug):
		name = frappe.get_value("Cohort", {"course": self.name, "slug": cohort_slug})
		return name and frappe.get_doc("Cohort", name)

	def reindex_exercises(self):
		for i, c in enumerate(get_chapters(self.name), start=1):
			self._reindex_exercises_in_chapter(c, i)

	def _reindex_exercises_in_chapter(self, c, index):
		i = 1
		for lesson in self.get_lessons(c):
			for exercise in lesson.get_exercises():
				exercise.index_ = i
				exercise.index_label = f"{index}.{i}"
				exercise.save()
				i += 1

	def get_all_memberships(self, member):
		all_memberships = frappe.get_all(
			"LMS Enrollment", {"member": member, "course": self.name}, ["batch_old"]
		)
		for membership in all_memberships:
			membership.batch_title = frappe.db.get_value("LMS Batch Old", membership.batch_old, "title")
		return all_memberships


@frappe.whitelist()
def reindex_exercises(doc):
	course_data = json.loads(doc)
	course = frappe.get_doc("LMS Course", course_data["name"])
	course.reindex_exercises()
	frappe.msgprint("All exercises in this course have been re-indexed.")
