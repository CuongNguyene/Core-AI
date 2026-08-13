<template>
	<div v-if="quiz.data" ref="quizRoot">
		<div
			class="bg-surface-blue-2 space-y-2 py-2 px-3 mb-4 rounded-md text-sm text-ink-blue-2 leading-5"
		>
			<div v-if="inVideo">
				{{ __('quiz.take.mustCompleteToContinueVideo') }}
			</div>
			<div class="leading-5">
				{{
					__('quiz.take.consistsOfQuestions').format(questions.length)
				}}
			</div>
			<div v-if="quiz.data?.duration" class="leading-5">
				{{
					__(
						'quiz.take.completeInMinutes'
					).format(quiz.data.duration)
				}}
			</div>
			<div v-if="quiz.data?.duration" class="leading-5">
				{{
					__(
						'quiz.take.autoSubmitOnTimeout'
					)
				}}
			</div>
			<div v-if="quiz.data.passing_percentage" class="leading-relaxed">
				{{
					__(
						'quiz.take.passingRequirement'
					).format(quiz.data.passing_percentage)
				}}
			</div>
			<div v-if="quiz.data.max_attempts" class="leading-5">
				{{
					__('quiz.take.attemptsAllowed').format(
						quiz.data.max_attempts == 1
							? __('quiz.take.oneTime')
							: __('quiz.take.nTimes').format(quiz.data.max_attempts)
					)
				}}
			</div>
			<div v-if="quiz.data.enable_negative_marking" class="leading-5">
				{{
					__(
						'quiz.take.negativeMarking'
					).format(
						quiz.data.marks_to_cut,
						quiz.data.marks_to_cut == 1 ? __('quiz.take.mark') : __('quiz.take.marksPlural')
					)
				}}
			</div>
		</div>

		<IntegrityWarningBanner
			v-if="!hideIntegrityBanner && !isInsideLesson"
			:count="violationCount"
			:studyTime="quiz.data.duration ? (quiz.data.duration * 60) - timer : undefined"
		/>

		<div v-if="quiz.data.duration" class="flex flex-col space-x-1 my-4">
			<div class="mb-2">
				<span class=""> {{ __('quiz.take.time') }}: </span>
				<span class="font-semibold">
					{{ formatTimer(timer) }}
				</span>
			</div>
			<ProgressBar :progress="timerProgress" />
		</div>

		<div v-if="activeQuestion == 0">
			<div class="border text-center p-12 rounded-md">
				<div class="font-semibold text-lg text-ink-gray-9">
					{{ quiz.data.title }}
				</div>
				<div v-if="hasPassedQuiz" class="mt-3 flex items-center justify-center gap-2">
					<Badge theme="green" size="lg" :label="__('Completed / Passed')">
						<template #prefix>
							<CheckCircle class="w-4 h-4 text-ink-green-2 mr-1" />
						</template>
					</Badge>
					<span class="text-sm text-ink-gray-6" v-if="latestAttempt">
						({{ __('Score: {0}%').format(Math.round(latestAttempt.percentage)) }})
					</span>
				</div>
				<div v-if="!questions.length" class="leading-5 text-ink-gray-7 mt-4">
					{{
						__(
							'quiz.take.noQuestionsYet'
						)
					}}
				</div>
				<div class="flex items-center justify-center space-x-2 mt-4">
					<Button
						v-if="
							questions.length &&
							(!quiz.data.max_attempts ||
								attempts.data?.length < quiz.data.max_attempts)
						"
						variant="solid"
						@click="startQuiz"
					>
						<span>
							{{ inVideo ? __('quiz.take.startTheQuiz') : __('quiz.take.start') }}
						</span>
					</Button>
					<Button v-if="inVideo" @click="props.backToVideo()">
						{{ __('quiz.take.resumeVideo') }}
					</Button>
				</div>
				<div
					v-if="
						quiz.data.max_attempts &&
						attempts.data?.length >= quiz.data.max_attempts
					"
					class="leading-5 text-ink-gray-7"
				>
					{{
						__(
							'quiz.take.maxAttemptsExceeded'
						)
					}}
				</div>
			</div>
		</div>
		<div v-else-if="!quizSubmission.data">
			<div v-for="(question, qtidx) in questions">
				<div
					v-if="qtidx == activeQuestion - 1 && questionDetails.data"
					class="border rounded-md p-5"
				>
					<div class="flex justify-between">
						<div class="text-sm text-ink-gray-5">
							<span class="mr-2">
								{{ __('quiz.take.questionN').format(activeQuestion) }}:
							</span>
							<span>
								{{ getInstructions(questionDetails.data) }}
							</span>
						</div>
						<div class="text-ink-gray-9 text-sm font-semibold item-left">
							{{ question.marks }}
							{{ question.marks == 1 ? __('quiz.take.mark') : __('quiz.take.marksPlural') }}
						</div>
					</div>
					<div
						class="text-ink-gray-9 font-semibold mt-2 leading-5"
						v-html="questionDetails.data.question"
					></div>
					<div
						v-if="questionDetails.data.type == 'Choices'"
						v-for="index in questionDetails.data.option_order || [1, 2, 3, 4]"
						:key="index"
					>
						<label
							v-if="questionDetails.data[`option_${index}`]"
							class="flex items-center bg-surface-gray-3 rounded-md p-3 mt-4 w-full cursor-pointer focus:border-blue-600"
						>
							<input
								v-if="!showAnswers.length && !questionDetails.data.multiple"
								type="radio"
								:name="encodeURIComponent(questionDetails.data.question)"
								class="w-3.5 h-3.5 text-ink-gray-9 focus:ring-outline-gray-modals"
								@change="markAnswer(index)"
							/>

							<input
								v-else-if="!showAnswers.length && questionDetails.data.multiple"
								type="checkbox"
								:name="encodeURIComponent(questionDetails.data.question)"
								class="w-3.5 h-3.5 text-ink-gray-9 rounded-sm focus:ring-outline-gray-modals"
								@change="markAnswer(index)"
							/>
							<div
								v-else-if="quiz.data.show_answers"
								v-for="(answer, idx) in showAnswers"
							>
								<div v-if="index - 1 == idx">
									<CheckCircle
										v-if="answer == 1"
										class="w-4 h-4 text-ink-green-2"
									/>
									<MinusCircle
										v-else-if="answer == 2"
										class="w-4 h-4 text-ink-green-2"
									/>
									<XCircle
										v-else-if="answer == 0"
										class="w-4 h-4 text-ink-red-3"
									/>
									<MinusCircle v-else class="w-4 h-4" />
								</div>
							</div>
							<span
								class="ml-2"
								v-html="questionDetails.data[`option_${index}`]"
							>
							</span>
						</label>
						<div
							v-if="questionDetails.data[`explanation_${index}`]"
							class="mt-2 text-xs"
							v-show="showAnswers.length"
						>
							{{ questionDetails.data[`explanation_${index}`] }}
						</div>
					</div>
					<div v-else-if="questionDetails.data.type == 'User Input'">
						<FormControl
							v-model="possibleAnswer"
							type="textarea"
							:disabled="showAnswers.length ? true : false"
							class="my-2"
						/>
						<div v-if="showAnswers.length">
							<Badge v-if="showAnswers[0]" :label="__('quiz.take.correct')" theme="green">
								<template #prefix>
									<CheckCircle class="w-4 h-4 text-ink-green-2 mr-1" />
								</template>
							</Badge>
							<Badge v-else theme="red" :label="__('quiz.take.incorrect')">
								<template #prefix>
									<XCircle class="w-4 h-4 text-ink-red-3 mr-1" />
								</template>
							</Badge>
						</div>
					</div>
					<div v-else>
						<TextEditor
							class="mt-4"
							:content="possibleAnswer"
							@change="(val) => (possibleAnswer = val)"
							:editable="true"
							:fixedMenu="true"
							editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
						/>
					</div>
					<div class="flex items-center justify-between mt-4">
						<div class="text-sm text-ink-gray-5">
							{{
								__('quiz.take.questionNofM').format(
									activeQuestion,
									questions.length
								)
							}}
						</div>
						<Button
							v-if="
								quiz.data.show_answers &&
								!showAnswers.length &&
								questionDetails.data.type != 'Open Ended'
							"
							@click="checkAnswer()"
						>
							<span>
								{{ __('quiz.take.check') }}
							</span>
						</Button>
						<Button
							v-else-if="activeQuestion != questions.length"
							@click="nextQuestion()"
						>
							<span>
								{{ __('quiz.take.next') }}
							</span>
						</Button>
						<Button v-else @click="submitQuiz()">
							<span>
								{{ __('quiz.take.submit') }}
							</span>
						</Button>
					</div>
				</div>
			</div>
		</div>
		<div v-else class="border rounded-md p-20 text-center space-y-2">
			<div class="text-lg font-semibold text-ink-gray-9">
				{{ __('quiz.take.quizSummary') }}
			</div>
			<div
				v-if="quizSubmission.data.is_open_ended"
				class="leading-5 text-ink-gray-7"
			>
				{{
					__(
						'quiz.take.openEndedSubmitted'
					)
				}}
			</div>
			<div v-else>
				{{
					__(
						'quiz.take.resultSummary'
					).format(
						Math.ceil(quizSubmission.data.percentage),
						quizSubmission.data.score,
						quizSubmission.data.score_out_of
					)
				}}
			</div>
			<div class="space-x-2">
				<Button
					@click="resetQuiz()"
					class="mt-2"
					v-if="
						!quiz.data.max_attempts ||
						attempts?.data.length < quiz.data.max_attempts
					"
				>
					<span>
						{{ __('quiz.take.tryAgain') }}
					</span>
				</Button>
				<Button v-if="inVideo" @click="props.backToVideo()">
					{{ __('quiz.take.resumeVideo') }}
				</Button>
			</div>
		</div>
		<div
			v-if="
				quiz.data.show_submission_history &&
				attempts?.data &&
				attempts.data.length > 0
			"
			class="mt-10"
		>
			<ListView
				:columns="getSubmissionColumns()"
				:rows="attempts?.data"
				row-key="name"
				:options="{
					selectable: false,
					showTooltip: false,
					emptyState: { title: __('quiz.take.noSubmissionsFound') },
				}"
			>
			</ListView>
		</div>
	</div>
