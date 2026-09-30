# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import json
import random
import re
from binascii import Error as BinasciiError

import frappe
from frappe import _, safe_decode
from frappe.core.doctype.file.utils import get_random_filename
from frappe.model.document import Document
from frappe.utils import cint, comma_and, cstr, now_datetime, time_diff_in_seconds
from frappe.utils.file_manager import safe_b64decode
from fuzzywuzzy import fuzz

from lms.lms.doctype.course_lesson.course_lesson import save_progress
from lms.lms.utils import (
	check_quiz_access,
)

# Grace period to absorb network/render latency between the client-side timer
# hitting zero and the auto-submit request actually reaching the server.
QUIZ_DURATION_GRACE_SECONDS = 60


class LMSQuiz(Document):
	def validate(self):
		self.validate_duplicate_questions()
		self.validate_limit()
		self.calculate_total_marks()
		self.validate_open_ended_questions()
		self.validate_passing_percentage()

	def validate_passing_percentage(self):
		percentage = cint(self.passing_percentage)
		if percentage < 0 or percentage > 100:
			frappe.throw(_("Passing Percentage must be between 0 and 100."))

	def validate_duplicate_questions(self):
		questions = [row.question for row in self.questions]
		rows = [i + 1 for i, x in enumerate(questions) if questions.count(x) > 1]
		if len(rows):
			frappe.throw(_("Rows {0} have the duplicate questions.").format(frappe.bold(comma_and(rows))))

	def validate_limit(self):
		if self.limit_questions_to and cint(self.limit_questions_to) >= len(self.questions):
			frappe.throw(_("Limit cannot be greater than or equal to the number of questions in the quiz."))

		if self.limit_questions_to and cint(self.limit_questions_to) < len(self.questions):
			marks = [question.marks for question in self.questions]
			if len(set(marks)) > 1:
				frappe.throw(_("All questions should have the same marks if the limit is set."))

	def calculate_total_marks(self):
		if len(self.questions) == 0:
			self.total_marks = 0
			return

		if self.limit_questions_to:
			self.total_marks = sum(
				question.marks for question in self.questions[: cint(self.limit_questions_to)]
			)
		else:
			self.total_marks = sum(cint(question.marks) for question in self.questions)

	def validate_open_ended_questions(self):
		types = [question.type for question in self.questions]
		types = set(types)

		if "Open Ended" in types:
			if len(types) > 1:
				frappe.throw(
					_(
						"If you want open ended questions then make sure each question in the quiz is of open ended type."
					)
				)
			else:
				self.show_answers = 0

	def get_last_submission_details(self):
		"""Returns the latest submission for this user."""
		user = frappe.session.user
		if not user or user == "Guest":
			return

		result = frappe.get_all(
			"LMS Quiz Submission",
			fields="*",
			filters={"owner": user, "quiz": self.name},
			order_by="creation desc",
			page_length=1,
		)

		if result:
			return result[0]


@frappe.whitelist()
def get_quiz(quiz):
	"""Returns quiz metadata for the student-facing quiz runner. Deliberately
	excludes the `questions` child table, which embeds the full text of every
	question (via question_detail) regardless of shuffle_questions or
	limit_questions_to — sending it here would hand the browser the entire
	question bank up front. Use get_quiz_questions/get_question_details to
	fetch the (server-selected) questions and their content instead."""
	quiz_doc = frappe.get_doc("LMS Quiz", quiz)
	check_quiz_access(quiz_doc)

	fields = [
		"name",
		"title",
		"max_attempts",
		"show_answers",
		"show_submission_history",
		"total_marks",
		"passing_percentage",
		"duration",
		"shuffle_questions",
		"limit_questions_to",
		"enable_negative_marking",
		"marks_to_cut",
		"lesson",
		"course",
	]
	quiz_details = {field: quiz_doc.get(field) for field in fields}
	quiz_details["integrity_violation_threshold_seconds"] = (
		frappe.db.get_value(
			"LMS Course", quiz_doc.course, "integrity_violation_threshold_seconds"
		)
		if quiz_doc.course
		else None
	) or 2
	return quiz_details


@frappe.whitelist()
def get_quiz_questions(quiz):
	"""Selects (and shuffles/limits, per the quiz's own settings) the question
	set for this attempt on the server, instead of sending the full question
	bank to the browser and trusting it to slice/shuffle client-side. Only
	question refs are returned here — the actual question text and options
	are fetched one at a time via get_question_details."""
	quiz_doc = frappe.get_doc("LMS Quiz", quiz)
	check_quiz_access(quiz_doc)

	questions = [
		{"name": row.name, "question": row.question, "marks": row.marks, "type": row.type}
		for row in quiz_doc.questions
	]

	if quiz_doc.shuffle_questions:
		random.shuffle(questions)

	if quiz_doc.limit_questions_to:
		questions = questions[: cint(quiz_doc.limit_questions_to)]

	return questions


