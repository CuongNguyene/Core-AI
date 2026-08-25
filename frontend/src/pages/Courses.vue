<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b border-outline-gray-2 bg-surface-white/90 backdrop-blur-md px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<router-link
			v-if="canCreateCourse()"
			:to="{
				name: 'CourseForm',
				params: { courseName: 'new' },
			}"
		>
			<Button variant="solid">
				<template #prefix>
					<Plus class="h-4 w-4 stroke-1.5" />
				</template>
				{{ __('courses.list.create') }}
			</Button>
		</router-link>
	</header>
	<div class="p-5 pb-10">
		<div class="mb-6 border-b border-outline-gray-2 pb-4">
			<div
				class="flex flex-col lg:flex-row space-y-4 lg:space-y-0 lg:items-end justify-between"
			>
				<div>
					<div
						class="lms-courses__mono mb-1 text-[11px] uppercase tracking-[0.14em] text-ink-gray-5"
					>
						{{ __('courses.list.courses') }}
					</div>
					<div class="lms-courses__serif text-[1.75rem] leading-none text-ink-gray-9">
						{{ __('courses.list.allCourses') }}
					</div>
				</div>
				<div
					class="flex flex-col space-y-3 lg:space-y-0 lg:flex-row lg:items-center lg:space-x-4"
				>
					<TabButtons :buttons="courseTabs" v-model="currentTab" class="w-fit" />

				<div class="grid grid-cols-2 gap-2">
					<FormControl
						v-model="title"
						:placeholder="__('courses.list.searchByTitle')"
						type="text"
						class="w-full lg:min-w-0 lg:w-32 xl:w-40"
						@input="updateCourses()"
					/>
					<div class="w-full lg:min-w-0 lg:w-32 xl:w-40">
						<Link
							doctype="LMS Category"
							:value="currentCategory"
							:placeholder="__('courses.list.category')"
							@change="(val) => { currentCategory = val; updateCourses() }"
						/>
					</div>
				</div>

				<FormControl
					v-model="certification"
					:label="__('courses.list.certification')"
					type="checkbox"
					@change="updateCourses()"
				/>
			</div>
		</div>
	</div>
		<div
			v-if="courses.list.loading && !courses.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-8"
		>
			<CardSkeleton v-for="i in 8" :key="i" />
		</div>
		<div
			v-else-if="courses.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-8"
		>
			<router-link
				v-for="course in courses.data"
				:to="{ name: 'CourseDetail', params: { courseName: course.name } }"
			>
				<CourseCard :course="course" />
			</router-link>
		</div>
		<EmptyState v-else type="Courses" />
		<div
			v-if="!courses.list.loading && courses.hasNextPage"
			class="flex justify-center mt-5"
		>
			<Button @click="courses.next()">
				{{ __('courses.list.loadMore') }}
			</Button>
		</div>
	</div>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	call,
	createListResource,
	FormControl,
	TabButtons,
	usePageMeta,
} from 'frappe-ui'
import Link from '@/components/Controls/Link.vue'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { Plus } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import { canCreateCourse } from '@/utils'
import CourseCard from '@/components/CourseCard.vue'
import CardSkeleton from '@/components/CardSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import router from '../router'

const user = inject('$user')
const dayjs = inject('$dayjs')
const start = ref(0)
const pageLength = ref(30)
const currentCategory = ref(null)
const title = ref('')
const certification = ref(false)
const filters = ref({})
const currentTab = ref('All')
const { brand } = sessionStore()
const courseCount = ref(0)

onMounted(() => {
	setFiltersFromQuery()
	fetchCourses()
	if (user.data?.is_system_manager) getCourseCount()
})

const setFiltersFromQuery = () => {
	let queries = new URLSearchParams(location.search)
	title.value = queries.get('title') || ''
	currentCategory.value = queries.get('category') || null
	certification.value = queries.get('certification') || false
}

const courses = createListResource({
	doctype: 'LMS Course',
	url: 'lms.lms.utils.get_courses',
	cache: ['courses', user.data?.name],
	pageLength: pageLength.value,
	start: start.value,
	auto: false,
})

const isPersonaCaptured = async () => {
	let persona = await call('frappe.client.get_single_value', {
		doctype: 'LMS Settings',
		field: 'persona_captured',
	})
	return persona
}

const identifyUserPersona = async () => {
	if (user.data?.is_system_manager && !user.data?.developer_mode) {
		let personaCaptured = await isPersonaCaptured()
		if (personaCaptured) return
		if (!courseCount.value) {
			router.push({
				name: 'PersonaForm',
			})
		}
	}
}

