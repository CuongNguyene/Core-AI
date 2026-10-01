<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b border-outline-gray-2 bg-surface-white/90 px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs
			:items="[
				{
					label: __('Learning Assignments'),
					route: { name: 'LearningAssignments' },
				},
			]"
		/>
		<Button variant="solid" @click="showForm = true">{{
			__('Assign learning')
		}}</Button>
	</header>
	<div class="p-5 pb-10">
		<div class="mb-5 flex flex-wrap gap-2">
			<Button
				v-for="tab in tabs"
				:key="tab"
				:variant="status === tab ? 'solid' : 'subtle'"
				@click="status = tab"
			>
				{{ tab }}
			</Button>
		</div>
		<div v-if="resource.loading" class="text-sm text-ink-gray-6">
			{{ __('Loading...') }}
		</div>
		<div
			v-else-if="rows.length"
			class="overflow-x-auto rounded-md border border-outline-gray-2"
		>
			<table class="w-full text-left text-sm text-ink-gray-9">
				<thead class="bg-surface-gray-1 text-ink-gray-6">
					<tr>
						<th class="p-3">{{ __('Learner') }}</th>
						<th class="p-3">{{ __('Target') }}</th>
						<th class="p-3">{{ __('Completion deadline') }}</th>
						<th class="p-3">{{ __('Status') }}</th>
						<th class="p-3">{{ __('Progress') }}</th>
						<th class="p-3"></th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in rows"
						:key="row.name"
						class="border-t border-outline-gray-2 hover:bg-surface-gray-1"
					>
						<td class="p-3 text-ink-gray-9">{{ row.learner }}</td>
						<td class="p-3">
							<div class="font-medium text-ink-gray-9">
								{{ row.target_title }}
							</div>
							<div class="mt-0.5 text-xs text-ink-gray-6">
								{{ row.target_type }}
							</div>
						</td>
						<td class="p-3">
							<div class="text-ink-gray-8">
								{{
									row.due_at
										? formatDate(row.due_at)
										: __('No completion deadline')
								}}
							</div>
							<div
								v-if="row.due_at"
								class="mt-0.5 text-xs font-medium"
								:class="deadlineMeta(row).textClass"
							>
								{{ deadlineMeta(row).label }}
							</div>
						</td>
						<td class="p-3 text-ink-gray-6">{{ row.status }}</td>
						<td class="p-3 text-ink-gray-6">{{ row.progress }}%</td>
						<td class="p-3 text-right">
							<Button
								v-if="canCancel(row)"
								variant="subtle"
								@click="cancel(row)"
								>{{ __('Cancel assignment') }}</Button
							>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div
			v-else
			class="rounded-md border border-dashed border-outline-gray-2 p-10 text-center text-sm text-ink-gray-6"
		>
			{{ __('No learning assignments found.') }}
		</div>
	</div>
	<Dialog
		v-model="showForm"
		:options="{ title: __('Assign learning'), size: 'lg' }"
	>
		<template #body>
			<div class="space-y-4 p-5">
				<FormControl
					v-model="form.target_type"
					:label="__('Target type')"
					type="select"
					:options="[
						{ label: 'Course', value: 'Course' },
						{ label: 'Batch', value: 'Batch' },
					]"
				/>
				<FormControl
					v-model="form.target"
					:label="form.target_type"
					type="select"
					:options="targetOptions"
				/>
				<Autocomplete
					:model-value="form.learner"
					:label="__('Learner')"
					:options="learnerOptions"
					:placeholder="
						form.target
							? __('Search by learner name or email')
							: __('Select a course or batch first')
					"
					:readonly="!form.target"
					@update:model-value="selectLearner"
					@update:query="searchLearners"
				>
					<template #item-label="{ option }">
						<div class="flex flex-col text-ink-gray-8">
							<span>{{ option.label }}</span
							><span class="text-xs text-ink-gray-6">{{
								option.description
							}}</span>
						</div>
					</template>
				</Autocomplete>
				<div>
					<FormControl
						v-model="form.due_at"
						:label="__('Completion deadline (date and time)')"
						type="datetime-local"
					/>
					<p class="mt-1 text-xs text-ink-gray-6">
						{{
							__(
								'Leave blank only when this learning has no completion deadline.',
							)
						}}
					</p>
				</div>
				<FormControl
					v-model="form.mandatory"
					:label="__('Mandatory')"
					type="checkbox"
				/>
				<FormControl v-model="form.note" :label="__('Note')" type="textarea" />
				<div class="flex justify-end gap-2">
					<Button @click="showForm = false">{{ __('Close') }}</Button
					><Button variant="solid" :loading="saving" @click="submit">{{
						__('Assign')
					}}</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
	Breadcrumbs,
	Button,
	call,
	createResource,
	Dialog,
	FormControl,
	toast,
	usePageMeta,
} from 'frappe-ui'
import Autocomplete from '@/components/Controls/Autocomplete.vue'
import dayjs from '@/utils/dayjs'

