<template>
	<div
		class="group flex h-full flex-col overflow-hidden rounded-md border border-outline-gray-2 bg-surface-white transition-shadow duration-300 hover:shadow-md motion-reduce:transition-none"
	>
		<!-- Register strip: medium (Online/Offline) is the one structural fact
		always true of every batch, the equivalent of Program's Sequential/Open
		Track strip - plus a brass mark when the batch offers certification,
		matching the "officially recognised" meaning that color carries on
		course cards. -->
		<div
			class="flex items-center justify-between border-b border-outline-gray-2 px-3 py-1.5"
		>
			<span
				class="lms-batch-card__mono text-[10px] uppercase tracking-[0.12em] text-ink-gray-6"
			>
				{{
					batch.medium === 'Offline'
						? __('batches.card.offline')
						: __('batches.card.online')
				}}
			</span>
			<GraduationCap
				v-if="batch.certification"
				class="lms-batch-card__brass h-3 w-3 shrink-0 stroke-2"
			/>
		</div>

		<div class="relative h-[160px] w-full overflow-hidden">
			<div
				class="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-500 ease-out group-hover:scale-[1.05] motion-reduce:transition-none"
				:style="{ backgroundImage: getGradientColor() }"
			></div>
			<div
				class="relative flex h-full items-center justify-center px-6 text-center text-white"
			>
				<span class="lms-batch-card__serif leading-tight" :class="titleSize">
					{{ batch.title }}
				</span>
			</div>

			<Badge
				v-if="batch.seat_count && batch.seats_left > 0"
				theme="green"
				variant="solid"
				class="absolute right-2.5 top-2.5"
			>
				{{ batch.seats_left }}
				{{
					batch.seats_left > 1
						? __('batches.card.seatsLeft')
						: __('batches.card.seatLeft')
				}}
			</Badge>
			<Badge
				v-else-if="batch.seat_count && batch.seats_left <= 0"
				theme="red"
				variant="solid"
				class="absolute right-2.5 top-2.5"
			>
				{{ __('batches.card.soldOut') }}
			</Badge>
			<div
				v-if="!batch.published"
				:title="__('batches.card.private')"
				class="absolute left-2.5 top-2.5 flex h-7 w-7 items-center justify-center rounded-full bg-surface-white text-ink-gray-8 shadow-sm"
			>
				<Lock class="h-3.5 w-3.5 stroke-2" />
			</div>
		</div>

		<div class="flex flex-1 flex-col p-4">
			<div v-if="batch.amount" class="mb-1 text-right">
				<span class="lms-batch-card__mono text-sm font-medium text-ink-gray-8">
					{{ batch.price }}
				</span>
			</div>

			<div class="short-introduction text-sm text-ink-gray-6">
				{{ batch.description }}
			</div>

			<div
				class="lms-batch-card__mono mb-1 mt-3 flex flex-col gap-1.5 border-y border-outline-gray-1 py-2 text-[11px] text-ink-gray-6"
			>
				<DateRange :startDate="batch.start_date" :endDate="batch.end_date" />
				<div class="flex items-center gap-2">
					<Clock class="h-3.5 w-3.5 shrink-0 stroke-1.5" />
					<span>
						{{ formatTime(batch.start_time) }} - {{ formatTime(batch.end_time) }}
					</span>
				</div>
			</div>

			<div
				v-if="batch.instructors?.length"
				class="mt-auto flex avatar-group overlap pt-3"
			>
				<div
					class="h-6 mr-1"
					:class="{ 'avatar-group overlap': batch.instructors.length > 1 }"
				>
					<UserAvatar v-for="instructor in batch.instructors" :user="instructor" />
				</div>
				<CourseInstructors :instructors="batch.instructors" />
			</div>
		</div>
	</div>
</template>
<script setup>
import { Badge } from 'frappe-ui'
import { formatTime } from '@/utils'
import { Clock, GraduationCap, Lock } from 'lucide-vue-next'
import { computed } from 'vue'
import { theme } from '@/utils/theme'
import DateRange from '@/components/Common/DateRange.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import UserAvatar from '@/components/UserAvatar.vue'

const props = defineProps({
	batch: {
		type: Object,
		default: null,
	},
})

const titleSize = computed(() => {
	const title = props.batch?.title || ''
	if (title.length > 32) return 'text-lg'
	if (title.length > 20) return 'text-xl'
	return 'text-2xl'
})

const palette = ['blue', 'green', 'orange', 'red', 'purple', 'teal', 'pink']

const getGradientColor = () => {
	const key = props.batch?.title || ''
	let sum = 0
	for (let i = 0; i < key.length; i++) sum += key.charCodeAt(i)
	const color = palette[sum % palette.length]
	const colorMap = theme.backgroundColor[color] || theme.backgroundColor.blue
	return `radial-gradient(ellipse 140% 100% at 100% 0%, ${colorMap[300]} 0%, ${colorMap[600]} 45%, #16222e 100%)`
}
</script>
<style scoped>
.lms-batch-card__serif {
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

.lms-batch-card__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
	font-variant-numeric: tabular-nums;
}

.lms-batch-card__brass {
	color: #9c7a3c;
}
</style>
<style>
.short-introduction {
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	text-overflow: ellipsis;
	width: 100%;
	overflow: hidden;
	margin: 0.25rem 0 1rem;
	line-height: 1.5;
}

.avatar-group {
	display: inline-flex;
	align-items: center;
}

.avatar-group .avatar {
	transition: margin 0.1s ease-in-out;
}

.avatar-group.overlap .avatar + .avatar {
	margin-left: calc(-8px);
}
</style>
