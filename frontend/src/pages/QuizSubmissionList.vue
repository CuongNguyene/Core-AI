<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
	</header>
	<div v-if="submissions.data?.length" class="py-5 mx-5">
		<div class="text-xl font-semibold mb-5">
			{{ submissions.data[0].quiz_title }}
		</div>
		<ListView
			:columns="quizColumns"
			:rows="submissions.data"
			row-key="name"
			:options="{ showTooltip: false, selectable: false }"
		>
			<ListHeader
				class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
			>
				<ListHeaderItem :item="item" v-for="item in quizColumns">
				</ListHeaderItem>
			</ListHeader>
			<ListRows>
				<router-link
					v-for="row in submissions.data"
					:to="{
						name: 'QuizSubmission',
						params: {
							submission: row.name,
						},
					}"
				>
					<ListRow :row="row" />
				</router-link>
			</ListRows>
		</ListView>
		<div class="flex justify-center my-5">
			<Button v-if="submissions.hasNextPage" @click="submissions.next()">
				{{ __('quiz.submission.loadMore') }}
			</Button>
		</div>
	</div>
	<EmptyState v-else />
</template>
<script setup>
import {
	createListResource,
	Breadcrumbs,
	Button,
	ListView,
	ListRow,
	ListRows,
	ListHeader,
	ListHeaderItem,
	usePageMeta,
} from 'frappe-ui'
import { computed, onMounted, inject, watch } from 'vue'
import { sessionStore } from '../stores/session'
import { useRouter } from 'vue-router'
import EmptyState from '@/components/EmptyState.vue'

const { brand } = sessionStore()
const router = useRouter()
const user = inject('$user')

const redirectIfNotAllowed = () => {
	if (user.data && !user.data?.is_instructor && !user.data?.is_moderator)
		window.location.href = '/lms/courses'
}

// user.data can load either before this component mounts (checked in
// onMounted below) or asynchronously after (caught by this watcher) -
// a plain onMounted check alone misses the latter case.
watch(user, redirectIfNotAllowed)

onMounted(redirectIfNotAllowed)

const props = defineProps({
	quizID: {
		type: String,
		required: true,
	},
})

const submissions = createListResource({
	doctype: 'LMS Quiz Submission',
	filters: {
		quiz: props.quizID,
	},
	fields: ['name', 'member_name', 'score', 'percentage', 'quiz_title'],
	orderBy: 'creation desc',
	auto: true,
})

const quizColumns = computed(() => {
	return [
		{
			label: __('quiz.submission.member'),
			key: 'member_name',
			width: 1,
		},
		{
			label: __('quiz.submission.score'),
			key: 'score',
			width: 1,
			align: 'center',
		},
		{
			label: __('quiz.submission.percentage'),
			key: 'percentage',
			width: 1,
			align: 'center',
		},
	]
})

const breadcrumbs = computed(() => {
	return [
		{
			label: __('quiz.builder.quizzes'),
			route: { name: 'Quizzes' },
		},
		{
			label: submissions.data?.[0]?.quiz_title || __('quiz.builder.quiz'),
			route: { name: 'QuizForm', params: { quizID: props.quizID } },
		},
		{
			label: __('quiz.submission.submissions'),
		},
	]
})

usePageMeta(() => {
	return {
		title: __('quiz.submission.quizSubmissions'),
		icon: brand.favicon,
	}
})
</script>
