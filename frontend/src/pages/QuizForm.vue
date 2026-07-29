<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<div v-if="!readOnlyMode" class="space-x-2">
			<Badge v-if="quizDetails.isDirty" theme="orange">
				{{ __('quiz.builder.notSaved') }}
			</Badge>
			<Button v-if="quizDetails.doc?.name" @click="testQuiz()">
				<template #prefix>
					<ListChecks class="size-4 stroke-1.5" />
				</template>
				{{ __('quiz.builder.testQuiz') }}
			</Button>
			<router-link
				v-if="quizDetails.doc?.name"
				:to="{
					name: 'QuizSubmissionList',
					params: {
						quizID: quizDetails.doc.name,
					},
				}"
			>
				<Button>
					<template #prefix>
						<ClipboardList class="size-4 stroke-1.5" />
					</template>
					{{ __('quiz.builder.checkSubmissions') }}
				</Button>
			</router-link>
			<Button variant="solid" @click="submitQuiz()">
				{{ __('quiz.builder.save') }}
			</Button>
		</div>
	</header>
	<div v-if="quizDetails.doc" class="py-5">
		<div class="px-20 pb-5 space-y-5 border-b mb-5">
			<div class="text-lg text-ink-gray-9 font-semibold mb-4">
				{{ __('quiz.builder.details') }}
			</div>
			<div class="grid grid-cols-2 gap-5">
				<div class="space-y-5">
					<FormControl
						v-model="quizDetails.doc.title"
						:label="__('quiz.builder.title')"
						:required="true"
					/>
					<FormControl
						type="number"
						v-model="quizDetails.doc.max_attempts"
						:label="__('quiz.builder.maximumAttempts')"
					/>
					<FormControl
						type="number"
						v-model="quizDetails.doc.duration"
						:label="__('quiz.builder.durationMinutes')"
					/>
				</div>
				<div class="space-y-5">
					<FormControl
						v-model="quizDetails.doc.total_marks"
						:label="__('quiz.builder.totalMarks')"
						disabled
					/>
					<FormControl
						type="number"
						:min="0"
						:max="100"
						v-model="quizDetails.doc.passing_percentage"
						:label="__('quiz.builder.passingPercentage')"
						:required="true"
					/>
				</div>
			</div>
		</div>
		<div class="px-20 pb-5 space-y-5 border-b mb-5">
			<div class="text-lg text-ink-gray-9 font-semibold mb-4">
				{{ __('quiz.builder.settings') }}
			</div>
			<div class="grid grid-cols-3 gap-5">
				<div class="flex flex-col space-y-10">
					<FormControl
						v-model="quizDetails.doc.show_answers"
						type="checkbox"
						:label="__('quiz.builder.showAnswers')"
					/>
					<FormControl
						v-model="quizDetails.doc.show_submission_history"
						type="checkbox"
						:label="__('quiz.builder.showSubmissionHistory')"
					/>
				</div>
				<div class="flex flex-col space-y-5">
					<FormControl
						v-model="quizDetails.doc.shuffle_questions"
						type="checkbox"
						:label="__('quiz.builder.shuffleQuestions')"
					/>
					<FormControl
						v-if="quizDetails.doc.shuffle_questions"
						v-model="quizDetails.doc.limit_questions_to"
						:label="__('quiz.builder.limitQuestionsTo')"
					/>
				</div>
				<div class="flex flex-col space-y-5">
					<FormControl
						v-model="quizDetails.doc.enable_negative_marking"
						type="checkbox"
						:label="__('quiz.builder.enableNegativeMarking')"
					/>
					<FormControl
						v-if="quizDetails.doc.enable_negative_marking"
						v-model="quizDetails.doc.marks_to_cut"
						:label="__('quiz.builder.marksToDeduct')"
					/>
				</div>
			</div>
		</div>

		<div v-if="!isNew" class="px-20 pb-5 space-y-5 mb-5">
			<div class="flex items-center justify-between mb-4">
				<div class="text-lg font-semibold text-ink-gray-9">
					{{ __('quiz.builder.questions') }}
				</div>
				<Button v-if="!readOnlyMode" @click="openQuestionModal()">
					<template #prefix>
						<Plus class="w-4 h-4" />
					</template>
					{{ __('quiz.builder.newQuestion') }}
				</Button>
			</div>
			<ListView
				v-if="questions.length"
				:columns="questionColumns"
				:rows="questions"
				row-key="name"
				:options="{
					showTooltip: false,
				}"
			>
				<ListHeader
					class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
				>
					<ListHeaderItem :item="item" v-for="item in questionColumns" />
				</ListHeader>
				<ListRows>
					<ListRow
						:row="row"
						v-slot="{ idx, column, item }"
						v-for="row in questions"
						@click="openQuestionModal(row)"
						class="cursor-pointer"
					>
						<ListRowItem :item="item">
							<div
								v-if="column.key == 'question_detail'"
								class="text-xs truncate h-4"
								v-html="item"
							></div>
							<div v-else class="text-xs">
								{{ item }}
							</div>
						</ListRowItem>
					</ListRow>
				</ListRows>
				<ListSelectBanner>
					<template #actions="{ unselectAll, selections }">
						<div class="flex gap-2">
							<Button
								variant="ghost"
								@click="deleteQuestions(selections, unselectAll)"
							>
								<Trash2 class="h-4 w-4 stroke-1.5" />
							</Button>
						</div>
					</template>
				</ListSelectBanner>
			</ListView>
			<div v-else class="text-ink-gray-6 text-sm">
				{{ __('quiz.builder.noQuestionsAdded') }}
			</div>
		</div>
	</div>

	<Question
		v-model="showQuestionModal"
		:questionDetail="currentQuestion"
		v-model:quiz="quizDetails"
		:title="
			currentQuestion.question
				? __('quiz.editQuestion')
				: __('quiz.addNewQuestion')
		"
	/>
