# Copyright (c) 2021, FOSS United and Contributors
# See license.txt

# import frappe
import json
import unittest

import frappe
from frappe.utils import add_to_date, now_datetime

from lms.lms.doctype.lms_quiz.lms_quiz import check_answer, quiz_summary, start_quiz_attempt


class TestLMSQuiz(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		frappe.get_doc({"doctype": "LMS Quiz", "title": "Test Quiz", "passing_percentage": 90}).save(
			ignore_permissions=True
		)

	def test_with_multiple_options(self):
		question = frappe.new_doc("LMS Question")
		question.question = "Question Multiple"
		question.type = "Choices"
		question.option_1 = "Option 1"
		question.is_correct_1 = 1
		question.option_2 = "Option 2"
		question.is_correct_2 = 1
		question.save()
		self.assertTrue(question.multiple)

	def test_with_no_correct_option(self):
		question = frappe.new_doc("LMS Question")
		question.question = "Question Multiple"
		question.type = "Choices"
		question.option_1 = "Option 1"
		question.option_2 = "Option 2"
		self.assertRaises(frappe.ValidationError, question.save)

	def test_with_no_possible_answers(self):
		question = frappe.new_doc("LMS Question")
		question.question = "Question Multiple"
		question.type = "User Input"
		self.assertRaises(frappe.ValidationError, question.save)

	def test_tampered_is_correct_is_ignored(self):
		"""quiz_summary must recompute correctness from the DB and not trust a
		client-supplied is_correct value (which can be edited client-side,
		e.g. in localStorage, before the final submission request)."""
		question = frappe.new_doc("LMS Question")
		question.question = "Tamper Test Question"
		question.type = "Choices"
		question.option_1 = "Right Answer"
		question.is_correct_1 = 1
		question.option_2 = "Wrong Answer"
		question.is_correct_2 = 0
		question.save()

		quiz = frappe.get_doc("LMS Quiz", "test-quiz")
		quiz.append("questions", {"question": question.name, "marks": 1})
		quiz.save(ignore_permissions=True)

		results = json.dumps(
			[
				{
					"question_name": question.name,
					"answer": "Wrong Answer",
					"is_correct": [True],
				}
			]
		)

		summary = quiz_summary(quiz.name, results)

		self.assertEqual(summary["score"], 0)
		self.assertFalse(summary["pass"])

		frappe.db.delete("LMS Quiz Submission", {"quiz": quiz.name})

	def make_timed_quiz(self):
		question = frappe.new_doc("LMS Question")
		question.question = "Timer Test Question"
		question.type = "Choices"
		question.option_1 = "Right"
		question.is_correct_1 = 1
		question.option_2 = "Wrong"
		question.save()

		quiz = frappe.new_doc("LMS Quiz")
		quiz.title = "Timer Test Quiz"
		quiz.passing_percentage = 50
		quiz.duration = 1
		quiz.append("questions", {"question": question.name, "marks": 1})
		quiz.save(ignore_permissions=True)

		results = json.dumps(
			[{"question_name": question.name, "answer": "Right", "is_correct": [True]}]
		)
		return quiz, results

	def cleanup_timed_quiz(self, quiz):
		frappe.db.delete("LMS Quiz Submission", {"quiz": quiz.name})
		frappe.db.delete("LMS Quiz Attempt", {"quiz": quiz.name})
		frappe.db.delete("LMS Quiz", quiz.name)

	def test_submission_without_active_attempt_is_rejected(self):
		"""A timed quiz must not be submittable without ever having called
		start_quiz_attempt, otherwise the duration check would be trivially
		bypassed by calling quiz_summary directly."""
		quiz, results = self.make_timed_quiz()
		self.assertRaises(frappe.ValidationError, quiz_summary, quiz.name, results)
		self.cleanup_timed_quiz(quiz)

	def test_submission_within_duration_succeeds(self):
		quiz, results = self.make_timed_quiz()
		start_quiz_attempt(quiz.name)
		summary = quiz_summary(quiz.name, results)
		self.assertEqual(summary["score"], 1)
		self.cleanup_timed_quiz(quiz)

	def test_submission_after_duration_expires_is_rejected(self):
		"""The server-tracked start time (not the client's JS timer) is what
		must gate submission, since the client timer can be paused or bypassed."""
		quiz, results = self.make_timed_quiz()
		start_quiz_attempt(quiz.name)

		attempt_name = frappe.get_all(
			"LMS Quiz Attempt",
			filters={"quiz": quiz.name, "submission": ""},
			order_by="creation desc",
			limit_page_length=1,
			pluck="name",
		)[0]
		frappe.db.set_value(
			"LMS Quiz Attempt", attempt_name, "start_time", add_to_date(now_datetime(), minutes=-5)
		)

		self.assertRaises(frappe.ValidationError, quiz_summary, quiz.name, results)
		self.cleanup_timed_quiz(quiz)

	def test_duplicate_submission_of_same_attempt_is_rejected(self):
		"""A second submission against an already-closed attempt (double-click,
		or a client retry after a timed-out request) must fail cleanly instead
		of either scoring twice or leaking a raw DB error."""
		quiz, results = self.make_timed_quiz()
		start_quiz_attempt(quiz.name)

		first = quiz_summary(quiz.name, results)
		self.assertEqual(first["score"], 1)

		self.assertRaises(frappe.ValidationError, quiz_summary, quiz.name, results)
		self.assertEqual(frappe.db.count("LMS Quiz Submission", {"quiz": quiz.name}), 1)

		self.cleanup_timed_quiz(quiz)

	def test_check_answer_hides_correctness_when_show_answers_disabled(self):
		"""check_answer must not leak the answer key over the network for a
		quiz that isn't configured to reveal answers, regardless of whether
		the frontend chooses to render the response."""
		question = frappe.new_doc("LMS Question")
		question.question = "Leak Test Question"
		question.type = "Choices"
		question.option_1 = "Right"
		question.is_correct_1 = 1
		question.option_2 = "Wrong"
		question.save()

		hidden_quiz = frappe.new_doc("LMS Quiz")
		hidden_quiz.title = "Hidden Answers Quiz"
		hidden_quiz.passing_percentage = 50
		hidden_quiz.show_answers = 0
		hidden_quiz.append("questions", {"question": question.name, "marks": 1})
		hidden_quiz.save(ignore_permissions=True)

		shown_quiz = frappe.new_doc("LMS Quiz")
		shown_quiz.title = "Shown Answers Quiz"
		shown_quiz.passing_percentage = 50
		shown_quiz.show_answers = 1
		shown_quiz.append("questions", {"question": question.name, "marks": 1})
		shown_quiz.save(ignore_permissions=True)

		self.assertIsNone(check_answer(question.name, "Choices", json.dumps(["Right"])))
		self.assertIsNone(
			check_answer(question.name, "Choices", json.dumps(["Right"]), hidden_quiz.name)
		)
		self.assertIsNotNone(
			check_answer(question.name, "Choices", json.dumps(["Right"]), shown_quiz.name)
		)

		frappe.db.delete("LMS Quiz", hidden_quiz.name)
		frappe.db.delete("LMS Quiz", shown_quiz.name)

	@classmethod
	def tearDownClass(cls) -> None:
		frappe.db.delete("LMS Quiz", "test-quiz")
		frappe.db.delete("LMS Question")
