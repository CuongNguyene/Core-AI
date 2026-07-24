<template>
	<div class="">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<Button
				:label="__('Export')"
				:icon-left="Download"
				@click="showExportModal = true"
			/>
		</header>
		<div v-if="chartDetails.data" class="p-5">
			<div
				v-if="canViewDepartmentReport"
				class="grid grid-cols-2 sm:grid-cols-4 gap-3 items-end mb-4"
			>
				<div>
					<div class="text-xs text-ink-gray-5 mb-1">{{ __('Date Range') }}</div>
					<Dropdown
						v-if="!showDatePicker"
						:options="rangeOptions"
						class="w-full"
					>
						<template #default>
							<div
								class="flex justify-between items-center border rounded text-ink-gray-8 px-2 h-7 cursor-pointer hover:border-outline-gray-3"
							>
								<div class="flex items-center truncate">
									<Calendar class="size-4 text-ink-gray-5 mr-2 flex-shrink-0" />
									<span class="text-sm truncate">{{ presetLabel }}</span>
								</div>
								<ChevronDown class="size-4 text-ink-gray-5 flex-shrink-0" />
							</div>
						</template>
					</Dropdown>
					<DateRangePicker
						v-else
						ref="datePickerRef"
						class="w-full"
						v-model="filters.period"
						placeholder="Period"
						:formatter="formatRange"
						@update:modelValue="onDateRangeUpdate"
					>
						<template #prefix>
							<Calendar class="size-4 text-ink-gray-5 mr-2" />
						</template>
					</DateRangePicker>
				</div>
				<Link
					v-model="filters.company"
					:label="__('Company')"
					:placeholder="__('All Companies')"
					doctype="Company"
				/>
				<Link
					v-model="filters.department"
					:label="__('Department')"
					:placeholder="__('All Departments')"
					doctype="Department"
					:filters="departmentFilters"
				/>
				<Link
					v-model="filters.employee"
					:label="__('Employee')"
					:placeholder="__('All Employees')"
					doctype="Employee"
					:filters="employeeFilters"
				/>
			</div>
			<div v-else class="max-w-56 mb-4">
				<DateRangeFilter v-model="filters.period" :label="__('Date Range')" />
			</div>

			<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
				<Tooltip :text="__('Published Courses')">
					<NumberChart
						class="border rounded-md"
						:config="{ title: 'Courses', value: chartDetails.data.courses }"
					/>
				</Tooltip>
				<Tooltip :text="__('Course Enrollments')">
					<NumberChart
						class="border rounded-md"
						:config="{
							title: 'Enrollments',
							value: isStaffView
								? summary?.enrollments ?? chartDetails.data.enrollments
								: myStats.data?.enrollments ?? 0,
						}"
					/>
				</Tooltip>
				<Tooltip :text="__('Course Completions')">
					<NumberChart
						class="border rounded-md"
						:config="{
							title: 'Completions',
							value: isStaffView
								? summary?.completions ?? chartDetails.data.completions
								: myStats.data?.completions ?? 0,
						}"
					/>
				</Tooltip>
				<Tooltip :text="__('Certified Members')">
					<NumberChart
						class="border rounded-md"
						:config="{
							title: 'Certifications',
							value: isStaffView
								? summary?.certifications ?? chartDetails.data.certifications
								: myStats.data?.certifications ?? 0,
						}"
					/>
				</Tooltip>
			</div>
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
				<template v-if="canViewDepartmentReport">
					<div class="border rounded-md min-h-72">
						<AxisChart v-if="progressChartConfig" :config="progressChartConfig" />
					</div>
					<div class="border rounded-md min-h-72">
						<AxisChart v-if="employeesChartConfig" :config="employeesChartConfig" />
					</div>
				</template>
				<div v-else-if="isStaffView" class="border rounded-md min-h-72">
					<AxisChart v-if="signupsChartConfig" :config="signupsChartConfig" />
				</div>
				<div class="border rounded-md min-h-72">
					<AxisChart v-if="enrollmentChartConfig" :config="enrollmentChartConfig" />
				</div>
				<div class="border rounded-md">
					<AxisChart
						v-if="certificationChartConfig"
						:config="certificationChartConfig"
					/>
				</div>
				<div class="border rounded-md">
					<DonutChart v-if="donutChartConfig" :config="donutChartConfig" />
				</div>
				<div v-if="canViewDepartmentReport" class="border rounded-md">
					<DonutChart
						v-if="departmentChartConfig"
						:config="departmentChartConfig"
					/>
				</div>
			</div>

			<div class="mt-4">
				<div class="border rounded-md min-h-72">
					<AxisChart v-if="timeSpentChartConfig" :config="timeSpentChartConfig" />
				</div>
			</div>
		</div>

		<Dialog
			v-model="showExportModal"
			:options="{ title: __('Export Dashboard Report'), size: '5xl' }"
		>
			<template #body-content>
				<div class="space-y-4 pb-2 max-h-[70vh] overflow-y-auto">
					<div
						ref="chartsContainerRef"
						class="js-charts-export-container bg-surface-white rounded-md border p-4"
					>
						<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
							<template v-if="canViewDepartmentReport">
								<div class="border rounded-md min-h-72">
									<AxisChart
										v-if="progressChartConfig"
										:config="progressChartConfig"
									/>
								</div>
								<div class="border rounded-md min-h-72">
									<AxisChart
										v-if="employeesChartConfig"
										:config="employeesChartConfig"
									/>
								</div>
							</template>
							<div v-else-if="isStaffView" class="border rounded-md min-h-72">
								<AxisChart v-if="signupsChartConfig" :config="signupsChartConfig" />
							</div>
							<div class="border rounded-md min-h-72">
								<AxisChart
									v-if="enrollmentChartConfig"
									:config="enrollmentChartConfig"
								/>
							</div>
							<div class="border rounded-md">
								<AxisChart
									v-if="certificationChartConfig"
									:config="certificationChartConfig"
								/>
							</div>
							<div class="border rounded-md">
								<DonutChart v-if="donutChartConfig" :config="donutChartConfig" />
							</div>
							<div v-if="canViewDepartmentReport" class="border rounded-md">
								<DonutChart
									v-if="departmentChartConfig"
									:config="departmentChartConfig"
								/>
							</div>
							<div class="border rounded-md min-h-72">
								<AxisChart
									v-if="timeSpentChartConfig"
									:config="timeSpentChartConfig"
								/>
							</div>
						</div>
					</div>
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showExportModal = false" />
					<Button
						:label="__('Export PDF')"
						variant="solid"
						:loading="exporting"
						@click="exportPdf"
					/>
				</div>
			</template>
		</Dialog>
	</div>