def set_total_marks(questions):
	marks = 0
	for question in questions:
		marks += question.get("marks")
	return marks


@frappe.whitelist()
def quiz_summary(quiz, results=None):
	if isinstance(results, str):
		results = json.loads(results) if results else []
	elif not results:
		results = []
	percentage = 0

	quiz_details = frappe.db.get_value(
		"LMS Quiz",
		quiz,
		[
			"name",
			"total_marks",
			"passing_percentage",
			"lesson",
			"course",
			"enable_negative_marking",
			"marks_to_cut",
			"duration",
		],
		as_dict=1,
	)

	check_quiz_access(quiz_details)

	attempt = validate_quiz_duration(quiz_details, frappe.session.user)

	data = process_results(results, quiz_details)
	results = data["results"]
	score = data["score"]
	is_open_ended = data["is_open_ended"]

	score_out_of = quiz_details.total_marks
	percentage = (score / score_out_of) * 100 if score_out_of else 0
	submission = create_submission(
		quiz, results, score_out_of, quiz_details.passing_percentage, is_open_ended
	)

	if attempt:
		frappe.db.set_value("LMS Quiz Attempt", attempt.name, "submission", submission.name)

	save_progress_after_quiz(quiz_details, percentage)

	return {
		"score": score,
		"score_out_of": score_out_of,
		"submission": submission.name,
		"pass": percentage >= quiz_details.passing_percentage,
		"percentage": percentage,
		"is_open_ended": is_open_ended,
	}


@frappe.whitelist()
def start_quiz_attempt(quiz):
	"""Records (or resumes) a server-side start time for this user's attempt,
	so the quiz duration can be enforced independently of the client-side timer.
	Returns the remaining time computed server-side, so the client never has to
	reconcile timezone-dependent timestamps itself."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please log in to take this quiz."))

	check_quiz_access(frappe.get_doc("LMS Quiz", quiz))

	duration = cint(frappe.db.get_value("LMS Quiz", quiz, "duration"))
	if not duration:
		return {"duration": 0, "remaining_seconds": None}

	attempt = get_open_attempt(quiz, user)
	if not attempt or is_attempt_expired(attempt, duration):
		attempt = frappe.get_doc(
			{
				"doctype": "LMS Quiz Attempt",
				"quiz": quiz,
				"member": user,
				"start_time": now_datetime(),
			}
		).insert(ignore_permissions=True)

	elapsed = time_diff_in_seconds(now_datetime(), attempt.start_time)
	remaining_seconds = max(duration * 60 - int(elapsed), 0)

	return {"duration": duration, "remaining_seconds": remaining_seconds, "name": attempt.name}


ATTEMPT_CLAIM_MARKER = "__claiming__"


def get_open_attempt(quiz, user):
	"""frappe.get_all is used here (rather than a plain db.get_value filter)
	because it's the NULL-safe form: a brand-new attempt's "submission"
	column is NULL, not "", and only get_all's query builder treats an
	empty-string filter as matching that."""
	attempts = frappe.get_all(
		"LMS Quiz Attempt",
		filters={"quiz": quiz, "member": user, "submission": ""},
		fields=["name", "start_time"],
		order_by="creation desc",
		limit_page_length=1,
	)
	return attempts[0] if attempts else None


def claim_attempt_for_submission(attempt_name):
	"""Atomically marks the attempt as claimed via a conditional UPDATE, so two
	concurrent duplicate submissions for the same attempt (double-click, or a
	client retry after a timed-out request) can't both succeed.

	Deliberately not a SELECT ... FOR UPDATE: MariaDB 11 runs with
	innodb_snapshot_isolation=ON by default, under which a locking read
	inside Frappe's long-lived per-request transaction that has to wait for a
	concurrently-modified row raises "Record has changed since last read"
	(error 1020) instead of quietly seeing the new value once unblocked. A
	single UPDATE with a WHERE guard sidesteps that, since InnoDB evaluates
	an UPDATE's WHERE clause and takes its lock against the row's current
	version, not the transaction's original snapshot. That UPDATE can still
	hit error 1020 itself if this row was already changed by another
	transaction since ours began, so that specific error is treated as "someone
	else already claimed it" rather than left to bubble up as a raw 500.
	"""
	try:
		frappe.db.sql(
			"""
			update `tabLMS Quiz Attempt`
			set submission = %s
			where name = %s and (submission is null or submission = '')
			""",
			(ATTEMPT_CLAIM_MARKER, attempt_name),
		)
	except Exception as e:
		if getattr(e, "args", None) and e.args[0] == 1020:
			frappe.db.rollback()
			return False
		raise

	return frappe.db.sql("select row_count()")[0][0] == 1


def is_attempt_expired(attempt, duration):
	elapsed = time_diff_in_seconds(now_datetime(), attempt.start_time)
	return elapsed > (duration * 60 + QUIZ_DURATION_GRACE_SECONDS)


def validate_quiz_duration(quiz_details, user):
	"""Rejects a submission if it arrives after the quiz's server-tracked
	start time plus its duration (and a small network-latency grace period),
	and exclusively claims the attempt so it can't be submitted twice."""
	duration = cint(quiz_details.get("duration"))
	if not duration:
		return None

	attempt = get_open_attempt(quiz_details.name, user)
	if not attempt:
		if frappe.db.exists("LMS Quiz Attempt", {"quiz": quiz_details.name, "member": user}):
			frappe.throw(_("This quiz attempt has already been submitted."))
		frappe.throw(_("No active attempt found for this quiz. Please start the quiz again."))

	if is_attempt_expired(attempt, duration):
		frappe.throw(_("The time limit for this quiz has expired. Please start the quiz again."))

	if not claim_attempt_for_submission(attempt.name):
		frappe.throw(_("This quiz attempt has already been submitted."))

	return attempt