</template>
<script setup>
import {
	Badge,
	Button,
	call,
	createResource,
	ListView,
	TextEditor,
	FormControl,
	toast,
} from 'frappe-ui'
import { ref, watch, reactive, inject, computed, onBeforeUnmount, onMounted } from 'vue'
import { CheckCircle, XCircle, MinusCircle } from 'lucide-vue-next'
import { timeAgo } from '@/utils'
import { useRouter, useRoute } from 'vue-router'
import ProgressBar from '@/components/ProgressBar.vue'
import IntegrityWarningBanner from '@/components/IntegrityWarningBanner.vue'
import { useVisibilityLog } from '@/composables/useVisibilityLog'
import { useExamGuards } from '@/composables/useExamGuards'

const user = inject('$user')
const route = useRoute()
const isInsideLesson = computed(() => {
	if (route?.query?.fromLesson === '1') return true
	if (typeof window !== 'undefined') {
		const searchParams = new URLSearchParams(window.location.search)
		return searchParams.get('fromLesson') === '1'
	}
	return false
})
const activeQuestion = ref(0)
const currentQuestion = ref('')
const selectedOptions = reactive([0, 0, 0, 0])
const showAnswers = reactive([])
const questions = ref([])
const possibleAnswer = ref(null)
const timer = ref(0)
let timerInterval = null
const violationCount = ref(0)
const quizRoot = ref(null)
let visibilityLog = { start: () => {}, stop: () => {} }
let examGuards = { start: () => {}, stop: () => {} }

