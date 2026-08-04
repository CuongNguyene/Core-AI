<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
	</header>
	<div class="py-5 mx-5">
		<div class="text-lg font-semibold text-ink-gray-7 mb-4">
			{{
				submissions.data?.length
					? __('assignments.nSubmissions').format(submissions.data.length)
					: __('assignments.noSubmissions')
			}}
		</div>
		<div class="grid grid-cols-3 gap-5 mb-5">
			<Link
				doctype="LMS Assignment"
				v-model="assignmentID"
				:placeholder="__('assignments.assignment')"
			/>
			<Link doctype="User" v-model="member" :placeholder="__('assignments.member')" />
			<Autocomplete
				:modelValue="status"
				@update:modelValue="(opt) => (status = opt?.value || '')"
				:options="statusOptions"
				:placeholder="__('assignments.status')"
				size="sm"
			/>
		</div>
		<ListView
			v-if="submissions.loading || submissions.data?.length"
			:columns="submissionColumns"
			:rows="submissions.data"
			rowKey="name"
		>
			<ListHeader
				class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
			>
				<ListHeaderItem :item="item" v-for="item in submissionColumns">
					<template #prefix="{ item }">
						<FeatherIcon :name="item.icon?.toString()" class="h-4 w-4" />
					</template>
				</ListHeaderItem>
			</ListHeader>
			<ListRows>
				<router-link
					v-for="row in submissions.data"
					:to="{
						name: 'AssignmentSubmission',
						params: {
							assignmentID: row.assignment,
							submissionName: row.name,
						},
					}"
				>
					<ListRow :row="row">
						<template #default="{ column, item }">
							<ListRowItem :item="row[column.key]" :align="column.align">
								<div v-if="column.key == 'status'">
									<Badge :theme="getStatusTheme(row[column.key])">
										{{ row[column.key] }}
									</Badge>
								</div>
								<div v-else>
									{{ row[column.key] }}
								</div>
							</ListRowItem>
						</template>
					</ListRow>
				</router-link>
			</ListRows>
		</ListView>
		<EmptyState v-else type="Submissions" />
	</div>
</template>
<script setup>
import {
	Badge,
	Breadcrumbs,
	createListResource,
	FeatherIcon,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	ListRowItem,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { sessionStore } from '../stores/session'
import Link from '@/components/Controls/Link.vue'
import Autocomplete from '@/components/Controls/Autocomplete.vue'
import EmptyState from '@/components/EmptyState.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const { brand } = sessionStore()
const router = useRouter()
const assignmentID = ref('')
const member = ref('')
const status = ref('')

onMounted(() => {
	if (!user.data?.is_instructor && !user.data?.is_moderator) {
		router.push({ name: 'Courses' })
	}
	assignmentID.value = router.currentRoute.value.query.assignmentID
	member.value = router.currentRoute.value.query.member
	status.value = router.currentRoute.value.query.status
	reloadSubmissions()
})

const getAssignmentFilters = () => {
	let filters = {}
	if (assignmentID.value) {
		filters.assignment = assignmentID.value
	}
	if (member.value) {
		filters.member = member.value
	}
	if (status.value) {
		filters.status = status.value
	}
	return filters
}

const submissions = createListResource({
	doctype: 'LMS Assignment Submission',
	fields: [
		'name',
		'assignment',
		'assignment_title',
		'member_name',
		'creation',
		'status',
	],
	orderBy: 'creation desc',
	transform(data) {
		return data.map((row) => {
			return {
				...row,
				creation: dayjs(row.creation).fromNow(),
			}
		})
	},
})

watch([assignmentID, member, status], () => {
	router.push({
		query: {
			assignmentID: assignmentID.value,
			member: member.value,
			status: status.value,
		},
	})
	reloadSubmissions()
})

const reloadSubmissions = () => {
	submissions.update({
		filters: getAssignmentFilters(),
	})
	submissions.reload()
}

const submissionColumns = computed(() => {
	return [
		{
			label: __('assignments.member'),
			key: 'member_name',
			width: 1,
			icon: 'user',
		},
		{
			label: __('assignments.assignment'),
			key: 'assignment_title',
			width: 2,
			icon: 'file-text',
		},
		{
			label: __('assignments.submitted'),
			key: 'creation',
			width: 1,
			align: 'center',
			icon: 'clock',
		},
		{
			label: __('assignments.status'),
			key: 'status',
			width: 1,
			align: 'center',
			icon: 'check-circle',
		},
	]
})

const statusOptions = computed(() => {
	return [
		{ label: __('assignments.pass'), value: 'Pass' },
		{ label: __('assignments.fail'), value: 'Fail' },
		{ label: __('assignments.notGraded'), value: 'Not Graded' },
	]
})

const getStatusTheme = (status) => {
	if (status === 'Pass') {
		return 'green'
	} else if (status === 'Not Graded') {
		return 'blue'
	} else {
		return 'red'
	}
}

const breadcrumbs = computed(() => {
	return [
		{
			label: __('assignments.assignments'),
			route: { name: 'Assignments' },
		},
		{
			label: __('assignments.assignmentSubmissions'),
		},
	]
})

usePageMeta(() => {
	return {
		title: __('assignments.assignmentSubmissions'),
		icon: brand.favicon,
	}
})
</script>
