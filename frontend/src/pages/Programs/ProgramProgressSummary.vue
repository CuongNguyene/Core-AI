<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('programs.progressSummary.title').format(programName),
			size: '2xl',
		}"
	>
		<template #body-content>
			<div class="text-base">
				<div class="flex items-center justify-between space-x-4 mb-4">
					<NumberChart
						class="border rounded-md w-full"
						:config="{
							title: __('programs.progressSummary.enrollments'),
							value: programMembers.length || 0,
						}"
					/>
					<NumberChart
						class="border rounded-md w-full"
						:config="{
							title: __('programs.progressSummary.averageProgress'),
							value: averageProgress || 0,
						}"
					/>
				</div>
				<DonutChart
					:config="{
						data: progressDistribution || [],
						title: __('programs.progressSummary.progressDistribution'),
						categoryColumn: 'category',
						valueColumn: 'count',
						colors: [
							theme.colors.red['400'],
							theme.colors.amber['400'],
							theme.colors.pink['400'],
							theme.colors.blue['400'],
							theme.colors.green['400'],
						],
					}"
				/>

				<div class="mt-10">
					<FormControl
						v-model="searchFilter"
						:placeholder="__('programs.progressSummary.searchByMember')"
						class="mb-4"
					/>
					<ListView
						v-if="progressList.length"
						:columns="progressColumns"
						:rows="progressList"
						rowKey="name"
						:options="{
							selectable: false,
							showTooltip: false,
						}"
					/>
					<div v-else class="text-center text-gray-500">
						{{ __('programs.progressSummary.noMembers') }}
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import {
	Dialog,
	DonutChart,
	FormControl,
	ListView,
	NumberChart,
} from 'frappe-ui'
import type { ProgramMember } from '@/types'
import { computed, ref, watch } from 'vue'
import { theme } from '@/utils/theme'

const show = defineModel<boolean>({ default: false })
const searchFilter = ref<string | null>(null)

const props = defineProps<{
	programName: string
	programMembers: ProgramMember[]
}>()

const progressList = ref<ProgramMember[]>(props.programMembers || [])

const progressDistribution = computed(() => {
	const categories = ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%']
	const distribution = categories.map((category) => {
		const [min, max] = category.slice(0, -1).split('-').map(Number)
		return {
			category,
			count: props.programMembers.filter((member) => {
				const progress = member.progress || 0
				return progress >= min && progress < max
			}).length,
		}
	})
	return distribution
})

const averageProgress = computed(() => {
	if (props.programMembers.length === 0) return 0
	const totalProgress = props.programMembers.reduce(
		(sum, member) => sum + (member.progress || 0),
		0
	)
	return totalProgress / props.programMembers.length
})

watch(searchFilter, () => {
	if (searchFilter.value) {
		progressList.value = props.programMembers.filter((member) =>
			member.full_name.toLowerCase().includes(searchFilter.value?.toLowerCase())
		)
	} else {
		progressList.value = props.programMembers
	}
})

const progressColumns = computed(() => {
	return [
		{
			label: __('programs.progressSummary.member'),
			key: 'full_name',
			width: '50%',
		},
		{
			label: __('programs.progressSummary.progressPercent'),
			key: 'progress',
			align: 'right',
		},
	]
})
</script>