onBeforeUnmount(() => {
	visibilityLog.stop()
	examGuards.stop()
})

onMounted(() => {
	if (isInsideLesson.value && props.quizName) {
		examGuards = useExamGuards({
			referenceDoctype: 'LMS Quiz',
			referenceName: props.quizName,
		})
		examGuards.start()
	}
})

const props = defineProps({
	quizName: {
		type: String,
		required: true,
	},
	inVideo: {
		type: Boolean,
		default: false,
	},
	backToVideo: {
		type: Function,
		default: () => {},
	},
	hideIntegrityBanner: {
		type: Boolean,
		default: false,
	},
})

const emit = defineEmits(['violation-count'])

const quiz = createResource({
	url: 'lms.lms.doctype.lms_quiz.lms_quiz.get_quiz',
	makeParams(values) {
		return {
			quiz: props.quizName,
		}
	},
	cache: ['quiz', props.quizName],
	auto: true,
	transform(data) {
		data.duration = parseInt(data.duration)
	},
	onSuccess(data) {
		populateQuestions()
		setupTimer()
	},
})

// The server picks (and, per the quiz's own settings, shuffles/limits) which
// questions this attempt gets — the browser never sees the full question
// bank, only the subset it's allowed to answer right now.
const quizQuestions = createResource({
	url: 'lms.lms.doctype.lms_quiz.lms_quiz.get_quiz_questions',
	makeParams(values) {
		return {
			quiz: props.quizName,
		}
	},
	onSuccess(data) {
		questions.value = data
	},
})

const populateQuestions = () => {
	quizQuestions.reload()
}

const setupTimer = () => {
	if (quiz.data.duration) {
		timer.value = quiz.data.duration * 60
	}
}

const startTimer = () => {
	timerInterval = setInterval(() => {
		timer.value--
		if (timer.value == 0) {
			clearInterval(timerInterval)
			submitQuiz()
		}
	}, 1000)
}