</template>
<script setup>
import {
	AxisChart,
	Breadcrumbs,
	Button,
	createResource,
	dayjs,
	DateRangePicker,
	Dialog,
	Dropdown,
	DonutChart,
	NumberChart,
	Tooltip,
	usePageMeta,
} from 'frappe-ui'
import { Calendar, ChevronDown, Download } from 'lucide-vue-next'
import { computed, reactive, ref, watch } from 'vue'
import { sessionStore } from '../stores/session'
import { usersStore } from '../stores/user'
import Link from '@/components/Controls/Link.vue'
import DateRangeFilter from '@/components/Common/DateRangeFilter.vue'

const { brand } = sessionStore()
const { userResource } = usersStore()

const canViewDepartmentReport = computed(
	() => !!userResource.data?.can_view_department_report
)

const canViewTimeSpent = computed(
	() =>
		userResource.data?.is_moderator ||
		userResource.data?.is_instructor ||
		userResource.data?.is_system_manager
)

const isStaffView = computed(
	() => canViewTimeSpent.value || canViewDepartmentReport.value
)

const myStats = createResource({
	url: 'lms.lms.api.get_my_learning_stats',
	auto: true,
})

function getLastXDays(days) {
	let to = dayjs().format('YYYY-MM-DD')
	let from = dayjs().subtract(days, 'day').format('YYYY-MM-DD')
	return `${from},${to}`
}

function formatRange(range) {
	if (!range) return ''
	let [from, to] = range.split(',')
	if (!from || !to) return range
	return `${dayjs(from).format('MMM D')} - ${dayjs(to).format('MMM D, YYYY')}`
}

