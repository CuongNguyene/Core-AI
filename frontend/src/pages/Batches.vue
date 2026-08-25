<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<router-link
			v-if="canCreateBatch()"
			:to="{
				name: 'BatchForm',
				params: { batchName: 'new' },
			}"
		>
			<Button variant="solid">
				<template #prefix>
					<Plus class="h-4 w-4 stroke-1.5" />
				</template>
				{{ __('batches.list.create') }}
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
						class="lms-batches__mono mb-1 text-[11px] uppercase tracking-[0.14em] text-ink-gray-5"
					>
						{{ __('batches.list.batches') }}
					</div>
					<div class="lms-batches__serif text-[1.75rem] leading-none text-ink-gray-9">
						{{ __('batches.list.allBatches') }}
					</div>
				</div>
				<div
					class="flex flex-col space-y-3 lg:space-y-0 lg:flex-row lg:items-center lg:space-x-4"
				>
					<TabButtons
					v-if="user.data"
					:buttons="batchTabs"
					v-model="currentTab"
					class="w-fit"
				/>
				<div class="grid grid-cols-2 gap-2">
					<FormControl
						v-model="title"
						:placeholder="__('batches.list.searchByTitle')"
						type="text"
						class="min-w-40 lg:min-w-0 lg:w-32 xl:w-40"
						@input="updateBatches()"
					/>
					<div class="min-w-40 lg:min-w-0 lg:w-32 xl:w-40">
						<Link
							doctype="LMS Category"
							:value="currentCategory"
							:placeholder="__('batches.list.category')"
							@change="(val) => { currentCategory = val; updateBatches() }"
						/>
					</div>
				</div>

				<FormControl
					v-model="certification"
					:label="__('batches.list.certification')"
					type="checkbox"
					@change="updateBatches()"
				/>
			</div>
		</div>
	</div>
		<div
			v-if="batches.list.loading && !batches.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5"
		>
			<CardSkeleton v-for="i in 8" :key="i" />
		</div>
		<div
			v-else-if="batches.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5"
		>
			<router-link
				v-for="batch in batches.data"
				:to="{ name: 'BatchDetail', params: { batchName: batch.name } }"
			>
				<BatchCard :batch="batch" />
			</router-link>
		</div>
		<EmptyState v-else type="Batches" />

		<div
			v-if="!batches.list.loading && batches.hasNextPage"
			class="flex justify-center mt-5"
		>
			<Button @click="batches.next()">
				{{ __('batches.list.loadMore') }}
			</Button>
		</div>
	</div>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	createListResource,
	FormControl,
	TabButtons,
	usePageMeta,
} from 'frappe-ui'
import Link from '@/components/Controls/Link.vue'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { Plus } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import BatchCard from '@/components/BatchCard.vue'
import CardSkeleton from '@/components/CardSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const { brand } = sessionStore()
const start = ref(0)
const pageLength = ref(20)
const categories = ref([])
const currentCategory = ref(null)
const title = ref('')
const certification = ref(false)
const filters = ref({})
const is_student = computed(() => user.data?.is_student)
const currentTab = ref('All')
const orderBy = ref('start_date')
const readOnlyMode = window.read_only_mode

onMounted(() => {
	setFiltersFromQuery()
	updateBatches()
	categories.value = [
		{
			label: '',
			value: null,
		},
	]
})

const setFiltersFromQuery = () => {
	let queries = new URLSearchParams(location.search)
	title.value = queries.get('title') || ''
	currentCategory.value = queries.get('category') || null
	certification.value = queries.get('certification') || false
}

const batches = createListResource({
	doctype: 'LMS Batch',
	url: 'lms.lms.utils.get_batches',
	cache: ['batches', user.data?.name],
	pageLength: pageLength.value,
	start: start.value,
	onSuccess(data) {
		let allCategories = data.map((batch) => batch.category)
		allCategories = allCategories.filter(
			(category, index) => allCategories.indexOf(category) === index && category
		)
		if (categories.value.length <= allCategories.length) {
			updateCategories(data)
		}
	},
})

const updateBatches = () => {
	updateFilters()
	batches.update({
		filters: filters.value,
		orderBy: orderBy.value,
	})
	batches.reload()
}

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
	orderBy.value = 'start_date'
	if (!user.data) {
		return
	}
	if (currentTab.value == 'Enrolled' && is_student.value) {
		filters.value['enrolled'] = 1
		delete filters.value['start_date']
		delete filters.value['published']
		orderBy.value = 'start_date desc'
	} else if (is_student.value) {
		delete filters.value['enrolled']
	} else {
		delete filters.value['start_date']
		delete filters.value['published']
		orderBy.value = 'start_date desc'
		if (currentTab.value == 'Upcoming') {
			filters.value['start_date'] = ['>=', dayjs().format('YYYY-MM-DD')]
			filters.value['published'] = 1
			orderBy.value = 'start_date'
		} else if (currentTab.value == 'Archived') {
			filters.value['start_date'] = ['<=', dayjs().format('YYYY-MM-DD')]
		} else if (currentTab.value == 'Unpublished') {
			filters.value['published'] = 0
		}
	}
}

const updateStudentFilter = () => {
	if (!user.data) {
		filters.value['start_date'] = ['>=', dayjs().format('YYYY-MM-DD')]
		filters.value['published'] = 1
	} else if (is_student.value && currentTab.value != 'Enrolled') {
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

const updateCategories = (data) => {
	data.forEach((batch) => {
		if (
			batch.category &&
			!categories.value.find((category) => category.value === batch.category)
		)
			categories.value.push({
				label: batch.category,
				value: batch.category,
			})
	})
}

watch(currentTab, () => {
	updateBatches()
})

const batchTabs = computed(() => {
	let tabs = [
		{
			label: __('batches.list.all'),
			value: 'All',
		},
	]

	if (
		user.data?.is_moderator ||
		user.data?.is_instructor
) {
		tabs.push({ label: __('batches.list.upcoming'), value: 'Upcoming' })
		tabs.push({ label: __('batches.list.archived'), value: 'Archived' })
		tabs.push({ label: __('batches.list.unpublished'), value: 'Unpublished' })
	} else if (user.data) {
		tabs.push({ label: __('batches.list.enrolled'), value: 'Enrolled' })
	}
	return tabs
})

const canCreateBatch = () => {
	if (readOnlyMode) return false
	if (
		user.data?.is_moderator ||
		user.data?.is_instructor
)
		return true
	return false
}

const breadcrumbs = computed(() => [
	{
		label: __('batches.list.batches'),
		route: { name: 'Batches' },
	},
])

usePageMeta(() => {
	return {
		title: __('batches.list.batches'),
		icon: brand.favicon,
	}
})
</script>
<style scoped>
.lms-batches__serif {
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

.lms-batches__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}
</style>
