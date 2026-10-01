# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.realtime import get_website_room
from frappe.utils import flt
from frappe.utils.telemetry import capture

from lms.lms.utils import get_course_progress, has_met_reading_time

from ...md import find_macros


class CourseLesson(Document):
	def on_update(self):
		self.validate_quiz_id()

	def validate_quiz_id(self):
		if self.quiz_id and not frappe.db.exists("LMS Quiz", self.quiz_id):
			frappe.throw(_("Invalid Quiz ID"))

		if self.content:
			self.save_lesson_details_in_quiz(self.content)

		if self.instructor_content:
			self.save_lesson_details_in_quiz(self.instructor_content)

	def save_lesson_details_in_quiz(self, content):
		content = json.loads(self.content)
		for block in content.get("blocks"):
			if block.get("type") == "quiz":
				quiz = block.get("data").get("quiz")
				if not frappe.db.exists("LMS Quiz", quiz):
					frappe.throw(_("Invalid Quiz ID in content"))
				frappe.db.set_value(
					"LMS Quiz",
					quiz,
					{
						"course": self.course,
						"lesson": self.name,
					},
				)


@frappe.whitelist()
def save_progress(lesson, course, scorm_details=None):
	"""
	Note: Pass the argument scorm_details as a dict if it is SCORM related save_progress
	"""
	membership = frappe.db.exists("LMS Enrollment", {"course": course, "member": frappe.session.user})
	if not membership:
		return 0

	frappe.db.set_value("LMS Enrollment", membership, "current_lesson", lesson)
	progress_already_exists = frappe.db.exists(
		"LMS Course Progress", {"lesson": lesson, "member": frappe.session.user}
	)
	lesson_already_completed = frappe.db.exists(
		"LMS Course Progress",
		{"lesson": lesson, "member": frappe.session.user, "status": "Complete"},
	)

	quiz_completed = get_quiz_progress(lesson)
	assignment_completed = get_assignment_progress(lesson)
	video_completed = get_video_progress(lesson)
	min_reading_time = frappe.db.get_value("Course Lesson", lesson, "min_reading_time")
	# For video lessons, watching to the configured completion threshold (video_completed,
	# above) already proves engagement - watch_time itself is capped server-side to real
	# elapsed wall-clock time since the lesson was opened (see track_video_watch_duration).
	# Also requiring min_reading_time on top of that double-counts the same signal, and
	# unlike video watch tracking, has_met_reading_time subtracts tab-hidden intervals -
	# which are normal while a video keeps playing in the background - so a fully-watched
	# video could still fail this gate. So min_reading_time only gates lessons without video.
	reading_time_met = True if lesson_has_video(lesson) else has_met_reading_time(lesson, min_reading_time)

	if scorm_details:
		scorm_details = frappe._dict(**scorm_details)

	if (
		not lesson_already_completed
		and quiz_completed
		and assignment_completed
		and video_completed
		and reading_time_met
		and not scorm_details
	):
		if progress_already_exists:
			frappe.db.set_value("LMS Course Progress", progress_already_exists, "status", "Complete")
		else:
			frappe.get_doc(
				{
					"doctype": "LMS Course Progress",
					"lesson": lesson,
					"status": "Complete",
					"member": frappe.session.user,
				}
			).save(ignore_permissions=True)
	elif scorm_details and not lesson_already_completed and not progress_already_exists:
		# Create new SCORM progress
		frappe.get_doc(
			{
				"doctype": "LMS Course Progress",
				"lesson": lesson,
				"status": "Complete" if scorm_details.is_complete else "Partially Complete",
				"member": frappe.session.user,
				"scorm_content": "" if scorm_details.is_complete else scorm_details.scorm_content,
			}
		).save(ignore_permissions=True)
	elif scorm_details and not lesson_already_completed and progress_already_exists:
		# Update Existing SCORM Progress
		frappe.db.set_value(
			"LMS Course Progress",
			progress_already_exists,
			{
				"lesson": lesson,
				"status": "Complete" if scorm_details.is_complete else "Partially Complete",
				"member": frappe.session.user,
				"scorm_content": "" if scorm_details.is_complete else scorm_details.scorm_content,
			},
		)

	progress = get_course_progress(course)
	capture_progress_for_analytics(progress, course)

	# Had to get doc, as on_change doesn't trigger when you use set_value. The trigger is necessary for badge to get assigned.
	enrollment = frappe.get_doc("LMS Enrollment", membership)
	enrollment.progress = progress
	enrollment.save(ignore_permissions=True)
	enrollment.run_method("on_change")

	frappe.publish_realtime(
		event="update_lesson_progress",
		room=get_website_room(),
		message={"course": course, "lesson": lesson, "progress": progress},
		after_commit=True,
	)

	lesson_completed = bool(
		frappe.db.exists(
			"LMS Course Progress",
			{"lesson": lesson, "member": frappe.session.user, "status": "Complete"},
		)
	)

	return {
		"progress": progress,
		"lesson_completed": lesson_completed,
		"quiz_completed": quiz_completed,
		"assignment_completed": assignment_completed,
		"video_completed": video_completed,
		"reading_time_met": reading_time_met,
	}


