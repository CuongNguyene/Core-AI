<template>
	<Dialog v-model="show" :options="{ size: '2xl' }">
		<template #body-title>
			<h3 class="lms-stat-detail__serif text-2xl leading-6 text-ink-gray-9">
				{{ title }}
			</h3>
		</template>
		<template #body-content>
			<div v-if="details.loading" class="py-10 text-center text-ink-gray-5 text-sm">
				{{ __('Loading...') }}
			</div>
			<div
				v-else-if="!details.data?.length"
				class="py-10 text-center text-ink-gray-5 text-sm"
			>
				{{ __('No records found for the current filters.') }}
			</div>
			<div v-else class="max-h-[60vh] overflow-y-auto -mx-4">
				<table class="w-full text-sm">
					<thead class="sticky top-0 bg-surface-white">
						<tr class="text-left text-ink-gray-5 border-b">
							<th
								v-for="column in columns"
								:key="column.key"
								class="font-medium px-4 py-2"
							>
								{{ column.label }}
							</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="(row, index) in details.data"
							:key="index"
							class="border-b last:border-0"
						>
							<td
								v-for="column in columns"
								:key="column.key"
								class="px-4 py-2 text-ink-gray-8"
							>
								{{ column.format ? column.format(row[column.key]) : row[column.key] }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, createResource, dayjs } from 'frappe-ui'
import { computed, watch } from 'vue'

const show = defineModel({ default: false })

const props = defineProps({
	metric: { type: String, required: true },
	title: { type: String, required: true },
	scope: { type: String, required: true },
	department: { type: String, default: '' },
	employee: { type: String, default: '' },
	company: { type: String, default: '' },
	fromDate: { type: String, default: '' },
	toDate: { type: String, default: '' },
})

const columnsByMetric = {
	courses: [{ key: 'title', label: __('statistics.details.course') }],
	enrollments: (scope) => [
		...(scope === 'mine' ? [] : [{ key: 'member_name', label: __('statistics.details.member') }]),
		{ key: 'course_title', label: __('statistics.details.course') },
		{
			key: 'progress',
			label: __('statistics.details.progress'),
			format: (v) => `${Math.round(v)}%`,
		},
		{
			key: 'date',
			label: __('statistics.details.enrolledOn'),
			format: (v) => dayjs(v).format('D MMM YYYY'),
		},
	],
	completions: (scope) => [
		...(scope === 'mine' ? [] : [{ key: 'member_name', label: __('statistics.details.member') }]),
		{ key: 'course_title', label: __('statistics.details.course') },
		{
			key: 'date',
			label: __('statistics.details.completedOn'),
			format: (v) => dayjs(v).format('D MMM YYYY'),
		},
	],
	certifications: (scope) => [
		...(scope === 'mine' ? [] : [{ key: 'member_name', label: __('statistics.details.member') }]),
		{ key: 'course_title', label: __('statistics.details.course') },
		{
			key: 'date',
			label: __('statistics.details.issuedOn'),
			format: (v) => dayjs(v).format('D MMM YYYY'),
		},
	],
	time_spent: (scope) => [
		...(scope === 'mine' ? [] : [{ key: 'member_name', label: __('statistics.details.member') }]),
		{ key: 'course_title', label: __('statistics.details.course') },
		{
			key: 'hours',
			label: __('statistics.details.hours'),
			format: (v) => __('statistics.details.hoursValue').format(v),
		},
	],
}

const columns = computed(() => {
	let config = columnsByMetric[props.metric]
	return typeof config === 'function' ? config(props.scope) : config
})

const details = createResource({
	url: 'lms.lms.api.get_statistic_details',
	auto: false,
})

function reload() {
	if (!show.value) return
	details.submit({
		metric: props.metric,
		scope: props.scope,
		department: props.department,
		employee: props.employee,
		company: props.company,
		from_date: props.fromDate,
		to_date: props.toDate,
	})
}

watch(show, (isOpen) => {
	if (isOpen) reload()
})
watch(
	() => [
		props.metric,
		props.scope,
		props.department,
		props.employee,
		props.company,
		props.fromDate,
		props.toDate,
	],
	reload
)
</script>
<style scoped>
.lms-stat-detail__serif {
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