const formatTimer = (seconds) => {
	const hrs = Math.floor(seconds / 3600)
		.toString()
		.padStart(2, '0')
	const mins = Math.floor((seconds % 3600) / 60)
		.toString()
		.padStart(2, '0')
	const secs = (seconds % 60).toString().padStart(2, '0')
	return hrs != '00' ? `${hrs}:${mins}:${secs}` : `${mins}:${secs}`
}

const timerProgress = computed(() => {
	return (timer.value / (quiz.data.duration * 60)) * 100
})

const attempts = createResource({
	url: 'frappe.client.get_list',
	makeParams(values) {
		return {
			doctype: 'LMS Quiz Submission',
			filters: {
				member: user?.data?.name,
				quiz: quiz?.data?.name,
			},
			fields: [
				'name',
				'creation',
				'score',
				'score_out_of',
				'percentage',
				'passing_percentage',
			],
			order_by: 'creation desc',
		}
	},
	transform(data) {
		if (Array.isArray(data)) {
			data.forEach((submission, index) => {
				submission.creation = timeAgo(submission.creation)
				submission.idx = index + 1
			})
		}
	},
})

const latestAttempt = computed(() => attempts.data?.[0])

const hasPassedQuiz = computed(() => {
	if (!attempts.data?.length) return false
	const passing = quiz.data?.passing_percentage || 0
	return attempts.data.some((att) => Number(att.percentage || 0) >= passing)
})

watch(
	() => quiz.data,
	() => {
		if (quiz.data) {
			populateQuestions()
			attempts.reload()
		}
		if (quiz.data && quiz.data.max_attempts) {
			resetQuiz()
		}
	}
)

const quizSubmission = createResource({
	url: 'lms.lms.doctype.lms_quiz.lms_quiz.quiz_summary',
	makeParams(values) {
		return {
			quiz: quiz.data.name,
			results: localStorage.getItem(quiz.data.title),
		}
	},
})

const questionDetails = createResource({
	url: 'lms.lms.utils.get_question_details',
	makeParams(values) {
		return {
			question: currentQuestion.value,
			quiz: quiz.data?.name,
		}
	},
})

watch(activeQuestion, (value) => {
	if (value > 0) {
		const question = questions.value[value - 1]
		if (!question) return
		currentQuestion.value = question.question
		questionDetails.reload()
	}
})

watch(
	() => props.quizName,
	(newName) => {
		if (newName) {
			quiz.reload()
		}
	}
)

const startQuiz = async () => {
	activeQuestion.value = 1
	localStorage.removeItem(quiz.data.title)

	const onLog = (count) => {
		violationCount.value = count || 0
		emit('violation-count', violationCount.value)
	}

	if (quiz.data.duration) {
		const attempt = await call('lms.lms.doctype.lms_quiz.lms_quiz.start_quiz_attempt', {
			quiz: quiz.data.name,
		})
		timer.value = attempt.remaining_seconds
		startTimer()

		visibilityLog.stop()
		visibilityLog = useVisibilityLog({
			referenceDoctype: 'LMS Quiz Attempt',
			referenceName: attempt.name,
			minDurationSec: quiz.data.integrity_violation_threshold_seconds || 2,
			onLog,
		})
		visibilityLog.start()

		examGuards.stop()
		examGuards = useExamGuards({
			referenceDoctype: 'LMS Quiz Attempt',
			referenceName: attempt.name,
			onLog,
		})
		examGuards.start()
	} else {
		examGuards.stop()
		examGuards = useExamGuards({
			referenceDoctype: 'Course Lesson',
			referenceName: quiz.data.name,
			onLog,
		})
		examGuards.start()
	}
}

const markAnswer = (index) => {
	if (!questionDetails.data.multiple)
		selectedOptions.splice(0, selectedOptions.length, ...[0, 0, 0, 0])
	selectedOptions[index - 1] = selectedOptions[index - 1] ? 0 : 1
}

const getAnswers = () => {
	let answers = []
	const type = questionDetails.data.type

	if (type == 'Choices') {
		selectedOptions.forEach((value, index) => {
			if (selectedOptions[index])
				answers.push(questionDetails.data[`option_${index + 1}`])
		})
	} else {
		answers.push(possibleAnswer.value)
	}

	return answers
}