const rangePresets = { 0: 'Today', 7: 'Last 7 Days', 30: 'Last 30 Days', 60: 'Last 60 Days', 90: 'Last 90 Days' }

function presetLabelFor(period) {
	if (!period) return 'Custom Range'
	let [from, to] = period.split(',')
	if (!from || !to) return period
	let diffDays = dayjs(to).diff(dayjs(from), 'day')
	return rangePresets[diffDays] || formatRange(period)
}

const filters = reactive({
	company: '',
	department: '',
	employee: '',
	period: getLastXDays(30),
	granularity: 'Monthly',
})

const departmentFilters = computed(() => {
	return filters.company ? { company: filters.company } : {}
})

const employeeFilters = computed(() => {
	let f = {}
	if (filters.company) f.company = filters.company
	if (filters.department) f.department = filters.department
	return f
})

watch(
	() => filters.company,
	() => {
		filters.department = ''
		filters.employee = ''
	}
)

watch(
	() => filters.department,
	() => {
		filters.employee = ''
	}
)

const showDatePicker = ref(false)
const datePickerRef = ref(null)
const presetLabel = ref(presetLabelFor(filters.period))

function applyPreset(label, period) {
	presetLabel.value = label
	filters.period = period
	showDatePicker.value = false
}

const rangeOptions = computed(() => [
	{
		group: 'Presets',
		hideLabel: true,
		items: [
			{ label: __('Today'), onClick: () => applyPreset('Today', getLastXDays(0)) },
			{ label: __('Last 7 Days'), onClick: () => applyPreset('Last 7 Days', getLastXDays(7)) },
			{ label: __('Last 30 Days'), onClick: () => applyPreset('Last 30 Days', getLastXDays(30)) },
			{ label: __('Last 60 Days'), onClick: () => applyPreset('Last 60 Days', getLastXDays(60)) },
			{ label: __('Last 90 Days'), onClick: () => applyPreset('Last 90 Days', getLastXDays(90)) },
		],
	},
	{
		label: __('Custom Range'),
		onClick: () => {
			presetLabel.value = 'Custom Range'
			showDatePicker.value = true
			setTimeout(() => datePickerRef.value?.open(), 0)
		},
	},
])

function onDateRangeUpdate(range) {
	showDatePicker.value = false
	presetLabel.value = presetLabelFor(range)
}

const showExportModal = ref(false)
const exporting = ref(false)

const departmentReport = createResource({
	url: 'lms.lms.api.get_department_report',
	auto: false,
})

watch(
	canViewDepartmentReport,
	(canView) => {
		if (canView) reload()
	},
	{ immediate: true }
)

watch(filters, () => {
	if (canViewDepartmentReport.value) reload()
})

function reload() {
	let [from_date, to_date] = (filters.period || '').split(',')
	departmentReport.submit({
		company: filters.company,
		department: filters.department,
		employee: filters.employee,
		from_date,
		to_date,
		granularity: filters.granularity,
	})
}

const summary = computed(() => departmentReport.data?.summary)
const periodSummary = computed(() => departmentReport.data?.period_summary)
const departmentSummary = computed(() => departmentReport.data?.department_summary)

const enrollmentXAxis = computed(() => {
	return canViewDepartmentReport.value
		? { key: 'period', type: 'category', title: 'Period' }
		: { key: 'date', type: 'time', title: 'Date', timeGrain: 'day' }
})

const progressChartConfig = computed(() => {
	if (!periodSummary.value) return null
	return {
		data: periodSummary.value,
		title: 'Progress',
		subtitle: 'Avg progress & completion rate by period',
		xAxis: { key: 'period', type: 'category', title: 'Period' },
		yAxis: { title: '%' },
		series: [
			{ name: 'avg_progress', type: 'line', showDataPoints: true },
			{ name: 'completion_rate', type: 'line', showDataPoints: true },
		],
	}
})

const employeesChartConfig = computed(() => {
	if (!periodSummary.value) return null
	return {
		data: periodSummary.value,
		title: 'Employees',
		subtitle: 'Employees enrolled by period',
		xAxis: { key: 'period', type: 'category', title: 'Period' },
		yAxis: { title: 'Employees' },
		series: [{ name: 'employees', type: 'bar' }],
	}
})

