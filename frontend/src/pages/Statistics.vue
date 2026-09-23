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
					<div class="text-xs text-ink-gray-5 mb-1">
						{{ __('statistics.dateRange') }}
					</div>
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
				<DateRangeFilter
					v-model="filters.period"
					:label="__('statistics.dateRange')"
				/>
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
								? (summary?.enrollments ?? chartDetails.data.enrollments)
								: (myStats.data?.enrollments ?? 0),
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
								? (summary?.completions ?? chartDetails.data.completions)
								: (myStats.data?.completions ?? 0),
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
								? (summary?.certifications ?? chartDetails.data.certifications)
								: (myStats.data?.certifications ?? 0),
						}"
						@click="
							openDetail('certifications', __('statistics.certifications'))
						"
					/>
				</Tooltip>
				<Tooltip :text="__('statistics.tapForDetails')">
					<NumberChart
						class="border rounded-md cursor-pointer hover:border-outline-gray-3"
						:config="{
							title: __('statistics.timeSpentLearning'),
							value: isStaffView
								? (summary?.time_spent_hours ??
									chartDetails.data.time_spent_hours)
								: totalTimeSpentHours,
							suffix: __('statistics.hoursSuffix'),
						}"
						@click="
							openDetail('time_spent', __('statistics.timeSpentLearning'))
						"
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
			</div>

			<div class="mt-4">
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

		<Dialog v-model="showExportModal" :options="{ size: '5xl' }">
			<template #body-title>
				<h3 class="lms-statistics__serif text-2xl leading-6 text-ink-gray-9">
					{{ __('statistics.exportDashboardReport') }}
				</h3>
			</template>
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
								<AxisChart
									v-if="signupsChartConfig"
									:config="signupsChartConfig"
								/>
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
								<DonutChart
									v-if="donutChartConfig"
									:config="donutChartConfig"
								/>
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
					<Button
						:label="__('statistics.cancel')"
						@click="showExportModal = false"
					/>
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
	() => !!userResource.data?.can_view_department_report,
)

const canViewTimeSpent = computed(
	() =>
		userResource.data?.is_moderator ||
		userResource.data?.is_instructor ||
		userResource.data?.is_system_manager,
)

const isStaffView = computed(
	() => canViewTimeSpent.value || canViewDepartmentReport.value,
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
	},
)

watch(
	() => filters.department,
	() => {
		filters.employee = ''
	},
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
			{
				label: __('statistics.today'),
				onClick: () => applyPreset(__('statistics.today'), getLastXDays(0)),
			},
			{
				label: __('statistics.last7Days'),
				onClick: () => applyPreset(__('statistics.last7Days'), getLastXDays(7)),
			},
			{
				label: __('statistics.last30Days'),
				onClick: () =>
					applyPreset(__('statistics.last30Days'), getLastXDays(30)),
			},
			{
				label: __('statistics.last60Days'),
				onClick: () =>
					applyPreset(__('statistics.last60Days'), getLastXDays(60)),
			},
			{
				label: __('statistics.last90Days'),
				onClick: () =>
					applyPreset(__('statistics.last90Days'), getLastXDays(90)),
			},
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
	{ immediate: true },
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
const departmentSummary = computed(
	() => departmentReport.data?.department_summary,
)
const topLearners = computed(() => recognitionReport.data?.top_learners || [])
const departmentRanking = computed(
	() => recognitionReport.data?.department_ranking || [],
)

const enrollmentXAxis = computed(() => {
	return canViewDepartmentReport.value
		? { key: 'period', type: 'category', title: __('statistics.period') }
		: {
				key: 'date',
				type: 'time',
				title: __('statistics.date'),
				timeGrain: 'day',
			}
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
		xAxis: {
			key: 'date',
			type: 'time',
			title: __('statistics.date'),
			timeGrain: 'day',
		},
		yAxis: { title: __('statistics.signups') },
		series: [{ name: 'signups', type: 'line', showDataPoints: true }],
	}
})