def process_results(results, quiz_details):
	results = results or []
	score = 0
	is_open_ended = False

	for result in results:
		question_details = frappe.db.get_value(
			"LMS Quiz Question",
			{"parent": quiz_details.name, "question": result["question_name"]},
			["question", "marks", "question_detail", "type"],
			as_dict=1,
		)

		result["question_name"] = question_details.question
		result["question"] = question_details.question_detail
		result["marks_out_of"] = question_details.marks

		if question_details.type != "Open Ended":
			raw_ans = result.get("answer", "")
			if isinstance(raw_ans, list):
				submitted_answers = [cstr(a).strip() for a in raw_ans]
			elif isinstance(raw_ans, str) and raw_ans.startswith("[") and raw_ans.endswith("]"):
				try:
					submitted_answers = [cstr(a).strip() for a in json.loads(raw_ans)]
				except Exception:
					submitted_answers = [a.strip() for a in cstr(raw_ans).split(",") if a.strip()]
			else:
				submitted_answers = [a.strip() for a in cstr(raw_ans).split(",") if a.strip()]

			correct = evaluate_answer(question_details.question, question_details.type, submitted_answers)
			result["is_correct"] = correct

			if correct:
				marks = question_details.marks
			else:
				marks = -quiz_details.marks_to_cut if quiz_details.enable_negative_marking else 0

			result["marks"] = marks
			score += marks

		else:
			is_open_ended = True
			result["is_correct"] = 0
			result["answer"] = re.sub(
				r'<img[^>]*src\s*=\s*["\'](?=data:)(.*?)["\']', _save_file, result["answer"]
			)

	return {
		"results": results,
		"score": score,
		"is_open_ended": is_open_ended,
	}


def evaluate_answer(question, type, submitted_answers):
	"""Recomputes correctness server-side from the DB, ignoring any is_correct
	value the client may have sent, since that value is user-editable (e.g. via
	localStorage) before the final submission request."""
	if type == "Choices":
		fields = []
		for num in range(1, 5):
			fields.append(f"option_{num}")
			fields.append(f"is_correct_{num}")

		question_details = frappe.db.get_value("LMS Question", question, fields, as_dict=1)
		if not question_details:
			return False

		correct_options = {
			cstr(question_details.get(f"option_{num}")).strip()
			for num in range(1, 5)
			if question_details.get(f"option_{num}") and question_details.get(f"is_correct_{num}")
		}
		submitted_set = {cstr(ans).strip() for ans in submitted_answers if cstr(ans).strip()}
		return submitted_set == correct_options

	return bool(check_input_answers(question, submitted_answers[0] if submitted_answers else ""))


