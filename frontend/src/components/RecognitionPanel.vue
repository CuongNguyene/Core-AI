<template>
	<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
		<div class="border rounded-md p-4">
			<div class="text-sm font-medium text-ink-gray-7">{{ __('statistics.topLearners') }}</div>
			<div class="text-xs text-ink-gray-5 mb-3">{{ __('statistics.topLearnersSubtitle') }}</div>
			<div v-if="topLearners.length" class="space-y-2">
				<div
					v-for="(row, idx) in topLearners"
					:key="row.employee"
					class="flex items-center justify-between gap-3 text-sm py-1.5"
					:class="idx !== topLearners.length - 1 ? 'border-b' : ''"
				>
					<div class="flex items-center gap-2 min-w-0">
						<span class="text-ink-gray-5 w-5 flex-shrink-0">{{ idx + 1 }}</span>
						<div class="min-w-0">
							<div class="truncate">{{ row.employee_name }}</div>
							<div class="text-xs text-ink-gray-5 truncate">{{ row.department_name }}</div>
						</div>
					</div>
					<div class="flex items-center gap-3 text-xs text-ink-gray-6 flex-shrink-0">
						<span>{{ row.time_spent_hours }}{{ __('statistics.hoursSuffix') }}</span>
						<span>{{ row.completions }} {{ __('statistics.completions') }}</span>
						<span>{{ row.certifications }} {{ __('statistics.certifications') }}</span>
					</div>
				</div>
			</div>
			<div v-else class="text-sm text-ink-gray-5">{{ __('statistics.noDataForPeriod') }}</div>
		</div>
		<div class="border rounded-md p-4">
			<div class="text-sm font-medium text-ink-gray-7">{{ __('statistics.departmentRanking') }}</div>
			<div class="text-xs text-ink-gray-5 mb-3">{{ __('statistics.departmentRankingSubtitle') }}</div>
			<div v-if="departmentRanking.length" class="space-y-2">
				<div
					v-for="(row, idx) in departmentRanking"
					:key="row.department"
					class="flex items-center justify-between gap-3 text-sm py-1.5"
					:class="idx !== departmentRanking.length - 1 ? 'border-b' : ''"
				>
					<div class="flex items-center gap-2 min-w-0">
						<span class="text-ink-gray-5 w-5 flex-shrink-0">{{ idx + 1 }}</span>
						<div class="min-w-0">
							<div class="truncate">{{ row.department_name }}</div>
							<div class="text-xs text-ink-gray-5">
								{{ row.employees }} {{ __('statistics.employees') }}
							</div>
						</div>
					</div>
					<div class="flex items-center gap-3 text-xs text-ink-gray-6 flex-shrink-0">
						<span>{{ row.avg_hours_per_employee }}{{ __('statistics.hoursSuffix') }}/{{ __('statistics.employee') }}</span>
						<span>{{ row.completions }} {{ __('statistics.completions') }}</span>
					</div>
				</div>
			</div>
			<div v-else class="text-sm text-ink-gray-5">{{ __('statistics.noDataForPeriod') }}</div>
		</div>
	</div>
</template>
<script setup>
defineProps({
	topLearners: {
		type: Array,
		default: () => [],
	},
	departmentRanking: {
		type: Array,
		default: () => [],
	},
})
</script>
