<template>
	<div class="">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-2 bg-surface-white/90 backdrop-blur-md px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<Button
				:label="__('statistics.export')"
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
					<div class="text-xs text-ink-gray-5 mb-1">{{ __('statistics.dateRange') }}</div>
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
						:placeholder="__('statistics.period')"
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
					:label="__('statistics.company')"
					:placeholder="__('statistics.allCompanies')"
					doctype="Company"
				/>
				<Link
					v-model="filters.department"
					:label="__('statistics.department')"
					:placeholder="__('statistics.allDepartments')"
					doctype="Department"
					:filters="departmentFilters"
				/>
				<Link
					v-model="filters.employee"
					:label="__('statistics.employee')"
					:placeholder="__('statistics.allEmployees')"
					doctype="Employee"
					:filters="employeeFilters"
				/>
			</div>
			<div v-else class="max-w-56 mb-4">
				<DateRangeFilter v-model="filters.period" :label="__('statistics.dateRange')" />
			</div>

			<div
				class="grid grid-cols-1 md:grid-cols-2 gap-4"
				:class="isStaffView ? 'lg:grid-cols-5' : 'lg:grid-cols-4'"
			>
				<Tooltip v-if="isStaffView" :text="__('statistics.tapForDetails')">
					<NumberChart
						class="border rounded-md cursor-pointer hover:border-outline-gray-3"
						:config="{
							title: __('statistics.courses'),
							value: summary?.courses ?? chartDetails.data.courses,
						}"
						@click="openDetail('courses', __('statistics.courses'))"
					/>
				</Tooltip>
				<Tooltip :text="__('statistics.tapForDetails')">
					<NumberChart
						class="border rounded-md cursor-pointer hover:border-outline-gray-3"
						:config="{
							title: __('statistics.enrollments'),
							value: isStaffView
								? summary?.enrollments ?? chartDetails.data.enrollments
								: myStats.data?.enrollments ?? 0,
						}"
						@click="openDetail('enrollments', __('statistics.enrollments'))"
					/>
				</Tooltip>
				<Tooltip :text="__('statistics.tapForDetails')">
					<NumberChart
						class="border rounded-md cursor-pointer hover:border-outline-gray-3"
						:config="{
							title: __('statistics.completions'),
							value: isStaffView
								? summary?.completions ?? chartDetails.data.completions
								: myStats.data?.completions ?? 0,
						}"
						@click="openDetail('completions', __('statistics.completions'))"
					/>
				</Tooltip>
				<Tooltip :text="__('statistics.tapForDetails')">
					<NumberChart
						class="border rounded-md cursor-pointer hover:border-outline-gray-3"
						:config="{
							title: __('statistics.certifications'),
							value: isStaffView
								? summary?.certifications ?? chartDetails.data.certifications
								: myStats.data?.certifications ?? 0,
						}"
						@click="openDetail('certifications', __('statistics.certifications'))"
					/>
				</Tooltip>
				<Tooltip :text="__('statistics.tapForDetails')">
					<NumberChart
						class="border rounded-md cursor-pointer hover:border-outline-gray-3"
						:config="{
							title: __('statistics.timeSpentLearning'),
							value: isStaffView
								? summary?.time_spent_hours ?? chartDetails.data.time_spent_hours
								: totalTimeSpentHours,
							suffix: __('statistics.hoursSuffix'),
						}"
						@click="openDetail('time_spent', __('statistics.timeSpentLearning'))"
					/>
				</Tooltip>
			</div>

			<StatDetailModal
				v-model="showDetailModal"
				:metric="selectedMetric"
				:title="selectedTitle"
				:scope="detailScope"
				:department="filters.department"
				:employee="filters.employee"
				:company="filters.company"
				:from-date="detailFromDate"
				:to-date="detailToDate"
			/>
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

			<div v-if="canViewDepartmentReport" class="mt-4">
				<div class="lms-statistics__serif text-base text-ink-gray-9 mb-2">
					{{ __('statistics.recognition') }}
				</div>
				<RecognitionPanel
					:top-learners="topLearners"
					:department-ranking="departmentRanking"
				/>
			</div>
		</div>

		<Dialog
			v-model="showExportModal"
			:options="{ title: __('statistics.exportDashboardReport'), size: '5xl' }"
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
						<div v-if="canViewDepartmentReport" class="mt-4">
							<div class="lms-statistics__serif text-base text-ink-gray-9 mb-2">
								{{ __('statistics.recognition') }}
							</div>
							<RecognitionPanel
								:top-learners="topLearners"
								:department-ranking="departmentRanking"
							/>
						</div>
					</div>
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('statistics.cancel')" @click="showExportModal = false" />
					<Button
						:label="__('statistics.exportPdf')"
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
import StatDetailModal from '@/components/Modals/StatDetailModal.vue'
import RecognitionPanel from '@/components/RecognitionPanel.vue'
import { capitalize } from '@/utils'

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
	return `${capitalize(dayjs(from).format('D MMMM'))} - ${capitalize(dayjs(to).format('D MMMM YYYY'))}`
}