const signupsChartConfig = computed(() => {
	if (!signupsChart.data) return null
	return {
		data: signupsChart.data,
		title: 'Signups',
		subtitle: 'Signups per day',
		xAxis: { key: 'date', type: 'time', title: 'Date', timeGrain: 'day' },
		yAxis: { title: 'Signups' },
		series: [{ name: 'signups', type: 'line', showDataPoints: true }],
	}
})

const enrollmentChartConfig = computed(() => {
	let data = canViewDepartmentReport.value ? periodSummary.value : enrollmentChart.data
	if (!data) return null
	return {
		data,
		title: 'Enrollments',
		subtitle: canViewDepartmentReport.value
			? 'Enrollments by period'
			: 'Enrollments per day',
		xAxis: enrollmentXAxis.value,
		yAxis: { title: 'Enrollments' },
		series: [{ name: 'enrollments', type: 'line', showDataPoints: true }],
	}
})

const certificationChartConfig = computed(() => {
	let data = canViewDepartmentReport.value ? periodSummary.value : certification.data
	if (!data) return null
	return {
		data,
		title: 'Certifications',
		subtitle: canViewDepartmentReport.value
			? 'Certifications by period'
			: 'Certifications per day',
		xAxis: enrollmentXAxis.value,
		yAxis: { title: 'Certifications' },
		series: [{ name: 'certifications', type: 'line', showDataPoints: true }],
	}
})

const donutChartConfig = computed(() => {
	let data
	if (canViewDepartmentReport.value && summary.value) {
		data = [
			{ label: 'Completed', value: summary.value.completions },
			{
				label: 'In Progress',
				value: summary.value.enrollments - summary.value.completions,
			},
		]
	} else {
		data = courseCompletion.data
	}
	if (!data) return null
	return {
		data,
		title: 'Completions',
		subtitle: 'Course Completion',
		categoryColumn: 'label',
		valueColumn: 'value',
	}
})

const departmentChartConfig = computed(() => {
	if (!departmentSummary.value) return null
	return {
		data: departmentSummary.value,
		title: 'Departments',
		subtitle: 'Enrollments by department',
		categoryColumn: 'department_name',
		valueColumn: 'enrollments',
	}
})

async function exportPdf() {
	exporting.value = true
	try {
		const { default: html2canvas } = await import('html2canvas')
		const { jsPDF } = await import('jspdf')

		const container = document.querySelector('.js-charts-export-container')
		if (!container) throw new Error('Export container not found')

		const clone = container.cloneNode(true)
		Object.assign(clone.style, {
			position: 'fixed',
			top: '-9999px',
			left: '-9999px',
			width: `${container.clientWidth}px`,
			background: '#fff',
		})
		document.body.appendChild(clone)
		await new Promise((resolve) => setTimeout(resolve, 600))

		const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })
		const pdfW = pdf.internal.pageSize.getWidth()
		const pdfH = pdf.internal.pageSize.getHeight()
		const margin = 10
		const gap = 6
		const headerH = 15
		const colW = (pdfW - margin * 2 - gap) / 2

		const drawHeader = () => {
			pdf.setFontSize(10)
			pdf.setTextColor(60, 60, 60)
			pdf.text(
				`Company: ${filters.company || 'All'}  |  Department: ${
					filters.department || 'All'
				}  |  Employee: ${filters.employee || 'All'}  |  Period: ${
					formatRange(filters.period) || presetLabel.value
				}`,
				margin,
				margin + 5
			)
			pdf.setDrawColor(220, 220, 220)
			pdf.line(margin, margin + headerH - 2, pdfW - margin, margin + headerH - 2)
		}

		drawHeader()
		let currentX = margin
		let currentY = margin + headerH
		let maxRowH = 0

		const chartElements = clone.querySelectorAll('.grid > .border.rounded-md')
		for (const el of Array.from(chartElements)) {
			const canvas = await html2canvas(el, {
				scale: 2.5,
				backgroundColor: '#ffffff',
				useCORS: true,
				logging: false,
			})
			const imgH = colW * (canvas.height / canvas.width)

			if (currentY + imgH > pdfH - margin) {
				pdf.addPage()
				drawHeader()
				currentX = margin
				currentY = margin + headerH
				maxRowH = 0
			}

			pdf.addImage(canvas.toDataURL('image/png'), 'PNG', currentX, currentY, colW, imgH)
			maxRowH = Math.max(maxRowH, imgH)
			currentX += colW + gap

			if (currentX + colW > pdfW) {
				currentX = margin
				currentY += maxRowH + gap
				maxRowH = 0
			}
		}

		document.body.removeChild(clone)
		pdf.save(`Department_Report_${dayjs().format('YYYY-MM-DD_HHmm')}.pdf`)
	} catch (err) {
		console.error('PDF Export Error:', err)
		alert(`Export failed: ${err.message}`)
	} finally {
		exporting.value = false
	}
}

