<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b border-outline-gray-2 bg-surface-white/90 backdrop-blur-md px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
	</header>
	<div class="p-5 pb-10">
		<div class="mb-6 border-b border-outline-gray-2 pb-4">
			<div
				class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"
			>
				<div>
					<div
						class="lms-my-learning__mono mb-1 text-[11px] uppercase tracking-[0.14em] text-ink-gray-5"
					>
						Learning operations
					</div>
					<h1
						class="lms-my-learning__serif text-[1.75rem] leading-none text-ink-gray-9"
					>
						{{ __('My Learning') }}
					</h1>
					<p class="mt-2 text-sm text-ink-gray-6">
						{{ __('Your assigned learning, deadlines, and progress.') }}
					</p>
				</div>
				<TabButtons v-model="currentTab" :buttons="tabs" class="w-fit" />
			</div>
		</div>

		<div
			v-if="myLearning.loading"
			class="grid grid-cols-1 gap-4 lg:grid-cols-2"
		>
			<CardSkeleton v-for="index in 4" :key="index" />
		</div>
		<div
			v-else-if="assignments.length"
			class="grid grid-cols-1 gap-4 lg:grid-cols-2"
		>
			<article
				v-for="assignment in assignments"
				:key="assignment.name"
				class="rounded-md border border-outline-gray-2 bg-surface-white p-5"
			>
				<div class="flex items-start justify-between gap-4">
					<div>
						<div
							class="lms-my-learning__mono text-[10px] uppercase tracking-[0.12em] text-ink-gray-5"
						>
							{{ assignment.target_type }} ·
							{{ assignment.mandatory ? __('Mandatory') : __('Optional') }}
						</div>
						<h2
							class="lms-my-learning__serif mt-1 text-xl leading-tight text-ink-gray-9"
						>
							{{ assignment.target_title }}
						</h2>
					</div>
					<span
						class="shrink-0 rounded-full border px-2 py-1 text-xs"
						:class="statusClass(assignment.status)"
					>
						{{ assignment.status }}
					</span>
				</div>

				<p
					v-if="assignment.note"
					class="mt-3 text-sm leading-6 text-ink-gray-6"
				>
					{{ assignment.note }}
				</p>

				<div class="mt-4">
					<div
						class="mb-2 flex items-center justify-between text-sm text-ink-gray-6"
					>
						<span>{{ __('Progress') }}</span>
						<span>{{ assignment.progress }}%</span>
					</div>
					<ProgressBar
						:progress="assignment.progress"
						size="md"
						:completionColor="true"
					/>
				</div>

				<div class="mt-4 space-y-2 text-sm text-ink-gray-6">
					<div v-if="assignment.due_at" class="flex items-start gap-2">
						<CalendarClock
							class="mt-0.5 h-4 w-4 shrink-0 stroke-1.5"
							:class="deadlineMeta(assignment).iconClass"
						/>
						<div class="flex flex-col gap-0.5">
							<span
								>{{ __('Completion deadline') }}:
								{{ formatDate(assignment.due_at) }}</span
							>
							<span
								class="text-xs font-medium"
								:class="deadlineMeta(assignment).textClass"
							>
								{{ deadlineMeta(assignment).label }}
							</span>
						</div>
					</div>
					<div v-else class="flex items-center gap-2">
						<CalendarClock class="h-4 w-4 shrink-0 stroke-1.5" />
						<span>{{ __('No completion deadline') }}</span>
					</div>
					<div
						v-if="assignment.last_activity_at"
						class="flex items-center gap-2"
					>
						<History class="h-4 w-4 shrink-0 stroke-1.5" />
						<span
							>{{ __('Last activity') }}:
							{{ formatDate(assignment.last_activity_at) }}</span
						>
					</div>
					<div
						v-if="assignment.completed_late"
						class="flex items-center gap-2 text-ink-amber-3"
					>
						<CircleAlert class="h-4 w-4 shrink-0 stroke-1.5" />
						<span>{{ __('Completed after the deadline') }}</span>
					</div>
				</div>

				<div
					v-if="assignment.items.length"
					class="mt-4 border-t border-outline-gray-2 pt-3"
				>
					<div
						class="lms-my-learning__mono mb-2 text-[10px] uppercase tracking-[0.12em] text-ink-gray-5"
					>
						{{ __('Courses') }}
					</div>
					<div
						v-for="item in assignment.items"
						:key="item.course"
						class="flex items-center justify-between gap-3 py-1.5"
					>
						<span class="min-w-0 truncate text-sm text-ink-gray-8">{{
							item.course_title
						}}</span>
						<span class="shrink-0 text-xs text-ink-gray-5"
							>{{ item.progress }}%</span
						>
					</div>
				</div>

				<div class="mt-5 flex justify-end">
					<Button variant="solid" @click="continueLearning(assignment)">
						{{ __('Continue learning') }}
					</Button>
				</div>
			</article>
		</div>
		<div
			v-else
			class="rounded-md border border-dashed border-outline-gray-2 bg-surface-gray-1 px-5 py-12 text-center"
		>
			<div class="lms-my-learning__serif text-xl text-ink-gray-9">
				{{ __('No learning in this view.') }}
			</div>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{
					__('Assigned learning will appear here when it is available to you.')
				}}
			</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
	Breadcrumbs,
	Button,
	createResource,
	TabButtons,
	usePageMeta,
} from 'frappe-ui'
import { CalendarClock, CircleAlert, History } from 'lucide-vue-next'
import CardSkeleton from '@/components/CardSkeleton.vue'
import ProgressBar from '@/components/ProgressBar.vue'