const rangePresets = {
	0: () => __('statistics.today'),
	7: () => __('statistics.last7Days'),
	30: () => __('statistics.last30Days'),
	60: () => __('statistics.last60Days'),
	90: () => __('statistics.last90Days'),
}

function presetLabelFor(period) {
	if (!period) return __('statistics.customRange')
	let [from, to] = period.split(',')
	if (!from || !to) return period
	let diffDays = dayjs(to).diff(dayjs(from), 'day')
	return rangePresets[diffDays]?.() || formatRange(period)
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
		group: __('statistics.presets'),
		hideLabel: true,
		items: [
			{ label: __('statistics.today'), onClick: () => applyPreset(__('statistics.today'), getLastXDays(0)) },
			{ label: __('statistics.last7Days'), onClick: () => applyPreset(__('statistics.last7Days'), getLastXDays(7)) },
			{ label: __('statistics.last30Days'), onClick: () => applyPreset(__('statistics.last30Days'), getLastXDays(30)) },
			{ label: __('statistics.last60Days'), onClick: () => applyPreset(__('statistics.last60Days'), getLastXDays(60)) },
			{ label: __('statistics.last90Days'), onClick: () => applyPreset(__('statistics.last90Days'), getLastXDays(90)) },
		],
	},
	{
		label: __('statistics.customRange'),
		onClick: () => {
			presetLabel.value = __('statistics.customRange')
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

const recognitionReport = createResource({
	url: 'lms.lms.api.get_learning_recognition',
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
	recognitionReport.submit({
		company: filters.company,
		department: filters.department,
		employee: filters.employee,
		from_date,
		to_date,
	})
}

const summary = computed(() => departmentReport.data?.summary)
const periodSummary = computed(() => departmentReport.data?.period_summary)
const departmentSummary = computed(() => departmentReport.data?.department_summary)
const topLearners = computed(() => recognitionReport.data?.top_learners || [])
const departmentRanking = computed(() => recognitionReport.data?.department_ranking || [])

const enrollmentXAxis = computed(() => {
	return canViewDepartmentReport.value
		? { key: 'period', type: 'category', title: __('statistics.period') }
		: { key: 'date', type: 'time', title: __('statistics.date'), timeGrain: 'day' }
})

const progressChartConfig = computed(() => {
	if (!periodSummary.value) return null
	return {
		data: periodSummary.value,
		title: __('statistics.progress'),
		subtitle: __('statistics.avgProgressSubtitle'),
		xAxis: { key: 'period', type: 'category', title: __('statistics.period') },
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
		title: __('statistics.employees'),
		subtitle: __('statistics.employeesSubtitle'),
		xAxis: { key: 'period', type: 'category', title: __('statistics.period') },
		yAxis: { title: __('statistics.employees') },
		series: [{ name: 'employees', type: 'bar' }],
	}
})

const signupsChartConfig = computed(() => {
	if (!signupsChart.data) return null
	return {
		data: signupsChart.data,
		title: __('statistics.signups'),
		subtitle: __('statistics.signupsSubtitle'),
		xAxis: { key: 'date', type: 'time', title: __('statistics.date'), timeGrain: 'day' },
		yAxis: { title: __('statistics.signups') },
		series: [{ name: 'signups', type: 'line', showDataPoints: true }],
	}
})

const enrollmentChartConfig = computed(() => {
	let data = canViewDepartmentReport.value ? periodSummary.value : enrollmentChart.data
	if (!data) return null
	return {
		data,
		title: __('statistics.enrollments'),
		subtitle: canViewDepartmentReport.value
			? __('statistics.enrollmentsByPeriod')
			: __('statistics.enrollmentsPerDay'),
		xAxis: enrollmentXAxis.value,
		yAxis: { title: __('statistics.enrollments') },
		series: [{ name: 'enrollments', type: 'line', showDataPoints: true }],
	}
})

const certificationChartConfig = computed(() => {
	let data = canViewDepartmentReport.value ? periodSummary.value : certification.data
	if (!data) return null
	return {
		data,
		title: __('statistics.certifications'),
		subtitle: canViewDepartmentReport.value
			? __('statistics.certificationsByPeriod')
			: __('statistics.certificationsPerDay'),
		xAxis: enrollmentXAxis.value,
		yAxis: { title: __('statistics.certifications') },
		series: [{ name: 'certifications', type: 'line', showDataPoints: true }],
	}
})

const donutChartConfig = computed(() => {
	let data
	if (canViewDepartmentReport.value && summary.value) {
		data = [
			{ label: __('statistics.completed'), value: summary.value.completions },
			{
				label: __('statistics.inProgress'),
				value: summary.value.enrollments - summary.value.completions,
			},
		]
	} else {
		data = courseCompletion.data
	}
	if (!data) return null
	return {
		data,
		title: __('statistics.completions'),
		subtitle: __('statistics.courseCompletion'),
		categoryColumn: 'label',
		valueColumn: 'value',
	}
})

const departmentChartConfig = computed(() => {
	if (!departmentSummary.value) return null
	return {
		data: departmentSummary.value,
		title: __('statistics.departments'),
		subtitle: __('statistics.enrollmentsByDepartment'),
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
				__('statistics.pdfHeader').format(
					filters.company || __('statistics.all'),
					filters.department || __('statistics.all'),
					filters.employee || __('statistics.all'),
					formatRange(filters.period) || presetLabel.value
				),
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
			label: __('statistics.title'),
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

const showDetailModal = ref(false)
const selectedMetric = ref('courses')
const selectedTitle = ref('')

// Mirrors the same three-way split already used for the tile values
// themselves (summary vs chartDetails vs myStats) so the drill-down modal
// always matches what the tile it was opened from is showing.
const detailScope = computed(() => {
	if (!isStaffView.value) return 'mine'
	return canViewDepartmentReport.value ? 'department' : 'global'
})

const detailFromDate = computed(() => (filters.period || '').split(',')[0] || '')
const detailToDate = computed(() => (filters.period || '').split(',')[1] || '')

function openDetail(metric, title) {
	selectedMetric.value = metric
	selectedTitle.value = title
	showDetailModal.value = true
}

// Derived from the same time-log data as the chart below, rather than a
// separate API call, so the number tile always agrees with what the chart
// shows for the current filters/date range.
const totalTimeSpentHours = computed(() => {
	if (!timeSpent.data) return 0
	let totalSeconds = timeSpent.data.reduce((sum, row) => sum + row.seconds, 0)
	return +(totalSeconds / 3600).toFixed(1)
})

const timeSpentChartConfig = computed(() => {
	if (!timeSpent.data) return null
	let data = timeSpent.data.map((row) => ({
		label: row.label,
		hours: +(row.seconds / 3600).toFixed(2),
	}))
	return {
		data,
		title: __('statistics.timeSpent'),
		subtitle: isStaffView.value
			? __('statistics.totalHoursStudied')
			: __('statistics.yourHoursStudied'),
		xAxis: { key: 'label', type: 'category', title: __('statistics.period') },
		yAxis: { title: __('statistics.hours') },
		series: [{ name: 'hours', type: 'bar' }],
	}
})

usePageMeta(() => {
	return {
		title: __('statistics.title'),
		icon: brand.favicon,
	}
})
</script>
<style scoped>
.lms-statistics__serif {
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
