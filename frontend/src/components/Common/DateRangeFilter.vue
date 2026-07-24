<template>
	<div>
		<div v-if="label" class="text-xs text-ink-gray-5 mb-1">{{ label }}</div>
		<Dropdown v-if="!showDatePicker" :options="rangeOptions" class="w-full">
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
			:modelValue="modelValue"
			placeholder="Period"
			:formatter="formatRange"
			@update:modelValue="onDateRangeUpdate"
		>
			<template #prefix>
				<Calendar class="size-4 text-ink-gray-5 mr-2" />
			</template>
		</DateRangePicker>
	</div>
</template>
<script setup>
import { DateRangePicker, Dropdown, dayjs } from 'frappe-ui'
import { Calendar, ChevronDown } from 'lucide-vue-next'
import { ref, watch } from 'vue'

const props = defineProps({
	modelValue: {
		type: String,
		default: '',
	},
	label: {
		type: String,
		default: '',
	},
})
const emit = defineEmits(['update:modelValue'])

const showDatePicker = ref(false)
const datePickerRef = ref(null)

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

const rangePresets = {
	0: 'Today',
	7: 'Last 7 Days',
	30: 'Last 30 Days',
	60: 'Last 60 Days',
	90: 'Last 90 Days',
}

function presetLabelFor(period) {
	if (!period) return __('Custom Range')
	let [from, to] = period.split(',')
	if (!from || !to) return period
	let diffDays = dayjs(to).diff(dayjs(from), 'day')
	return rangePresets[diffDays] ? __(rangePresets[diffDays]) : formatRange(period)
}

const presetLabel = ref(presetLabelFor(props.modelValue))

watch(
	() => props.modelValue,
	(val) => {
		presetLabel.value = presetLabelFor(val)
	}
)

function applyPreset(label, period) {
	presetLabel.value = label
	showDatePicker.value = false
	emit('update:modelValue', period)
}

const rangeOptions = [
	{
		group: 'Presets',
		hideLabel: true,
		items: [
			{ label: __('Today'), onClick: () => applyPreset(__('Today'), getLastXDays(0)) },
			{
				label: __('Last 7 Days'),
				onClick: () => applyPreset(__('Last 7 Days'), getLastXDays(7)),
			},
			{
				label: __('Last 30 Days'),
				onClick: () => applyPreset(__('Last 30 Days'), getLastXDays(30)),
			},
			{
				label: __('Last 60 Days'),
				onClick: () => applyPreset(__('Last 60 Days'), getLastXDays(60)),
			},
			{
				label: __('Last 90 Days'),
				onClick: () => applyPreset(__('Last 90 Days'), getLastXDays(90)),
			},
		],
	},
	{
		label: __('Custom Range'),
		onClick: () => {
			presetLabel.value = __('Custom Range')
			showDatePicker.value = true
			setTimeout(() => datePickerRef.value?.open(), 0)
		},
	},
]

function onDateRangeUpdate(range) {
	showDatePicker.value = false
	presetLabel.value = presetLabelFor(range)
	emit('update:modelValue', range)
}

defineExpose({ getLastXDays })
</script>
