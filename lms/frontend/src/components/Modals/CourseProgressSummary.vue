<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('courses.progress.summary'),
			size: '5xl',
		}"
	>
		<template #body-title>
			<h3 class="lms-progress-summary__serif text-2xl leading-6 text-ink-gray-9">
				{{ __('courses.progress.summary') }}
			</h3>
		</template>
		<template #body-content>
			<div
				class="flex flex-col-reverse md:flex-row justify-between md:space-x-10 text-base mt-10"
			>
				<div class="w-full">
					<div class="flex items-center justify-between space-x-5 mb-4">
						<FormControl
							v-model="searchFilter"
							:placeholder="__('courses.progress.searchByMember')"
							type="text"
							class="w-full"
						/>
					</div>
					<div class="max-h-[70vh] overflow-y-auto">
						<ListView
							v-if="progressList.loading || progressList.data?.length"
							:columns="progressColumns"
							:rows="progressList.data"
							rowKey="name"
							:options="{
								selectable: false,
								showTooltip: false,
							}"
						>
							<ListHeader
								class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
							>
								<ListHeaderItem
									:item="item"
									v-for="item in progressColumns"
									:key="item.key"
								>
									<template #prefix="{ item }">
										<FeatherIcon
											:name="item.icon?.toString()"
											class="h-4 w-4"
										/>
									</template>
								</ListHeaderItem>
							</ListHeader>
							<ListRows v-for="row in progressList.data">
								<router-link
									:to="{
										name: 'Profile',
										params: { username: row.member_username },
									}"
								>
									<ListRow :row="row">
										<template #default="{ column, item }">
											<ListRowItem
												:item="row[column.key]"
												:align="column.align"
											>
												<template #prefix>
													<div v-if="column.key == 'member_name'">
														<Avatar
															class="flex items-center"
															:image="row['member_image']"
															:label="item"
															size="sm"
														/>
													</div>
												</template>
												<div
													:class="
														column.key === 'progress'
															? 'lms-progress-summary__mono'
															: ''
													"
												>
													{{ row[column.key].toString()
													}}{{ column.key === 'progress' ? '%' : '' }}
												</div>
											</ListRowItem>
										</template>
									</ListRow>
								</router-link>
							</ListRows>
						</ListView>
						<div
							v-if="progressList.data && progressList.hasNextPage"
							class="flex justify-center my-5"
						>
							<Button @click="progressList.next()">
								{{ __('courses.progress.loadMore') }}
							</Button>
						</div>
					</div>
				</div>
				<div class="mb-4 self-start w-full space-y-5">
					<div
						class="flex flex-col md:flex-row items-center space-y-2 md:space-y-0 md:space-x-4"
					>
						<NumberChart
							class="border rounded-md w-full"
							:config="{
									title: __('courses.progress.enrollments'),
								value: memberCount || 0,
							}"
						/>
						<NumberChart
							class="border rounded-md w-full"
							:config="{
									title: __('courses.progress.averageProgress'),
								value: chartDetails.data?.average_progress || 0,
							}"
						/>
					</div>
					<DonutChart
						:config="{
							data: chartDetails.data?.progress_distribution || [],
								title: __('courses.progress.progressDistribution'),
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
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import {
	Avatar,
	Button,
	createListResource,
	createResource,
	Dialog,
	DonutChart,
	FeatherIcon,
	FormControl,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	ListRowItem,
	NumberChart,
} from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { theme } from '@/utils/theme'

const show = defineModel<boolean>({ default: false })
const searchFilter = ref<string | null>(null)
type Filters = {
	course: string | undefined

	member_name?: string[]
}

const props = defineProps<{
	courseName?: string
	enrollments?: number
}>()

const memberCount = ref<number>(props.enrollments || 0)

const chartDetails = createResource({
	url: 'lms.lms.api.get_course_progress_distribution',
	params: {
		course: props.courseName,
	},
	auto: true,
})

const progressList = createListResource({
	doctype: 'LMS Enrollment',
	filters: {
		course: props.courseName,
	},
	fields: [
		'name',
		'member',
		'member_name',
		'member_image',
		'member_username',
		'progress',
	],
	pageLength: 50,
	auto: true,
})

watch([searchFilter], () => {
	let filterApplied = false
	let filters: Filters = {
		course: props.courseName,
	}

	if (searchFilter.value) {
		filters.member_name = ['like', `%${searchFilter.value}%`]
		filterApplied = true
	}

	progressList.update({
		filters: filters,
	})
	progressList.reload(
		{},
		{
			onSuccess(data: any[]) {
				memberCount.value = filterApplied ? data.length : props.enrollments || 0
			},
		}
	)
})

const progressColumns = computed(() => {
	return [
		{
			label: __('courses.progress.member'),
			key: 'member_name',
			width: '60%',
			icon: 'user',
		},
		{
			label: __('courses.progress.progress'),
			key: 'progress',
			align: 'right',
			icon: 'trending-up',
		},
	]
})
</script>
<style scoped>
.lms-progress-summary__serif {
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

.lms-progress-summary__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
	font-variant-numeric: tabular-nums;
}
</style>
