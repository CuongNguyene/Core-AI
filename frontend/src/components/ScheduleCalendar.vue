<template>
	<div class="border rounded-md">
		<div class="flex flex-col lg:flex-row">
			<div class="lg:w-72 shrink-0 border-b lg:border-b-0 lg:border-r p-4">
				<div class="flex items-center justify-between mb-3">
					<button
						class="p-1 rounded hover:bg-surface-gray-2 text-ink-gray-6"
						@click="goToMonth(-1)"
					>
						<ChevronLeft class="size-4 stroke-1.5" />
					</button>
					<span class="font-semibold text-sm text-ink-gray-9">
						{{ currentMonth.format('MMMM YYYY') }}
					</span>
					<button
						class="p-1 rounded hover:bg-surface-gray-2 text-ink-gray-6"
						@click="goToMonth(1)"
					>
						<ChevronRight class="size-4 stroke-1.5" />
					</button>
				</div>
				<div
					class="grid grid-cols-7 gap-y-1 text-center text-[11px] text-ink-gray-5 mb-1"
				>
					<span v-for="d in weekDayLabels">{{ d }}</span>
				</div>
				<div class="grid grid-cols-7 gap-y-1 text-center">
					<button
						v-for="cell in calendarCells"
						:key="cell.dateStr"
						class="relative flex flex-col items-center justify-center size-8 mx-auto rounded-full text-xs focus:outline-none focus-visible:ring focus-visible:ring-outline-gray-3"
						:class="[
							cell.isCurrentMonth ? 'text-ink-gray-8' : 'text-ink-gray-3',
							cell.dateStr === selectedDate
								? 'bg-surface-gray-7 text-ink-white'
								: cell.isToday
									? 'bg-surface-gray-3'
									: 'hover:bg-surface-gray-2',
						]"
						@click="selectDate(cell.dateStr)"
					>
						{{ cell.day }}
						<span
							v-if="cell.hasEvents"
							class="absolute bottom-0.5 size-1 rounded-full"
							:class="
								cell.dateStr === selectedDate
									? 'bg-surface-white'
									: 'bg-surface-blue-2'
							"
						/>
					</button>
				</div>
				<button
					v-if="selectedDate"
					class="text-xs text-ink-gray-5 hover:text-ink-gray-7 mt-3"
					@click="selectedDate = null"
				>
					{{ __('home.schedule.clearSelection') }}
				</button>
			</div>

			<div class="flex-1 p-4 min-w-0">
				<div class="font-semibold text-sm text-ink-gray-9 mb-3">
					{{
						selectedDate
							? formatSelectedDate(selectedDate)
							: __('home.schedule.upcoming')
					}}
				</div>

				<div v-if="scheduleResource.loading" class="text-sm text-ink-gray-5">
					{{ __('home.schedule.loading') }}
				</div>
				<div
					v-else-if="!displayedEvents.length"
					class="text-sm text-ink-gray-5"
				>
					{{ __('home.schedule.noEvents') }}
				</div>
				<div v-else class="space-y-2">
					<component
						:is="event.url ? 'a' : 'div'"
						v-for="event in displayedEvents"
						:key="event.reference_docname + event.date + event.start_time"
						:href="event.url || undefined"
						:target="event.url ? '_blank' : undefined"
						class="flex items-center gap-3 p-2 rounded-md border"
						:class="event.url ? 'hover:bg-surface-gray-1 cursor-pointer' : ''"
					>
						<div
							class="w-1 self-stretch rounded-full shrink-0"
							:class="eventTypeColor(event.type).bar"
						/>
						<div class="flex-1 min-w-0">
							<div class="text-sm font-medium text-ink-gray-9 truncate">
								{{ event.title }}
							</div>
							<div class="text-xs text-ink-gray-5 truncate">
								{{ event.batch_title }}
							</div>
						</div>
						<div class="text-right shrink-0">
							<span
								class="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded"
								:class="eventTypeColor(event.type).badge"
							>
								{{ event.type }}
							</span>
							<div class="text-xs text-ink-gray-6 mt-1">
								{{ !selectedDate ? formatEventDate(event.date) + ', ' : '' }}
								{{ event.start_time ? formatTime(event.start_time) : '' }}
							</div>
						</div>
					</component>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { createResource } from 'frappe-ui'
