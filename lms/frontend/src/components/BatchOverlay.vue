<template>
	<div
		v-if="batch.data"
		class="overflow-hidden rounded-md border border-outline-gray-2 lg:w-72"
	>
		<div
			class="flex items-center justify-between border-b border-outline-gray-2 px-4 py-2"
		>
			<span
				class="lms-batch-overlay__mono text-[10px] uppercase tracking-[0.12em] text-ink-gray-6"
			>
				{{
					batch.data.medium === 'Offline'
						? __('batches.card.offline')
						: __('batches.card.online')
				}}
			</span>
			<GraduationCap
				v-if="batch.data.certification"
				class="lms-batch-overlay__brass h-3 w-3 shrink-0 stroke-2"
			/>
		</div>

		<div class="p-5">
			<div class="mb-3 flex items-center justify-between gap-2">
				<div
					v-if="batch.data.amount"
					class="lms-batch-overlay__mono text-lg font-medium text-ink-gray-9"
				>
					{{ formatNumberIntoCurrency(batch.data.amount, batch.data.currency) }}
				</div>
				<Badge
					v-if="batch.data.seat_count && seats_left > 0"
					theme="green"
					variant="subtle"
				>
					{{ seats_left }}
					{{ seats_left > 1 ? __('batches.card.seatsLeft') : __('batches.card.seatLeft') }}
				</Badge>
				<Badge
					v-else-if="batch.data.seat_count && seats_left <= 0"
					theme="red"
					variant="subtle"
				>
					{{ __('batches.card.soldOut') }}
				</Badge>
			</div>

			<div
				class="lms-batch-overlay__mono mb-3 flex flex-col gap-2 border-y border-outline-gray-1 py-3 text-sm text-ink-gray-7"
			>
				<div v-if="batch.data.courses.length" class="flex items-center">
					<BookOpen class="h-4 w-4 stroke-1.5 mr-2" />
					<span> {{ batch.data.courses.length }} {{ __('batches.overlay.courses') }} </span>
				</div>
				<DateRange :startDate="batch.data.start_date" :endDate="batch.data.end_date" />
				<div class="flex items-center">
					<Clock class="h-4 w-4 stroke-1.5 mr-2" />
					<span>
						{{ formatTime(batch.data.start_time) }} -
						{{ formatTime(batch.data.end_time) }}
					</span>
				</div>
			</div>
			<!-- <div v-if="batch.data.timezone" class="flex items-center text-ink-gray-7">
				<Globe class="h-4 w-4 stroke-1.5 mr-2" />
				<span>
					{{ batch.data.timezone }}
				</span>
			</div> -->
		<div v-if="!readOnlyMode">
			<router-link
				v-if="canAccessBatch"
				:to="{
					name: 'Batch',
					params: {
						batchName: batch.data.name,
					},
				}"
			>
				<Button variant="solid" class="w-full mt-4">
					<template #prefix>
						<LogIn v-if="isStudent" class="size-4 stroke-1.5" />
						<Settings v-else class="size-4 stroke-1.5" />
					</template>
					<span>
						{{ isStudent ? __('batches.overlay.visitBatch') : __('batches.overlay.manageBatch') }}
					</span>
				</Button>
			</router-link>
			<router-link
				:to="{
					name: 'Billing',
					params: {
						type: 'batch',
						name: batch.data.name,
					},
				}"
				v-else-if="
					batch.data.paid_batch &&
					batch.data.seats_left > 0 &&
					batch.data.accept_enrollments
				"
			>
				<Button v-if="!isStudent" class="w-full mt-4" variant="solid">
					<template #prefix>
						<CreditCard class="size-4 stroke-1.5" />
					</template>
					<span>
						{{ __('batches.overlay.registerNow') }}
					</span>
				</Button>
			</router-link>
			<Button
				variant="solid"
				class="w-full mt-2"
				v-else-if="
					batch.data.allow_self_enrollment &&
					(!batch.data.seat_count || batch.data.seats_left > 0) &&
					batch.data.accept_enrollments
				"
				@click="enrollInBatch()"
			>
				<template #prefix>
					<GraduationCap class="size-4 stroke-1.5" />
				</template>
				{{ __('batches.overlay.enrollNow') }}
			</Button>
			<router-link
				v-if="isModerator"
				:to="{
					name: 'BatchForm',
					params: {
						batchName: batch.data.name,
					},
				}"
			>
				<Button class="w-full mt-2">
					<template #prefix>
						<Pencil class="size-4 stroke-1.5" />
					</template>
					<span>
						{{ __('batches.overlay.edit') }}
					</span>
				</Button>
			</router-link>
		</div>
	</div>
	</div>
</template>
<script setup>
import { inject, computed } from 'vue'
import { Badge, Button, createResource, toast } from 'frappe-ui'
import {
	BookOpen,
	Clock,
	CreditCard,
	Globe,
	GraduationCap,
	LogIn,
	Pencil,
	Settings,
} from 'lucide-vue-next'
import { formatNumberIntoCurrency, formatTime } from '@/utils'
import DateRange from '@/components/Common/DateRange.vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const user = inject('$user')
const readOnlyMode = window.read_only_mode

const props = defineProps({
	batch: {
		type: Object,
		default: null,
	},
})

const enroll = createResource({
	url: 'lms.lms.utils.enroll_in_batch',
	makeParams(values) {
		return {
			batch: props.batch.data.name,
		}
	},
})

const enrollInBatch = () => {
	if (!user.data) {
		window.location.href = `/login?redirect-to=/batches/details/${props.batch.data.name}`
	}
	enroll.submit(
		{},
		{
			onSuccess(data) {
				toast.success(__('batches.overlay.enrolledSuccess'))
				router.push({
					name: 'Batch',
					params: {
						batchName: props.batch.data.name,
					},
				})
			},
		}
	)
}

const seats_left = computed(() => {
	if (props.batch.data?.seat_count) {
		return props.batch.data?.seat_count - props.batch.data?.students?.length
	}
	return null
})

const isStudent = computed(() => {
	return props.batch.data?.students?.includes(user.data?.name)
})

const isModerator = computed(() => {
	return user.data?.is_moderator
})

const isInstructor = computed(() => {
	return user.data?.is_instructor
})

const canAccessBatch = computed(() => {
	return isModerator.value || isStudent.value || isInstructor.value
})
</script>
<style scoped>
.lms-batch-overlay__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
	font-variant-numeric: tabular-nums;
}

.lms-batch-overlay__brass {
	color: #9c7a3c;
}
</style>