def capture_progress_for_analytics(progress, course):
	if progress in [25, 50, 75, 100]:
		capture("course_progress", "lms", properties={"course": course, "progress": progress})


def get_quiz_progress(lesson):
	lesson_details = frappe.db.get_value(
		"Course Lesson", lesson, ["body", "content", "completion_quiz"], as_dict=1
	)
	quizzes = []

	if lesson_details.content:
		content = json.loads(lesson_details.content)

		for block in content.get("blocks"):
			if block.get("type") == "quiz":
				quizzes.append(block.get("data").get("quiz"))
			if block.get("type") == "upload":
				quizzes_in_video = block.get("data").get("quizzes")
				if quizzes_in_video and len(quizzes_in_video) > 0:
					for row in quizzes_in_video:
						quizzes.append(row.get("quiz"))

	elif lesson_details.body:
		macros = find_macros(lesson_details.body)
		quizzes = [value for name, value in macros if name == "Quiz"]

	# Mandatory completion quiz
	if lesson_details.completion_quiz:
		quizzes.append(lesson_details.completion_quiz)

	for quiz in quizzes:
		passing_percentage = frappe.db.get_value("LMS Quiz", quiz, "passing_percentage")
		if not frappe.db.exists(
			"LMS Quiz Submission",
			{
				"quiz": quiz,
				"member": frappe.session.user,
				"percentage": [">=", passing_percentage],
			},
		):
			return False
	return True


def get_assignment_progress(lesson):
	lesson_details = frappe.db.get_value("Course Lesson", lesson, ["body", "content"], as_dict=1)
	assignments = []

	if lesson_details.content:
		content = json.loads(lesson_details.content)

		for block in content.get("blocks"):
			if block.get("type") == "assignment":
				assignments.append(block.get("data").get("assignment"))

	elif lesson_details.body:
		macros = find_macros(lesson_details.body)
		assignments = [value for name, value in macros if name == "Assignment"]

	for assignment in assignments:
		if not frappe.db.exists(
			"LMS Assignment Submission",
			{"assignment": assignment, "member": frappe.session.user},
		):
			return False
	return True


@frappe.whitelist()
def get_lesson_info(chapter):
	return frappe.db.get_value("Course Chapter", chapter, "course")


def lesson_has_video(lesson):
	lesson_details = frappe.db.get_value("Course Lesson", lesson, ["body", "content"], as_dict=1)
	if not lesson_details:
		return False

	if lesson_details.content:
		content = json.loads(lesson_details.content)
		for block in content.get("blocks", []):
			if block.get("type") == "upload" and block.get("data", {}).get(
				"file_type", ""
			).lower() in ["mp4", "webm", "ogg", "mov"]:
				return True
			if block.get("type") == "embed":
				return True
	elif lesson_details.body:
		macros = find_macros(lesson_details.body)
		videos = [value for name, value in macros if name in ["YouTubeVideo", "Video"]]
		if videos:
			return True

	return False


def get_video_progress(lesson):
	if not frappe.db.exists("Course Lesson", lesson):
		return True

	if not lesson_has_video(lesson):
		return True

	override, lesson_threshold = frappe.db.get_value(
		"Course Lesson", lesson, ["override_video_completion_threshold", "video_completion_threshold"]
	)
	if override:
		threshold = flt(lesson_threshold)
	else:
		threshold = flt(frappe.db.get_single_value("LMS Settings", "video_completion_threshold") or 90)

	records = frappe.get_all(
		"LMS Video Watch Duration",
		filters={"lesson": lesson, "member": frappe.session.user},
		fields=["watch_time", "duration"],
	)
	if not records:
		return False

	for rec in records:
		watch_time = flt(rec.get("watch_time"))
		duration = flt(rec.get("duration"))
		if duration > 0:
			pct = (watch_time / duration) * 100
			if pct >= threshold:
				return True
		elif watch_time > 0 and threshold == 0:
			return True

	return False
