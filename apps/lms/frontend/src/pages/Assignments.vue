<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-2 bg-surface-white/90 backdrop-blur-md px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<Button
			v-if="!readOnlyMode"
			variant="solid"
			@click="
				() => {
					assignmentID = 'new'
					showAssignmentForm = true
				}
			"
		>
			<template #prefix>
				<Plus class="w-4 h-4" />
			</template>
			{{ __('assignments.create') }}
		</Button>
	</header>

	<div class="py-5 mx-5">
		<div class="flex items-center justify-between mb-4">
			<div class="lms-assignments__serif text-lg text-ink-gray-9">
				{{
					assignments.data?.length
						? __('assignments.nAssignments').format(assignments.data.length)
						: __('assignments.noAssignments')
				}}
			</div>
			<div class="flex items-center space-x-2">
				<FormControl
					v-model="titleFilter"
					type="text"
					:placeholder="__('assignments.searchByTitle')"
				>
					<template #prefix>
						<FeatherIcon name="search" class="size-4 text-ink-gray-5" />
					</template>
				</FormControl>
				<Autocomplete
					:modelValue="typeFilter"
					@update:modelValue="(opt) => (typeFilter = opt?.value || '')"
					:options="assignmentTypes"
					:placeholder="__('assignments.type')"
					size="sm"
				/>
			</div>
		</div>
		<ListView
			v-if="assignments.data?.length"
			:columns="assignmentColumns"
			:rows="assignments.data"
			row-key="name"
			:options="{
				showTooltip: false,
				selectable: false,
				onRowClick: (row) => {
					if (readOnlyMode) return
					assignmentID = row.name
					showAssignmentForm = true
				},
			}"
		>
			<ListHeader
				class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
			>
				<ListHeaderItem :item="item" v-for="item in assignmentColumns">
					<template #prefix="{ item }">
						<FeatherIcon :name="item.icon?.toString()" class="h-4 w-4" />
					</template>
				</ListHeaderItem>
			</ListHeader>
			<ListRows>
				<ListRow v-for="row in assignments.data" :row="row" :key="row.name">
					<template #default="{ column, item }">
						<ListRowItem :item="row[column.key]" :align="column.align">
							<div
								v-if="column.key == 'creation'"
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
			</ListRows>
		</ListView>
		<EmptyState v-else type="Assignments" />
		<div
			v-if="assignments.data && assignments.hasNextPage"
			class="flex justify-center my-5"
		>
			<Button @click="assignments.next()">
				{{ __('assignments.loadMore') }}
			</Button>
		</div>
	</div>
	<AssignmentForm
		v-model="showAssignmentForm"
		v-model:assignments="assignments"
		:assignmentID="assignmentID"
	/>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	createListResource,
	FeatherIcon,
	FormControl,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	ListRowItem,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { Plus } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { sessionStore } from '../stores/session'
import AssignmentForm from '@/components/Modals/AssignmentForm.vue'
import EmptyState from '@/components/EmptyState.vue'
import Autocomplete from '@/components/Controls/Autocomplete.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const titleFilter = ref('')
const typeFilter = ref('')
const showAssignmentForm = ref(false)
const assignmentID = ref('new')
const { brand } = sessionStore()
const router = useRouter()
const readOnlyMode = window.read_only_mode

const redirectIfNotAllowed = () => {
	if (user.data && !user.data?.is_moderator && !user.data?.is_instructor) {
		window.location.href = '/lms/courses'
	}
}

// user.data can load either before this component mounts (checked in
// onMounted below) or asynchronously after (caught by this watcher) -
// a plain onMounted check alone misses the latter case.
watch(user, redirectIfNotAllowed)

onMounted(() => {
	redirectIfNotAllowed()
	titleFilter.value = router.currentRoute.value.query.title
	typeFilter.value = router.currentRoute.value.query.type
})

watch([titleFilter, typeFilter], () => {
	router.push({
		query: {
			title: titleFilter.value,
			type: typeFilter.value,
		},
	})
	reloadAssignments()
})

const reloadAssignments = () => {
	assignments.update({
		filters: assignmentFilter.value,
	})
	assignments.reload()
}

const assignmentFilter = computed(() => {
	let filters = {}
	if (titleFilter.value) {
		filters.title = ['like', `%${titleFilter.value}%`]
	}
	if (typeFilter.value) {
		filters.type = typeFilter.value
	}
	return filters
})

const assignments = createListResource({
	doctype: 'LMS Assignment',
	filters: assignmentFilter,
	fields: ['name', 'title', 'type', 'creation', 'question'],
	orderBy: 'modified desc',
	auto: true,
	cache: ['assignments'],
	transform(data) {
		return data.map((row) => {
			return {
				...row,
				creation: dayjs(row.creation).fromNow(),
			}
		})
	},
})

watch(
	user,
	() => {
		if (user.data) {
			assignments.update({ filters: assignmentFilter.value })
			assignments.reload()
		}
	},
	{ immediate: true }
)

const assignmentColumns = computed(() => {
	return [
		{
			label: __('assignments.title'),
			key: 'title',
			width: 2,
			icon: 'file-text',
		},
		{
			label: __('assignments.type'),
			key: 'type',
			width: 1,
			align: 'center',
			icon: 'tag',
		},
		{
			label: __('assignments.created'),
			key: 'creation',
			width: 1,
			align: 'center',
			icon: 'clock',
		},
	]
})

const assignmentTypeLabels = {
	Document: 'assignments.typeDocument',
	Image: 'assignments.typeImage',
	PDF: 'assignments.typePdf',
	URL: 'assignments.typeUrl',
	Text: 'assignments.typeText',
}

const assignmentTypes = computed(() => {
	let types = ['Document', 'Image', 'PDF', 'URL', 'Text']
	return types.map((type) => {
		return {
			label: __(assignmentTypeLabels[type]),
			value: type,
		}
	})
})

const breadcrumbs = computed(() => [
	{
		label: __('assignments.assignments'),
		route: { name: 'Assignments' },
	},
])

usePageMeta(() => {
	return {
		title: __('assignments.assignments'),
		icon: brand.favicon,
	}
})
</script>
<style scoped>
.lms-assignments__serif {
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
</style>