def _save_file(match):
	data = match.group(1).split("data:")[1]
	headers, content = data.split(",")
	mtype = headers.split(";", 1)[0]

	if isinstance(content, str):
		content = content.encode("utf-8")
	if b"," in content:
		content = content.split(b",")[1]

	try:
		content = safe_b64decode(content)
	except BinasciiError:
		frappe.flags.has_dataurl = True
		return f'<img src="#broken-image" alt="{get_corrupted_image_msg()}"'

	if "filename=" in headers:
		filename = headers.split("filename=")[-1]
		filename = safe_decode(filename).split(";", 1)[0]

	else:
		filename = get_random_filename(content_type=mtype)

	_file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"decode": False,
			"is_private": False,
		}
	)
	_file.save(ignore_permissions=True)
	file_url = _file.unique_url
	frappe.flags.has_dataurl = True

	return f'<img src="{file_url}"'


def get_corrupted_image_msg():
	return _("Image: Corrupted Data Stream")


def create_submission(quiz, results, score_out_of, passing_percentage, is_open_ended=False):
	submission = frappe.new_doc("LMS Quiz Submission")
	# Score and percentage are calculated by the controller function
	submission.update(
		{
			"doctype": "LMS Quiz Submission",
			"quiz": quiz,
			"result": results,
			"score": 0,
			"score_out_of": score_out_of,
			"member": frappe.session.user,
			"percentage": 0,
			"passing_percentage": passing_percentage,
		}
	)
	submission.save(ignore_permissions=True)

	if is_open_ended:
		notify_instructors_of_open_ended_submission(submission)

	return submission


def notify_instructors_of_open_ended_submission(submission):
	"""Open Ended questions aren't auto-scored (see process_results), so an
	instructor needs to manually review them. Nothing else in the quiz
	submission flow tells them a submission is waiting."""
	from lms.lms.doctype.lms_notification.lms_notification import make_lms_notification_logs

	instructors = frappe.db.get_all(
		"Course Instructor", {"parent": submission.course}, pluck="instructor"
	)
	instructors = [instructor for instructor in instructors if instructor != submission.member]
	if not instructors:
		return

	notification = frappe._dict(
		{
			"subject": _("{0} submitted answers for {1} that need manual grading").format(
				submission.member_name, submission.quiz_title
			),
			"email_content": _("This submission has open-ended answers that need to be graded."),
			"document_type": submission.doctype,
			"document_name": submission.name,
			"for_user": submission.owner,
			"from_user": submission.member,
			"type": "Alert",
			"link": "",
		}
	)
	make_lms_notification_logs(notification, instructors)


def save_progress_after_quiz(quiz_details, percentage):
	if percentage >= quiz_details.passing_percentage and quiz_details.lesson and quiz_details.course:
		save_progress(quiz_details.lesson, quiz_details.course)
	elif not quiz_details.passing_percentage:
		save_progress(quiz_details.lesson, quiz_details.course)


@frappe.whitelist()
def check_answer(question, type, answers, quiz=None):
	answers = json.loads(answers)
	if type == "Choices":
		result = check_choice_answers(question, answers)
	else:
		result = check_input_answers(question, answers[0])

	# Only reveal per-question correctness when the quiz is explicitly set up
	# for it. Otherwise this endpoint would hand out the answer key over the
	# network for quizzes that are meant to hide it (e.g. graded assessments),
	# regardless of whether the frontend chooses to display the response.
	if not quiz or not frappe.db.get_value("LMS Quiz", quiz, "show_answers"):
		return None

	return result


def check_choice_answers(question, answers):
	fields = ["multiple"]
	is_correct = []
	for num in range(1, 5):
		fields.append(f"option_{cstr(num)}")
		fields.append(f"is_correct_{cstr(num)}")

	question_details = frappe.db.get_value("LMS Question", question, fields, as_dict=1)
	if not question_details:
		return [0, 0, 0, 0]

	cleaned_answers = {cstr(ans).strip() for ans in answers if cstr(ans).strip()}

	for num in range(1, 5):
		opt = cstr(question_details.get(f"option_{num}")).strip()
		if opt and opt in cleaned_answers:
			is_correct.append(question_details.get(f"is_correct_{num}", 0))
		elif question_details.get(f"is_correct_{num}"):
			is_correct.append(2)
		else:
			is_correct.append(0)

	return is_correct


def check_input_answers(question, answer):
	fields = []
	for num in range(1, 5):
		fields.append(f"possibility_{cstr(num)}")

	question_details = frappe.db.get_value("LMS Question", question, fields, as_dict=1)
	for num in range(1, 5):
		current_possibility = question_details[f"possibility_{num}"]
		if current_possibility and fuzz.token_sort_ratio(current_possibility, answer) > 85:
			return 1

	return 0