const router = useRouter()
const dayjs = inject<any>('$dayjs')
const currentTab = ref('All')

const myLearning = createResource({
	url: 'lms.lms.learning_assignment_api.get_my_learning',
	auto: true,
})

const tabs = computed(() => [
	{ label: `${__('All')} (${allAssignments.value.length})`, value: 'All' },
	{
		label: `${__('Assigned')} (${myLearning.data?.summary?.Assigned || 0})`,
		value: 'Assigned',
	},
	{
		label: `${__('In Progress')} (${myLearning.data?.summary?.['In Progress'] || 0})`,
		value: 'In Progress',
	},
	{
		label: `${__('Overdue')} (${myLearning.data?.summary?.Overdue || 0})`,
		value: 'Overdue',
	},
	{
		label: `${__('Completed')} (${myLearning.data?.summary?.Completed || 0})`,
		value: 'Completed',
	},
])

const visibleStatuses = ['Assigned', 'In Progress', 'Overdue', 'Completed']
const allAssignments = computed(() =>
	visibleStatuses.flatMap((status) => myLearning.data?.groups?.[status] || []),
)
const assignments = computed(() =>
	currentTab.value === 'All'
		? allAssignments.value
		: myLearning.data?.groups?.[currentTab.value] || [],
)

const breadcrumbs = computed(() => [
	{ label: __('My Learning'), route: { name: 'MyLearning' } },
])

const formatDate = (value: string) => dayjs?.(value).format('LLL') || value

const deadlineMeta = (assignment: any) => {
	if (!assignment.due_at || !dayjs) {
		return {
			label: __('No completion deadline'),
			textClass: 'text-ink-gray-6',
			iconClass: 'text-ink-gray-6',
		}
	}
	const remainingHours = dayjs(assignment.due_at).diff(dayjs(), 'hour', true)
	const overdueDays = Math.max(1, Math.ceil(Math.abs(remainingHours) / 24))
	const remainingDays = Math.max(1, Math.ceil(remainingHours / 24))
	if (assignment.completed_late) {
		return {
			label: __('Completed after the deadline'),
			textClass: 'text-ink-amber-3',
			iconClass: 'text-ink-amber-3',
		}
	}
	if (assignment.status === 'Completed') {
		return {
			label: __('Completed before the deadline'),
			textClass: 'text-ink-green-3',
			iconClass: 'text-ink-green-3',
		}
	}
	if (remainingHours < 0) {
		return {
			label: `${__('Overdue by')} ${overdueDays} ${__('day(s)')}`,
			textClass: 'text-ink-red-3',
			iconClass: 'text-ink-red-3',
		}
	}
	if (remainingHours < 24) {
		return {
			label: __('Due within 24 hours'),
			textClass: 'text-ink-amber-3',
			iconClass: 'text-ink-amber-3',
		}
	}
	if (remainingDays <= 3) {
		return {
			label: `${remainingDays} ${__('day(s) remaining')}`,
			textClass: 'text-ink-amber-3',
			iconClass: 'text-ink-amber-3',
		}
	}
	return {
		label: `${remainingDays} ${__('day(s) remaining')}`,
		textClass: 'text-ink-green-3',
		iconClass: 'text-ink-green-3',
	}
}

const statusClass = (status: string) => {
	if (status === 'Overdue')
		return 'border-outline-amber-2 bg-surface-amber-1 text-ink-amber-3'
	if (status === 'Completed')
		return 'border-outline-green-2 bg-surface-green-1 text-ink-green-3'
	if (status === 'In Progress')
		return 'border-outline-blue-2 bg-surface-blue-1 text-ink-blue-3'
	return 'border-outline-gray-2 bg-surface-gray-1 text-ink-gray-7'
}

const continueLearning = (assignment: any) => {
	const item =
		assignment.items.find((course: any) => course.progress < 100) ||
		assignment.items[0]
	if (!item) return
	if (item.continue_lesson) {
		const [chapterNumber, lessonNumber] = item.continue_lesson.split('-')
		router.push({
			name: 'Lesson',
			params: { courseName: item.course, chapterNumber, lessonNumber },
		})
		return
	}
	router.push({ name: 'CourseDetail', params: { courseName: item.course } })
}

usePageMeta(() => ({ title: __('My Learning') }))
</script>

<style scoped>
.lms-my-learning__serif {
	font-family:
		'Source Serif 4', Georgia, 'Iowan Old Style', 'Palatino Linotype',
		'Book Antiqua', Palatino, serif;
	letter-spacing: -0.01em;
}

.lms-my-learning__mono {
	font-family:
		'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
