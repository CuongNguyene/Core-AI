<template>
	<div
		class="flex flex-col border rounded-lg p-4 h-full transition-all duration-150 hover:border-outline-gray-3 hover:shadow-sm"
		style="min-height: 150px"
	>
		<div class="flex items-start justify-between gap-2 mb-1">
			<div class="line-clamp-2 text-lg leading-5 font-semibold text-ink-gray-9">
				{{ batch.title }}
			</div>
			<div
				v-if="batch.amount"
				class="shrink-0 text-sm font-semibold text-ink-gray-9"
			>
				{{ batch.price }}
			</div>
		</div>

		<div class="flex flex-wrap items-center gap-1.5 mb-2">
			<div
				v-if="batch.seat_count && batch.seats_left > 0"
				class="flex items-center gap-1 text-xs font-medium bg-green-100 text-green-700 px-2 py-0.5 rounded-full"
			>
				<Users class="h-3 w-3 stroke-2" />
				{{ batch.seats_left }}
				<span v-if="batch.seats_left > 1">
					{{ __('batches.card.seatsLeft') }}
				</span>
				<span v-else-if="batch.seats_left == 1">
					{{ __('batches.card.seatLeft') }}
				</span>
			</div>
			<div
				v-else-if="batch.seat_count && batch.seats_left <= 0"
				class="flex items-center gap-1 text-xs font-medium bg-red-100 text-red-700 px-2 py-0.5 rounded-full"
			>
				<Users class="h-3 w-3 stroke-2" />
				{{ __('batches.card.soldOut') }}
			</div>
			<div
				v-if="!batch.published"
				class="flex items-center gap-1 text-xs font-medium bg-gray-100 text-ink-gray-7 px-2 py-0.5 rounded-full"
			>
				<Lock class="h-3 w-3 stroke-2" />
				{{ __('batches.card.private') }}
			</div>
		</div>

		<div class="short-introduction text-sm text-ink-gray-7">
			{{ batch.description }}
		</div>

		<div class="flex flex-col space-y-2 mt-auto">
			<DateRange
				:startDate="batch.start_date"
				:endDate="batch.end_date"
				class="text-sm text-ink-gray-7"
			/>
			<div class="flex items-center text-sm text-ink-gray-7">
				<Clock class="h-4 w-4 stroke-1.5 mr-2 text-ink-gray-7 shrink-0" />
				<span>
					{{ formatTime(batch.start_time) }} - {{ formatTime(batch.end_time) }}
				</span>
			</div>
			<!-- <div
				v-if="batch.timezone"
				class="flex items-center text-sm text-ink-gray-7"
			>
				<Globe class="h-4 w-4 stroke-1.5 mr-2 text-ink-gray-5" />
				<span>
					{{ batch.timezone }}
				</span>
			</div> -->
		</div>
		<div
			v-if="batch.instructors?.length"
			class="flex avatar-group overlap mt-4 pt-3 border-t"
		>
			<div
				class="h-6 mr-1"
				:class="{ 'avatar-group overlap': batch.instructors.length > 1 }"
			>
				<UserAvatar
					v-for="instructor in batch.instructors"
					:user="instructor"
				/>
			</div>
			<CourseInstructors :instructors="batch.instructors" />
		</div>
	</div>
</template>
<script setup>
import { formatTime } from '@/utils'
import { Clock, Globe, Lock, Users } from 'lucide-vue-next'
import DateRange from '@/components/Common/DateRange.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import UserAvatar from '@/components/UserAvatar.vue'

const props = defineProps({
	batch: {
		type: Object,
		default: null,
	},
})
</script>
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
