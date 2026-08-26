<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-2 bg-surface-white/90 backdrop-blur-md px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs class="h-7" :items="breadcrumbs" />
	</header>
	<div class="p-5">
		<div v-if="certificate.data && Object.keys(certificate.data).length">
			<div class="lms-course-certification__serif text-lg text-ink-gray-9 mb-1">
				{{ __('courses.certification.title') }}
			</div>
			<div class="text-ink-gray-9 text-sm">
				{{
					__('courses.certification.alreadyCertified')
				}}
			</div>
			<div
				class="flex w-fit min-w-60 items-start gap-3 rounded-md border border-outline-gray-2 p-3 mt-5 cursor-pointer hover:bg-surface-gray-1"
				@click="openCertificate(certificate.data)"
			>
				<div
					class="lms-course-certification__seal flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
				>
					<GraduationCap class="h-4 w-4 stroke-2" />
				</div>
				<div class="space-y-1">
					<div class="lms-course-certification__serif text-lg text-ink-gray-9">
						{{ courseTitle }}
					</div>
					<div class="lms-course-certification__mono text-sm text-ink-gray-6">
						{{ __('courses.certification.issuedOn') }}
						{{ dayjs(certificate.data.issue_date).format('L') }}
					</div>
				</div>
			</div>
		</div>
		<div v-else>
			<UpcomingEvaluations v-if="courses.length" :courses="courses" />
		</div>
	</div>
</template>
<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { Breadcrumbs, call, createResource, usePageMeta } from 'frappe-ui'
import { GraduationCap } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { sessionStore } from '../stores/session'
import UpcomingEvaluations from '@/components/UpcomingEvaluations.vue'

const courseTitle = ref(null)
const evaluator = ref(null)
const { brand } = sessionStore()
const courses = ref([])
const user = inject('$user')
const dayjs = inject('$dayjs')
const router = useRouter()

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
})

onMounted(() => {
	fetchEnrollmentDetails()
	fetchCourseDetails()
})

const certificate = createResource({
	url: 'frappe.client.get_value',
	params: {
		doctype: 'LMS Certificate',
		filters: {
			member: user.data?.name,
			course: props.courseName,
		},
		fieldname: ['name', 'template', 'issue_date'],
	},
	cache: [user.data?.name, props.courseName],
})

const fetchEnrollmentDetails = () => {
	call('frappe.client.get_value', {
		doctype: 'LMS Enrollment',
		filters: { member: user.data?.name, course: props.courseName },
		fieldname: ['purchased_certificate'],
	}).then((data) => {
		if (data.purchased_certificate) {
			certificate.reload()
		} else {
			router.push({
				name: 'CourseDetail',
				params: { courseName: props.courseName },
			})
		}
	})
}

const fetchCourseDetails = () => {
	call('frappe.client.get_value', {
		doctype: 'LMS Course',
		filters: { name: props.courseName },
		fieldname: ['title', 'evaluator'],
	}).then((data) => {
		courseTitle.value = data.title
		evaluator.value = data.evaluator
		populateCourses()
	})
}

const populateCourses = () => {
	courses.value = [
		{
			course: props.courseName,
			title: courseTitle.value,
			evaluator: evaluator.value,
		},
	]
}

const openCertificate = (certificate) => {
	window.open(
		`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate&name=${
			certificate.name
		}&format=${encodeURIComponent(certificate.template)}`,
		'_blank'
	)
}

const breadcrumbs = computed(() => [
	{
		label: __('courses.list.courses'),
		route: { name: 'Courses' },
	},
	{
		label: courseTitle.value,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	},
	{
		label: __('courses.certification.title'),
	},
])

usePageMeta(() => {
	return {
		title: courseTitle.value,
		icon: brand.favicon,
	}
})
</script>
<style scoped>
.lms-course-certification__serif {
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

.lms-course-certification__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}

.lms-course-certification__seal {
	background: #efe8d8;
	color: #8a6a22;
}
</style>