const checkAnswer = () => {
	let answers = getAnswers()
	if (!answers.length) {
		toast.warning(__('quiz.take.selectOptionRequired'))
		return Promise.resolve()
	}

	return new Promise((resolve) => {
		createResource({
			url: 'lms.lms.doctype.lms_quiz.lms_quiz.check_answer',
			params: {
				question: currentQuestion.value,
				type: questionDetails.data.type,
				answers: JSON.stringify(answers),
				quiz: quiz.data.name,
			},
			auto: true,
			onSuccess(data) {
				let type = questionDetails.data.type
				if (data && type == 'Choices') {
					selectedOptions.forEach((option, index) => {
						if (option) {
							showAnswers[index] = option && data[index]
						} else if (data[index] == 2) {
							showAnswers[index] = 2
						} else {
							showAnswers[index] = undefined
						}
					})
				} else if (data) {
					showAnswers.push(data)
				}
				addToLocalStorage()
				if (!quiz.data.show_answers) {
					resetQuestion()
				}
				resolve()
			},
			onError() {
				addToLocalStorage()
				resolve()
			},
		})
	})
}

const addToLocalStorage = () => {
	let quizData = JSON.parse(localStorage.getItem(quiz.data.title))
	let questionData = {
		question_name: currentQuestion.value,
		answer: JSON.stringify(getAnswers()),
		is_correct: showAnswers.filter((answer) => {
			return answer != undefined
		}),
	}

	if (quizData) {
		let existingQuestion = quizData.find(
			(q) => q.question_name == questionData.question_name
		)
		if (!existingQuestion) {
			quizData.push(questionData)
		}
	} else {
		quizData = [questionData]
	}
	localStorage.setItem(quiz.data.title, JSON.stringify(quizData))
}

const nextQuestion = () => {
	if (!quiz.data.show_answers && questionDetails.data?.type != 'Open Ended') {
		checkAnswer()
	} else {
		if (questionDetails.data?.type == 'Open Ended') addToLocalStorage()
		resetQuestion()
	}
}

const resetQuestion = () => {
	if (activeQuestion.value == questions.value.length) return
	activeQuestion.value = activeQuestion.value + 1
	selectedOptions.splice(0, selectedOptions.length, ...[0, 0, 0, 0])
	showAnswers.length = 0
	possibleAnswer.value = null
}

const submitQuiz = async () => {
	if (!quiz.data.show_answers) {
		if (questionDetails.data.type == 'Open Ended') addToLocalStorage()
		else await checkAnswer()
		createSubmission()
		return
	}
	createSubmission()
}

const createSubmission = () => {
	quizSubmission.submit(
		{},
		{
			onSuccess(data) {
				markLessonProgress()
				if (quiz.data && quiz.data.max_attempts) attempts.reload()
				if (quiz.data.duration) clearInterval(timerInterval)
				visibilityLog.stop()
				examGuards.stop()
			},
			onError(err) {
				const errorTitle = err?.message || ''
				if (errorTitle.includes('MaximumAttemptsExceededError')) {
					const errorMessage = err.messages?.[0] || err
					toast.error(__(errorMessage))
					setTimeout(() => {
						window.location.reload()
					}, 3000)
				}
			},
		}
	)
}

const resetQuiz = () => {
	activeQuestion.value = 0
	selectedOptions.splice(0, selectedOptions.length, ...[0, 0, 0, 0])
	showAnswers.length = 0
	quizSubmission.reset()
	populateQuestions()
	setupTimer()
	visibilityLog.stop()
	examGuards.stop()
	violationCount.value = 0
}

const getInstructions = (question) => {
	if (question.type == 'Choices')
		if (question.multiple) return __('quiz.take.chooseAllThatApply')
		else return __('quiz.take.chooseOneAnswer')
	else return __('quiz.take.typeYourAnswer')
}

const markLessonProgress = () => {
	let pathname = window.location.pathname.split('/')
	if (!pathname.includes('courses'))
		pathname = window.parent.location.pathname.split('/')
	if (pathname[2] != 'courses') return
	let lessonIndex = pathname.pop().split('-')

	if (lessonIndex.length == 2) {
		call('lms.lms.api.mark_lesson_progress', {
			course: pathname[3],
			chapter_number: lessonIndex[0],
			lesson_number: lessonIndex[1],
		})
	}
}

const getSubmissionColumns = () => {
	return [
		{
			label: __('quiz.take.no'),
			key: 'idx',
		},
		{
			label: __('quiz.take.date'),
			key: 'creation',
		},
		{
			label: __('quiz.take.score'),
			key: 'score',
			align: 'center',
		},
		{
			label: __('quiz.take.scoreOutOf'),
			key: 'score_out_of',
			align: 'center',
		},
		{
			label: __('quiz.take.percentage'),
			key: 'percentage',
			align: 'center',
		},
	]
}
</script>
<style>
p {
	line-height: 1.5rem;
}
</style>
