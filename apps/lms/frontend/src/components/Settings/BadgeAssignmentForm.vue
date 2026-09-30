<template>
	<Dialog
		v-model="show"
		:options="{
			size: 'sm',
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					onClick: ({ close }) => {
						saveBadgeAssignment(close)
					},
				},
			],
		}"
	>
		<template #body-title>
			<h3 class="lms-badge-assignment-form__serif text-2xl leading-6 text-ink-gray-9">
				{{
					props.badgeAssignmentID === 'new'
						? __('Assign a Badge')
						: __('Edit Badge Assignment')
				}}
			</h3>
		</template>
		<template #body-content>
			<div class="space-y-4">
				<Link
					doctype="User"
					v-model="badgeAssignment.member"
					:label="__('Member')"
					:required="true"
				/>
				<Link
					doctype="LMS Badge"
					v-model="badgeAssignment.badge"
					:label="__('Badge')"
					:required="true"
				/>
				<div>
					<label class="text-xs text-ink-gray-5 mb-1">
						{{ __('Issued On') }}
						<span class="text-ink-red-3">*</span>
					</label>
					<DatePicker
						v-model="badgeAssignment.issued_on"
						:placeholder="__('Select Date')"
						:required="true"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { Dialog, DatePicker, toast } from 'frappe-ui'
import type {
	BadgeAssignments,
	BadgeAssignment,
} from '@/components/Settings/types'
import { ref, watch } from 'vue'
import { cleanError } from '@/utils'
import Link from '@/components/Controls/Link.vue'

const show = defineModel<boolean>({ required: true, default: false })
const defaultBadgeAssignment = {
	name: '',
	badge: '',
	member: '',
	issued_on: '',
	member_name: '',
	member_username: '',
	member_image: '',
}
const badgeAssignments = defineModel<BadgeAssignments>('badgeAssignments')
const badgeAssignment = ref<BadgeAssignment>(defaultBadgeAssignment)

const props = defineProps<{
	badgeAssignmentID: string
	badge: string | null
}>()

watch(
	() => props.badgeAssignmentID,
	(newID) => {
		if (newID === 'new') {
			badgeAssignment.value = {
				...defaultBadgeAssignment,
				badge: props.badge || '',
			}
		} else {
			const assignment = badgeAssignments.value?.data?.find(
				(assignment) => assignment.name === newID
			)
			if (assignment) {
				badgeAssignment.value = { ...assignment }
			}
		}
	}
)

const saveBadgeAssignment = (close: () => void) => {
	if (props.badgeAssignmentID === 'new') {
		createBadgeAssignment(close)
	} else {
		updateBadgeAssignment(close)
	}
}

const updateBadgeAssignment = async (close: () => void) => {
	badgeAssignments.value?.setValue.submit(
		{
			...badgeAssignment.value,
		},
		{
			onSuccess: () => {
				toast.success(__('Badge assignment updated successfully'))
				close()
			},
			onError: (error) => {
				toast.error(
					__('Failed to update badge assignment: ') + cleanError(error)
				)
			},
		}
	)
}

const createBadgeAssignment = (close: () => void) => {
	badgeAssignments.value?.insert.submit(
		{
			...badgeAssignment.value,
		},
		{
			onSuccess: () => {
				toast.success(__('Badge assignment created successfully'))
				close()
			},
			onError: (error) => {
				toast.error(
					__('Failed to create badge assignment: ') + cleanError(error)
				)
			},
		}
	)
}
</script>
<style scoped>
.lms-badge-assignment-form__serif {
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