</template>
<script setup>
import {
	Breadcrumbs,
	createResource,
	FormControl,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	ListRowItem,
	ListSelectBanner,
	Button,
	usePageMeta,
	toast,
	createDocumentResource,
	Badge,
} from 'frappe-ui'
import {
	computed,
	reactive,
	ref,
	onMounted,
	inject,
	onBeforeUnmount,
	watch,
} from 'vue'
import { sessionStore } from '../stores/session'
import { ClipboardList, ListChecks, Plus, Trash2 } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import Question from '@/components/Modals/Question.vue'

const { brand } = sessionStore()
const showQuestionModal = ref(false)
const currentQuestion = reactive({
	question: '',
	marks: 0,
	name: '',
})
const user = inject('$user')
const router = useRouter()
const readOnlyMode = window.read_only_mode

const props = defineProps({
	quizID: {
		type: String,
		required: true,
	},
})

const questions = ref([])

const isNew = computed(() => props.quizID === 'new')

const getBlankQuiz = () => ({
	title: '',
	max_attempts: 0,
	duration: '',
	total_marks: 0,
	passing_percentage: 0,
	show_answers: 0,
	show_submission_history: 0,
	shuffle_questions: 0,
	limit_questions_to: 0,
	enable_negative_marking: 0,
	marks_to_cut: 0,
	questions: [],
})

onMounted(() => {
	if (
		props.quizID == 'new' &&
		!user.data?.is_moderator &&
		!user.data?.is_instructor
	) {
		router.push({ name: 'Courses' })
	}
	if (props.quizID !== 'new') {
		quizDetails.reload()
	} else {
		quizDetails.doc = getBlankQuiz()
	}
	window.addEventListener('keydown', keyboardShortcut)
})

const keyboardShortcut = (e) => {
	if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
		submitQuiz()
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
})

watch(
	() => props.quizID !== 'new',
	(newVal) => {
		if (newVal) {
			quizDetails.reload()
		}
	}
)

const quizDetails = createDocumentResource({
	doctype: 'LMS Quiz',
	name: props.quizID,
	auto: false,
	onSuccess(doc) {
		if (doc.questions && doc.questions.length > 0) {
			questions.value = doc.questions.map((question) => question)
		}
	},
})

const newQuizResource = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'LMS Quiz',
				...values,
			},
		}
	},
})

const createQuiz = () => {
	newQuizResource.submit(
		{
			...quizDetails.doc,
			total_marks: calculateTotalMarks(),
		},
		{
			onSuccess(data) {
				quizDetails.name = data.name
				quizDetails.doc = data
				toast.success(__('quiz.builder.createdSuccess'))
				router.push({
					name: 'QuizForm',
					params: { quizID: data.name },
				})
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const submitQuiz = () => {
	if (isNew.value) {
		createQuiz()
		return
	}

	quizDetails.setValue.submit(
		{
			...quizDetails.doc,
			total_marks: calculateTotalMarks(),
		},
		{
			onSuccess(data) {
				quizDetails.doc.total_marks = data.total_marks
				toast.success(__('quiz.builder.updatedSuccess'))
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const testQuiz = () => {
	if (!quizDetails.doc?.questions?.length) {
		toast.warning(
			__('quiz.builder.addQuestionBeforeTest')
		)
		return
	}

	router.push({
		name: 'QuizPage',
		params: {
			quizID: quizDetails.doc.name,
		},
	})
}

const calculateTotalMarks = () => {
	let totalMarks = 0
	if (
		quizDetails.doc?.limit_questions_to &&
		quizDetails.doc?.questions.length > 0
	)
		return (
			quizDetails.doc.questions[0].marks * quizDetails.doc.limit_questions_to
		)

	quizDetails.doc?.questions.forEach((question) => {
		totalMarks += question.marks
	})
	return totalMarks
}

const questionColumns = computed(() => {
	return [
		{
			label: __('quiz.builder.id'),
			key: 'question',
			width: '10rem',
		},
		{
			label: __('quiz.builder.question'),
			key: 'question_detail',
			width: '40rem',
		},
		{
			label: __('quiz.builder.marks'),
			key: 'marks',
			width: '5rem',
		},
	]
})

const openQuestionModal = (question = null) => {
	if (question) {
		currentQuestion.question = question.question
		currentQuestion.marks = question.marks
		currentQuestion.name = question.name
	} else {
		currentQuestion.question = ''
		currentQuestion.marks = 0
		currentQuestion.name = ''
	}
	showQuestionModal.value = true
}

const deleteQuestionResource = createResource({
	url: 'lms.lms.api.delete_documents',
	makeParams(values) {
		return {
			doctype: 'LMS Quiz Question',
			documents: values.questions,
		}
	},
})

const deleteQuestions = (selections, unselectAll) => {
	deleteQuestionResource.submit(
		{
			questions: Array.from(selections),
		},
		{
			onSuccess() {
				toast.success(__('quiz.builder.questionsDeletedSuccess'))
				quizDetails.reload()
				unselectAll()
			},
		}
	)
}

const breadcrumbs = computed(() => {
	let crumbs = [
		{
			label: __('quiz.builder.quizzes'),
			route: {
				name: 'Quizzes',
			},
		},
	]

	crumbs.push({
		label: props.quizID == 'new' ? __('quiz.builder.newQuiz') : quizDetails.doc?.title,
		route: { name: 'QuizForm', params: { quizID: props.quizID } },
	})
	return crumbs
})

usePageMeta(() => {
	return {
		title: props.quizID == 'new' ? __('quiz.builder.newQuiz') : quizDetails.doc?.title,
		icon: brand.favicon,
	}
})
</script>