import dayjs from 'dayjs/esm'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { formatTime, capitalize } from '@/utils'

const props = defineProps<{
	endpoint: string
}>()

const currentMonth = ref(dayjs().startOf('month'))
const selectedDate = ref<string | null>(null)

const scheduleResource = createResource({
	url: props.endpoint,
	params: {
		from_date: currentMonth.value.startOf('month').format('YYYY-MM-DD'),
		to_date: currentMonth.value.endOf('month').format('YYYY-MM-DD'),
	},
	auto: true,
})

watch(currentMonth, () => {
	scheduleResource.update({
		params: {
			from_date: currentMonth.value.startOf('month').format('YYYY-MM-DD'),
			to_date: currentMonth.value.endOf('month').format('YYYY-MM-DD'),
		},
	})
	scheduleResource.reload()
})

const goToMonth = (offset: number) => {
	currentMonth.value = currentMonth.value.add(offset, 'month')
	selectedDate.value = null
}

const selectDate = (dateStr: string) => {
	selectedDate.value = selectedDate.value === dateStr ? null : dateStr
}

const formatSelectedDate = (dateStr: string) => {
	const date = dayjs(dateStr)
	const yearSuffix = date.year() === dayjs().year() ? '' : ', YYYY'
	return capitalize(date.format(`dddd, D MMMM${yearSuffix}`))
}

const formatEventDate = (dateStr: string) => {
	const date = dayjs(dateStr)
	const yearSuffix = date.year() === dayjs().year() ? '' : ', YYYY'
	return capitalize(date.format(`D MMMM${yearSuffix}`))
}

const weekDayLabels = ['S', 'M', 'T', 'W', 'T', 'F', 'S']

const eventsByDate = computed(() => {
	const map: Record<string, any[]> = {}
	for (const event of scheduleResource.data || []) {
		if (!map[event.date]) map[event.date] = []
		map[event.date].push(event)
	}
	return map
})

const calendarCells = computed(() => {
	const startOfMonth = currentMonth.value.startOf('month')
	const endOfMonth = currentMonth.value.endOf('month')
	const startOfGrid = startOfMonth.subtract(startOfMonth.day(), 'day')
	const totalCells = 42
	const today = dayjs().format('YYYY-MM-DD')

	const cells = []
	for (let i = 0; i < totalCells; i++) {
		const date = startOfGrid.add(i, 'day')
		const dateStr = date.format('YYYY-MM-DD')
		cells.push({
			dateStr,
			day: date.date(),
			isCurrentMonth: date.isSame(currentMonth.value, 'month'),
			isToday: dateStr === today,
			hasEvents: !!eventsByDate.value[dateStr]?.length,
		})
		if (i >= 34 && date.isAfter(endOfMonth) && date.day() === 6) break
	}
	return cells
})

const displayedEvents = computed(() => {
	if (selectedDate.value) {
		return eventsByDate.value[selectedDate.value] || []
	}
	const today = dayjs().format('YYYY-MM-DD')
	return (scheduleResource.data || [])
		.filter((event: any) => event.date >= today)
		.slice(0, 8)
})

const eventTypeColor = (type: string) => {
	const colors: Record<string, { bar: string; badge: string }> = {
		Session: {
			bar: 'bg-surface-blue-2',
			badge: 'bg-surface-blue-1 text-ink-blue-3',
		},
		Milestone: {
			bar: 'bg-surface-gray-5',
			badge: 'bg-surface-gray-2 text-ink-gray-7',
		},
		'Live Class': {
			bar: 'bg-surface-green-3',
			badge: 'bg-surface-green-1 text-ink-green-3',
		},
		Evaluation: {
			bar: 'bg-surface-amber-2',
			badge: 'bg-surface-amber-1 text-ink-amber-3',
		},
	}
	return colors[type] || colors.Session
}
</script>
