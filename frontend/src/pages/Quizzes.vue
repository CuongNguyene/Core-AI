<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<div v-if="!readOnlyMode" class="flex items-center space-x-2">
			<Button @click="showImportModal = true">
				<template #prefix>
					<Upload class="w-4 h-4 stroke-1.5" />
				</template>
				{{ __('quiz.io.import') }}
			</Button>
			<Button
				variant="solid"
				@click="router.push({ name: 'QuizForm', params: { quizID: 'new' } })"
			>
				<template #prefix>
					<Plus class="w-4 h-4" />
				</template>
				{{ __('quiz.list.create') }}
			</Button>
		</div>
	</header>
	<div class="py-5 mx-5">
		<div class="flex items-center justify-between mb-4">
			<div class="text-lg font-semibold text-ink-gray-7">
				{{
					quizzes.data?.length
						? __('quiz.list.nQuizzes').format(quizzes.data.length)
						: __('quiz.list.noQuizzes')
				}}
			</div>
			<FormControl v-model="search" type="text" :placeholder="__('quiz.list.search')">
				<template #prefix>
					<FeatherIcon name="search" class="size-4 text-ink-gray-5" />
				</template>
			</FormControl>
		</div>
		<ListView
			v-if="quizzes.data?.length"
			:columns="quizColumns"
			:rows="quizzes.data"
			row-key="name"
			:options="{ showTooltip: false, selectable: true }"
		>
			<ListHeader
				class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
			>
				<ListHeaderItem :item="item" v-for="item in quizColumns">
					<template #prefix="{ item }">
						<FeatherIcon :name="item.icon?.toString()" class="h-4 w-4" />
					</template>
				</ListHeaderItem>
			</ListHeader>
			<ListRows>
				<router-link
					v-for="row in quizzes.data"
					:to="{
						name: 'QuizForm',
						params: {
							quizID: row.name,
						},
					}"
				>
					<ListRow :row="row">
						<template #default="{ column, item }">
							<ListRowItem :item="row[column.key]" :align="column.align">
								<div v-if="column.key == 'show_answers'">
									<FormControl
										type="checkbox"
										v-model="row[column.key]"
										:disabled="true"
									/>
								</div>
								<div
									v-else-if="column.key == 'modified'"
									class="text-xs text-ink-gray-5"
								>
									{{ row[column.key] }}
								</div>
								<div v-else>
									{{ row[column.key] }}
								</div>
							</ListRowItem>
						</template>
					</ListRow>
				</router-link>
			</ListRows>
			<ListSelectBanner>
				<template #actions="{ unselectAll, selections }">
					<div class="flex gap-2">
						<Button
							variant="ghost"
							@click="deleteQuiz(selections, unselectAll)"
						>
							<FeatherIcon name="trash-2" class="h-4 w-4 stroke-1.5" />
						</Button>
					</div>
				</template>
			</ListSelectBanner>
		</ListView>
		<EmptyState v-else type="Quizzes" />
		<div v-if="quizzes.hasNextPage" class="flex justify-center my-5">
			<Button @click="quizzes.next()">
				{{ __('quiz.list.loadMore') }}
			</Button>
		</div>
	</div>
	<QuizImportModal v-model="showImportModal" @imported="quizzes.reload()" />
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	call,
	createListResource,
	FeatherIcon,
	FormControl,
	ListView,
	ListRows,
	ListRow,
	ListRowItem,
	ListHeader,
	ListHeaderItem,
	ListSelectBanner,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { Plus, Upload } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import EmptyState from '@/components/EmptyState.vue'
import QuizImportModal from '@/components/Modals/QuizImportModal.vue'

const { brand } = sessionStore()
const user = inject('$user')
const dayjs = inject('$dayjs')
const router = useRouter()
const search = ref('')
const readOnlyMode = window.read_only_mode
const quizFilters = ref({})
const showImportModal = ref(false)

const redirectIfNotAllowed = () => {
	if (!user.data) return
	if (!user.data?.is_moderator && !user.data?.is_instructor) {
		window.location.href = '/lms/courses'
	}
}

// user.data can load either before this component mounts (checked in
// onMounted below) or asynchronously after (caught by this watcher) -
// a plain onMounted check alone misses the latter case.
watch(user, redirectIfNotAllowed)

onMounted(redirectIfNotAllowed)

watch(search, () => {
	quizFilters.value['title'] = ['like', `%${search.value}%`]
	quizzes.update({
		filters: quizFilters.value,
	})
	quizzes.reload()
})

const quizzes = createListResource({
	doctype: 'LMS Quiz',
	filters: quizFilters,
	fields: [
		'name',
		'title',
		'passing_percentage',
		'total_marks',
		'show_answers',
		'max_attempts',
		'modified',
	],
	auto: true,
	cache: ['quizzes', user.data?.name],
	orderBy: 'modified desc',
	transform(data) {
		return data.map((quiz) => {
			return {
				...quiz,
				modified: dayjs(quiz.modified).fromNow(),
			}
		})
	},
})

watch(
	user,
	() => {
		if (user.data && !user.data?.is_moderator && user.data?.is_instructor) {
			quizFilters.value['owner'] = user.data?.name
			quizzes.update({ filters: quizFilters.value })
			quizzes.reload()
		}
	},
	{ immediate: true }
)

const deleteQuiz = async (selections, unselectAll) => {
	try {
		await Promise.all(
			Array.from(selections).map((quizName) =>
				call('lms.lms.api.delete_quiz', { quiz: quizName })
			)
		)
		toast.success(__('quiz.list.deletedSuccess'))
	} catch (err) {
		toast.error(err.messages?.[0] || err)
	}
	unselectAll()
	quizzes.reload()
}

const quizColumns = computed(() => {
	return [
		{
			label: __('quiz.builder.title'),
			key: 'title',
			width: 2,
			icon: 'file-text',
		},
		{
			label: __('quiz.builder.totalMarks'),
			key: 'total_marks',
			width: 1,
			align: 'center',
			icon: 'hash',
		},
		{
			label: __('quiz.builder.passingPercentage'),
			key: 'passing_percentage',
			width: 1,
			align: 'center',
			icon: 'percent',
		},
		{
			label: __('quiz.list.maxAttempts'),
			key: 'max_attempts',
			width: 1,
			align: 'center',
			icon: 'repeat',
		},
		{
			label: __('quiz.builder.showAnswers'),
			key: 'show_answers',
			width: 1,
			align: 'center',
			icon: 'eye',
		},
		{
			label: __('quiz.list.modified'),
			key: 'modified',
			width: 1,
			align: 'center',
			icon: 'clock',
		},
	]
})

const breadcrumbs = computed(() => {
	return [
		{
			label: __('quiz.builder.quizzes'),
			route: {
				name: 'Quizzes',
			},
		},
	]
})

usePageMeta(() => {
	return {
		title: __('quiz.builder.quizzes'),
		icon: brand.favicon,
	}
})
</script>