const breadcrumbs = computed(() => {
	return [
		{
			label: 'Statistics',
			route: {
				name: 'Statistics',
			},
		},
	]
})

const chartDetails = createResource({
	url: 'lms.lms.api.get_chart_details',
	cache: ['statistics'],
	auto: true,
})

const signupsChart = createResource({
	url: 'lms.lms.utils.get_chart_data',
	auto: false,
	transform(data) {
		return data.map((item) => {
			return {
				date: new Date(item.date),
				signups: item.count,
			}
		})
	},
})

const enrollmentChart = createResource({
	url: 'lms.lms.utils.get_chart_data',
	auto: false,
	transform(data) {
		return data.map((item) => {
			return {
				date: new Date(item.date),
				enrollments: item.count,
			}
		})
	},
})

const certification = createResource({
	url: 'lms.lms.utils.get_chart_data',
	auto: false,
	transform(data) {
		return data.map((item) => {
			return {
				date: new Date(item.date),
				certifications: item.count,
			}
		})
	},
})

const courseCompletion = createResource({
	url: 'lms.lms.utils.get_course_completion_data',
	auto: false,
})

watch(
	[() => userResource.data, () => filters.period],
	([data]) => {
		if (!data) return
		let member = isStaffView.value ? undefined : data.name
		let [from_date, to_date] = (filters.period || '').split(',')
		signupsChart.reload({ chart_name: 'New Signups', member, from_date, to_date })
		enrollmentChart.reload({
			chart_name: 'Course Enrollments',
			member,
			from_date,
			to_date,
		})
		certification.reload({ chart_name: 'Certification', member, from_date, to_date })
		courseCompletion.reload({ member })
	},
	{ immediate: true }
)

const timeSpentGranularity = computed(() => {
	let [from, to] = (filters.period || '').split(',')
	if (!from || !to) return 'day'
	let days = dayjs(to).diff(dayjs(from), 'day')
	if (days <= 31) return 'day'
	if (days <= 120) return 'week'
	return 'month'
})

const timeSpent = createResource({
	url: 'lms.lms.api.get_time_spent_summary',
	auto: false,
})

watch(
	[() => filters.period, () => userResource.data],
	() => {
		if (!userResource.data) return
		let [from_date, to_date] = (filters.period || '').split(',')
		timeSpent.submit({
			from_date,
			to_date,
			granularity: timeSpentGranularity.value,
			member: isStaffView.value ? undefined : userResource.data.name,
		})
	},
	{ immediate: true }
)

const timeSpentChartConfig = computed(() => {
	if (!timeSpent.data) return null
	let data = timeSpent.data.map((row) => ({
		label: row.label,
		hours: +(row.seconds / 3600).toFixed(2),
	}))
	return {
		data,
		title: 'Time Spent',
		subtitle: isStaffView.value
			? 'Total hours studied across all students'
			: 'Your hours studied',
		xAxis: { key: 'label', type: 'category', title: 'Period' },
		yAxis: { title: 'Hours' },
		series: [{ name: 'hours', type: 'bar' }],
	}
})

usePageMeta(() => {
	return {
		title: __('Statistics'),
		icon: brand.favicon,
	}
})
</script>