const enrollmentChartConfig = computed(() => {
	let data = canViewDepartmentReport.value
		? periodSummary.value
		: enrollmentChart.data
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
	let data = canViewDepartmentReport.value
		? periodSummary.value
		: certification.data
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

async function chartSvgToCanvas(svg) {
	const { width, height } = svg.getBoundingClientRect()
	if (!width || !height) throw new Error('Chart has no visible size')

	const svgMarkup = new XMLSerializer().serializeToString(svg)
	const svgBlob = new Blob([svgMarkup], { type: 'image/svg+xml;charset=utf-8' })
	const svgUrl = URL.createObjectURL(svgBlob)

	try {
		const image = await new Promise((resolve, reject) => {
			const chartImage = new Image()
			chartImage.onload = () => resolve(chartImage)
			chartImage.onerror = () => reject(new Error('Could not render chart image'))
			chartImage.src = svgUrl
		})

		const scale = 2
		const canvas = document.createElement('canvas')
		canvas.width = Math.ceil(width * scale)
		canvas.height = Math.ceil(height * scale)
		const context = canvas.getContext('2d')
		if (!context) throw new Error('Could not create export canvas')

		context.fillStyle = '#ffffff'
		context.fillRect(0, 0, canvas.width, canvas.height)
		context.drawImage(image, 0, 0, canvas.width, canvas.height)
		return canvas
	} finally {
		URL.revokeObjectURL(svgUrl)
	}
}

async function exportPdf() {
	exporting.value = true
	try {
		const { jsPDF } = await import('jspdf')

		const container = document.querySelector('.js-charts-export-container')
		if (!container) throw new Error('Export container not found')
		const chartSvgs = container.querySelectorAll('.grid > .border.rounded-md svg')
		if (!chartSvgs.length) throw new Error('No charts are ready to export')

		const pdf = new jsPDF({
			orientation: 'landscape',
			unit: 'mm',
			format: 'a4',
		})
		const pdfW = pdf.internal.pageSize.getWidth()
		const pdfH = pdf.internal.pageSize.getHeight()
		const margin = 10
		const gap = 6
		const colW = (pdfW - margin * 2 - gap) / 2
		const reportTitle = brand.name || 'LMS'
		const reportPeriod = formatRange(filters.period) || presetLabel.value
		const reportScope = canViewDepartmentReport.value
			? [filters.company || __('statistics.all'), filters.department || __('statistics.all')].join(
					' / '
				)
			: __('statistics.all')
		const metrics = [
			...(isStaffView.value
				? [
						{
							label: __('statistics.courses'),
							value: summary.value?.courses ?? chartDetails.data.courses,
						},
					]
				: []),
			{
				label: __('statistics.enrollments'),
				value: isStaffView.value
					? (summary.value?.enrollments ?? chartDetails.data.enrollments)
					: (myStats.data?.enrollments ?? 0),
			},
			{
				label: __('statistics.completions'),
				value: isStaffView.value
					? (summary.value?.completions ?? chartDetails.data.completions)
					: (myStats.data?.completions ?? 0),
			},
			{
				label: __('statistics.certifications'),
				value: isStaffView.value
					? (summary.value?.certifications ?? chartDetails.data.certifications)
					: (myStats.data?.certifications ?? 0),
			},
			{
				label: __('statistics.timeSpentLearning'),
				value: `${
					isStaffView.value
						? (summary.value?.time_spent_hours ?? chartDetails.data.time_spent_hours)
						: totalTimeSpentHours.value
				}${__('statistics.hoursSuffix')}`,
			},
		]
		const chartMetadata = [
			...(canViewDepartmentReport.value
				? [
						{ title: progressChartConfig.value?.title, config: progressChartConfig.value },
						{ title: employeesChartConfig.value?.title, config: employeesChartConfig.value },
					]
				: isStaffView.value
					? [{ title: signupsChartConfig.value?.title, config: signupsChartConfig.value }]
					: []),
			{ title: enrollmentChartConfig.value?.title, config: enrollmentChartConfig.value },
			{ title: certificationChartConfig.value?.title, config: certificationChartConfig.value },
			{ title: donutChartConfig.value?.title, config: donutChartConfig.value },
			...(canViewDepartmentReport.value
				? [{ title: departmentChartConfig.value?.title, config: departmentChartConfig.value }]
				: []),
			{ title: __('statistics.timeSpentLearning'), config: timeSpentChartConfig.value },
		].filter((chart) => chart.config)

		const drawHeader = (includeSummary = false) => {
			pdf.setFillColor(24, 44, 75)
			pdf.rect(0, 0, pdfW, includeSummary ? 48 : 26, 'F')
			pdf.setTextColor(255, 255, 255)
			pdf.setFontSize(16)
			pdf.text(reportTitle, margin, 12)
			pdf.setFontSize(9)
			pdf.text(__('statistics.exportDashboardReport'), margin, 19)
			pdf.setTextColor(52, 68, 91)
			pdf.setFillColor(241, 245, 249)
			pdf.roundedRect(margin, includeSummary ? 31 : 31, pdfW - margin * 2, 12, 2, 2, 'F')
			pdf.setFontSize(8)
			pdf.text(`${__('statistics.dateRange')}: ${reportPeriod}`, margin + 4, includeSummary ? 38 : 38)
			pdf.text(`${__('statistics.department')}: ${reportScope}`, pdfW / 2, includeSummary ? 38 : 38)
			return includeSummary ? 52 : 48
		}

		let currentY = drawHeader(true)
		const metricGap = 4
		const metricW = (pdfW - margin * 2 - metricGap * (metrics.length - 1)) / metrics.length
		metrics.forEach((metric, index) => {
			const x = margin + index * (metricW + metricGap)
			pdf.setFillColor(248, 250, 252)
			pdf.setDrawColor(226, 232, 240)
			pdf.roundedRect(x, currentY, metricW, 22, 2, 2, 'FD')
			pdf.setTextColor(100, 116, 139)
			pdf.setFontSize(7)
			pdf.text(metric.label, x + 3, currentY + 7)
			pdf.setTextColor(15, 23, 42)
			pdf.setFontSize(14)
			pdf.text(String(metric.value ?? 0), x + 3, currentY + 17)
		})
		currentY += 31
		pdf.setTextColor(15, 23, 42)
		pdf.setFontSize(11)
		pdf.text(__('statistics.title'), margin, currentY)
		currentY += 5

		let currentX = margin
		let maxRowH = 0
		const panelH = 92

		for (const [index, svg] of Array.from(chartSvgs).entries()) {
			const canvas = await chartSvgToCanvas(svg)
			const chart = chartMetadata[index]

			if (currentY + panelH > pdfH - margin - 8) {
				pdf.addPage()
				currentY = drawHeader()
				currentX = margin
				maxRowH = 0
			}

			pdf.setFillColor(255, 255, 255)
			pdf.setDrawColor(203, 213, 225)
			pdf.roundedRect(currentX, currentY, colW, panelH, 2, 2, 'FD')
			pdf.setTextColor(30, 41, 59)
			pdf.setFontSize(9)
			pdf.text(chart?.title || __('statistics.title'), currentX + 4, currentY + 7)

			const maxImageW = colW - 8
			const maxImageH = panelH - 14
			const scale = Math.min(maxImageW / canvas.width, maxImageH / canvas.height)
			const imgW = canvas.width * scale
			const imgH = canvas.height * scale
			pdf.addImage(
				canvas.toDataURL('image/png'),
				'PNG',
				currentX + (colW - imgW) / 2,
				currentY + 10 + (maxImageH - imgH) / 2,
				imgW,
				imgH,
			)
			maxRowH = Math.max(maxRowH, panelH)
			currentX += colW + gap

			if (currentX + colW > pdfW) {
				currentX = margin
				currentY += maxRowH + gap
				maxRowH = 0
			}
		}

		const pageCount = pdf.getNumberOfPages()
		for (let page = 1; page <= pageCount; page++) {
			pdf.setPage(page)
			pdf.setTextColor(100, 116, 139)
			pdf.setFontSize(7)
			pdf.text(
				`${reportTitle} | ${dayjs().format('YYYY-MM-DD HH:mm')} | ${page}/${pageCount}`,
				margin,
				pdfH - 5,
			)
		}

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
		signupsChart.reload({
			chart_name: 'New Signups',
			member,
			from_date,
			to_date,
		})
		enrollmentChart.reload({
			chart_name: 'Course Enrollments',
			member,
			from_date,
			to_date,
		})
		certification.reload({
			chart_name: 'Certification',
			member,
			from_date,
			to_date,
		})
		courseCompletion.reload({ member })
	},
	{ immediate: true },
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
	{ immediate: true },
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

const detailFromDate = computed(
	() => (filters.period || '').split(',')[0] || '',
)
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
		'Source Serif 4', Georgia, 'Iowan Old Style', 'Palatino Linotype',
		'Book Antiqua', Palatino, serif;
	letter-spacing: -0.01em;
}
</style>
