<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-2 bg-surface-white/90 backdrop-blur-md px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
	</header>
	<div v-if="program.data" class="pt-5 px-5 pb-10 w-full">
		<div class="flex items-center space-x-2 border-b border-outline-gray-2 pb-4 mb-5">
			<div class="lms-program-detail__serif text-2xl text-ink-gray-9">
				{{ program.data.name }}
			</div>

			<Badge
				v-if="program.data.progress != null"
				:theme="program.data.progress < 100 ? 'orange' : 'green'"
			>
				<span class="lms-program-detail__mono">
					{{ program.data.progress }}% {{ __('completed') }}
				</span>
			</Badge>

			<Tooltip
				v-if="program.data.enforce_course_order"
				placement="right"
				:text="
					__(
						'programs.detail.courseOrderTooltip'
					)
				"
			>
				<Info class="size-3 cursor-pointer" />
			</Tooltip>
		</div>
		<div
			v-if="program.data.courses?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-5"
		>
			<div
				v-for="course in program.data.courses"
				:key="course.name"
				class="relative group"
				:class="
					(course.eligible && program.data.enforce_course_order) ||
					!program.data.enforce_course_order
						? 'cursor-pointer'
						: 'cursor-default'
				"
			>
				<CourseCard
					:course="course"
					@click="openCourse(course, program.data.enforce_course_order)"
				/>
				<div
					v-if="!course.eligible && program.data.enforce_course_order"
					class="absolute inset-0 flex flex-col items-center justify-center space-y-2 text-ink-white rounded-md invisible group-hover:visible"
					:style="{
						background: 'radial-gradient(circle, darkgray 0%, lightgray 100%)',
					}"
				>
					<LockKeyhole class="size-5" />
					<span class="font-medium text-center leading-5 px-10">
						{{ __('programs.detail.lockedCourseMessage') }}
					</span>
				</div>
			</div>
		</div>
		<EmptyState v-else type="Courses" />
	</div>
</template>
<script setup lang="ts">
import { computed, inject, onMounted } from 'vue'
import {
	Badge,
	Breadcrumbs,
	call,
	createResource,
	Tooltip,
	usePageMeta,
} from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import { LockKeyhole, Info } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import CourseCard from '@/components/CourseCard.vue'
import EmptyState from '@/components/EmptyState.vue'

const { brand } = sessionStore()
const router = useRouter()
const user = inject<any>('$user')

const props = defineProps<{
	programName: string
}>()

onMounted(() => {
	checkIfEnrolled()
})

const checkIfEnrolled = () => {
	call('frappe.client.get_value', {
		doctype: 'LMS Program Member',
		filters: {
			member: user.data.name,
			parent: props.programName,
		},
		parent: 'LMS Program',
		fieldname: 'name',
	}).then((data: { name: string }) => {
		if (data.name) {
			program.reload()
		} else {
			router.push({ name: 'Programs' })
		}
	})
}

const program = createResource({
	url: 'lms.lms.utils.get_program_details',
	params: {
		program_name: props.programName,
	},
})

const openCourse = (course: any, enforceCourseOrder: boolean) => {
	if (!course.eligible && enforceCourseOrder) return
	router.push({
		name: 'CourseDetail',
		params: { courseName: course.name },
	})
}

const breadcrumbs = computed(() => {
	return [
		{ label: __('programs.list.title'), route: { name: 'Programs' } },
		{
			label: props.programName,
			route: {
				name: 'ProgramDetail',
				params: { programName: props.programName },
			},
		},
	]
})

usePageMeta(() => {
	return {
		title: props.programName,
		icon: brand.favicon,
	}
})
</script>
<style scoped>
.lms-program-detail__serif {
	font-family:
		'Source Serif 4',
		Georgia,
		'Iowan Old Style',
		'Palatino Linotype',
		'Book Antiqua',
		Palatino,
		serif;
	letter-spacing: -0.01em;
}

.lms-program-detail__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}
</style>