const getCourseCount = () => {
	if (!user.data) return

	call('frappe.client.get_count', {
		doctype: 'LMS Course',
	}).then((data) => {
		courseCount.value = data
		identifyUserPersona()
	})
}

const fetchCourses = () => {
	updateFilters()
	courses.update({
		filters: filters.value,
	})
	courses.reload()
}

const updateCourses = useDebounceFn(fetchCourses, 200)

const updateFilters = () => {
	updateCategoryFilter()
	updateTitleFilter()
	updateCertificationFilter()
	updateTabFilter()
	updateStudentFilter()
	setQueryParams()
}

const updateCategoryFilter = () => {
	if (currentCategory.value) {
		filters.value['category'] = currentCategory.value
	} else {
		delete filters.value['category']
	}
}

const updateTitleFilter = () => {
	if (title.value) {
		filters.value['title'] = ['like', `%${title.value}%`]
	} else {
		delete filters.value['title']
	}
}

const updateCertificationFilter = () => {
	if (certification.value) {
		filters.value['certification'] = 1
	} else {
		delete filters.value['certification']
	}
}

const updateTabFilter = () => {
	delete filters.value['live']
	delete filters.value['created']
	delete filters.value['published_on']
	delete filters.value['upcoming']

	if (currentTab.value == 'Enrolled' && user.data?.is_student) {
		filters.value['enrolled'] = 1
		delete filters.value['bookmarked']
		delete filters.value['published']
	} else if (currentTab.value == 'Bookmarked' && user.data) {
		filters.value['bookmarked'] = 1
		delete filters.value['enrolled']
		delete filters.value['published']
	} else {
		delete filters.value['published']
		delete filters.value['enrolled']
		delete filters.value['bookmarked']

		if (currentTab.value == 'Live') {
			filters.value['published'] = 1
			filters.value['upcoming'] = 0
			filters.value['live'] = 1
		} else if (currentTab.value == 'Upcoming') {
			filters.value['upcoming'] = 1
		} else if (currentTab.value == 'New') {
			filters.value['published'] = 1
			filters.value['published_on'] = [
				'>=',
				dayjs().add(-3, 'month').format('YYYY-MM-DD'),
			]
		} else if (currentTab.value == 'Created') {
			filters.value['created'] = 1
		} else if (currentTab.value == 'Unpublished') {
			filters.value['published'] = 0
		}
	}
}

const updateStudentFilter = () => {
	if (
		!user.data ||
		(user.data?.is_student &&
			currentTab.value != 'Enrolled' &&
			currentTab.value != 'Bookmarked')
	) {
		filters.value['published'] = 1
	}
}

const setQueryParams = () => {
	let queries = new URLSearchParams(location.search)
	let filterKeys = {
		title: title.value,
		category: currentCategory.value,
		certification: certification.value,
	}

	Object.keys(filterKeys).forEach((key) => {
		if (filterKeys[key]) {
			queries.set(key, filterKeys[key])
		} else {
			queries.delete(key)
		}
	})

	let queryString = ''
	if (queries.toString()) {
		queryString = `?${queries.toString()}`
	}

	history.replaceState({}, '', `${location.pathname}${queryString}`)
}

watch(currentTab, () => {
	updateCourses()
})

const courseTabs = computed(() => {
	let tabs = [
		{
			label: __('courses.list.all'),
			value: 'All',
		},
		{
			label: __('courses.list.live'),
			value: 'Live',
		},
		{
			label: __('courses.list.new'),
			value: 'New',
		},
		{
			label: __('courses.list.upcoming'),
			value: 'Upcoming',
		},
	]
	if (
		user.data?.is_moderator ||
		user.data?.is_instructor
	) {
		tabs.push({ label: __('courses.list.created'), value: 'Created' })
		tabs.push({ label: __('courses.list.unpublished'), value: 'Unpublished' })
	} else if (user.data) {
		tabs.push({ label: __('courses.list.enrolled'), value: 'Enrolled' })
	}
	if (user.data) {
		tabs.push({ label: __('courses.list.bookmarked'), value: 'Bookmarked' })
	}
	return tabs
})

const breadcrumbs = computed(() => [
	{
		label: __('courses.list.courses'),
		route: { name: 'Courses' },
	},
])

usePageMeta(() => {
	return {
		title: __('courses.list.courses'),
		icon: brand.favicon,
	}
})
</script>
<style scoped>
.lms-courses__serif {
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

.lms-courses__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}
</style>