const status = ref('All')
const showForm = ref(false)
const saving = ref(false)
const form = ref({
	learner: '',
	target_type: 'Course',
	target: '',
	due_at: '',
	mandatory: true,
	note: '',
})
const tabs = [
	'All',
	'Assigned',
	'In Progress',
	'Overdue',
	'Completed',
	'Cancelled',
]
const resource = createResource({
	url: 'lms.lms.learning_assignment_api.get_learning_assignment_management_data',
	auto: true,
})
const rows = computed(() =>
	(resource.data?.assignments || []).filter(
		(row: any) => status.value === 'All' || row.status === status.value,
	),
)
const canCancel = (row: any) =>
	['Assigned', 'In Progress', 'Overdue'].includes(row.status)
const formatDate = (value: string) => dayjs(value).format('LLL')
const deadlineMeta = (row: any) => {
	const remainingHours = dayjs(row.due_at).diff(dayjs(), 'hour', true)
	const overdueDays = Math.max(1, Math.ceil(Math.abs(remainingHours) / 24))
	const remainingDays = Math.max(1, Math.ceil(remainingHours / 24))
	if (row.completed_late)
		return {
			label: __('Completed after the deadline'),
			textClass: 'text-ink-amber-3',
		}
	if (row.status === 'Completed')
		return {
			label: __('Completed before the deadline'),
			textClass: 'text-ink-green-3',
		}
	if (remainingHours < 0)
		return {
			label: `${__('Overdue by')} ${overdueDays} ${__('day(s)')}`,
			textClass: 'text-ink-red-3',
		}
	if (remainingHours < 24)
		return { label: __('Due within 24 hours'), textClass: 'text-ink-amber-3' }
	if (remainingDays <= 3)
		return {
			label: `${remainingDays} ${__('day(s) remaining')}`,
			textClass: 'text-ink-amber-3',
		}
	return {
		label: `${remainingDays} ${__('day(s) remaining')}`,
		textClass: 'text-ink-green-3',
	}
}
const targetOptions = computed(() =>
	(form.value.target_type === 'Course'
		? resource.data?.courses
		: resource.data?.batches || []
	).map((target: any) => ({ label: target.title, value: target.name })),
)
const learnerOptions = ref([])
let learnerSearchRequest = 0

const searchLearners = async (txt = '') => {
	if (!form.value.target) {
		learnerOptions.value = []
		return
	}
	const request = ++learnerSearchRequest
	try {
		const results = await call(
			'lms.lms.learning_assignment_api.search_assignable_learners',
			{
				target_type: form.value.target_type,
				target: form.value.target,
				txt,
			},
		)
		if (request === learnerSearchRequest) learnerOptions.value = results
	} catch (error) {
		if (request === learnerSearchRequest) learnerOptions.value = []
	}
}

const selectLearner = (option: any) => {
	form.value.learner = option?.value || ''
}

watch(
	() => [form.value.target_type, form.value.target],
	() => {
		form.value.learner = ''
		searchLearners()
	},
)

const submit = async () => {
	try {
		if (!form.value.learner) {
			toast.error(__('Select a learner before assigning learning.'))
			return
		}
		saving.value = true
		const result = await call(
			'lms.lms.learning_assignment_api.create_learning_assignment',
			{ ...form.value },
		)
		if (result.already_assigned) {
			toast.info(
				__(
					'This learner already has an active assignment for the selected target.',
				),
			)
		} else {
			toast.success(__('Learning assigned.'))
		}
		showForm.value = false
		resource.reload()
	} finally {
		saving.value = false
	}
}
const cancel = async (row: any) => {
	const reason = window.prompt(__('Cancellation reason'))
	if (!reason) return
	await call('lms.lms.learning_assignment_api.cancel_learning_assignment', {
		name: row.name,
		reason,
	})
	resource.reload()
}
usePageMeta(() => ({ title: __('Learning Assignments') }))
</script>
