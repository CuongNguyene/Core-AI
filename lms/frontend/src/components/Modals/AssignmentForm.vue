<template>
	<Dialog
		v-model="show"
		:options="{
			size: 'lg',
		}"
	>
		<template #body>
			<div class="p-5 text-base">
				<div class="lms-assignment-form__serif text-2xl text-ink-gray-9 mb-5">
					{{
						assignmentID === 'new'
							? __('assignments.createAssignment')
							: __('assignments.editAssignment')
					}}
				</div>
				<div class="space-y-4 max-h-[75vh] overflow-y-auto">
					<FormControl
						v-model="assignment.title"
						:label="__('assignments.title')"
						:required="true"
					/>
					<Autocomplete
						:modelValue="assignment.type"
						@update:modelValue="(opt) => (assignment.type = opt.value)"
						:options="assignmentOptions"
						:label="__('assignments.submissionType')"
						size="sm"
						:required="true"
					/>
					<div>
						<div class="text-xs text-ink-gray-5 mb-2">
							{{ __('assignments.question') }}
							<span class="text-ink-red-3">*</span>
						</div>
						<TextEditor
							:content="assignment.question"
							@change="(val) => (assignment.question = val)"
							:editable="true"
							:fixedMenu="true"
							editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem] max-h-[18rem] overflow-y-auto"
						/>
					</div>
				</div>

				<div class="flex justify-end space-x-2 mt-5">
					<router-link
						:to="{
							name: 'AssignmentSubmissionList',
							query: {
								assignmentID: assignmentID,
							},
						}"
					>
						<Button v-if="assignmentID !== 'new'" variant="subtle">
							{{ __('assignments.checkSubmissions') }}
						</Button>
					</router-link>
					<Button variant="solid" @click="saveAssignment">
						{{ __('assignments.save') }}
					</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { Button, Dialog, FormControl, TextEditor, toast } from 'frappe-ui'
import Autocomplete from '@/components/Controls/Autocomplete.vue'
import { computed, reactive, watch } from 'vue'

const show = defineModel()
const assignments = defineModel<Assignments>('assignments')

interface Assignment {
	title: string
	type: string
	question: string
}

interface Assignments {
	data: Assignment[]
	get: (params: { doctype: string; name: string }) => Promise<Assignment>
	insert: {
		submit: (params: Assignment, options: { onSuccess: () => void }) => void
	}
}

const assignment = reactive({
	title: '',
	type: '',
	question: '',
})

const props = defineProps({
	assignmentID: {
		type: String,
		default: 'new',
	},
})

watch(
	() => props.assignmentID,
	(val) => {
		if (val !== 'new') {
			assignments.value?.data.forEach((row) => {
				if (row.name === val) {
					assignment.title = row.title
					assignment.type = row.type
					assignment.question = row.question
				}
			})
		} else {
			assignment.title = ''
			assignment.type = ''
			assignment.question = ''
		}
	},
	{ flush: 'post' }
)

watch(show, (isOpen) => {
	if (isOpen && props.assignmentID === 'new') {
		assignment.title = ''
		assignment.type = ''
		assignment.question = ''
	}
})

const saveAssignment = () => {
	if (!assignment.title?.trim()) {
		toast.warning(__('assignments.title') + ' is required')
		return
	}
	if (!assignment.type) {
		toast.warning(__('assignments.submissionType') + ' is required')
		return
	}
	if (!assignment.question?.trim()) {
		toast.warning(__('assignments.question') + ' is required')
		return
	}

	if (props.assignmentID == 'new') {
		assignments.value.insert.submit(
			{
				...assignment,
			},
			{
				onSuccess() {
					show.value = false
					toast.success(__('assignments.createdSuccess'))
				},
				onError(err: any) {
					toast.warning(__(err.messages?.[0] || err))
				},
			}
		)
	} else {
		assignments.value.setValue.submit(
			{
				...assignment,
				name: props.assignmentID,
			},
			{
				onSuccess() {
					show.value = false
					toast.success(__('assignments.updatedSuccess'))
				},
				onError(err: any) {
					toast.warning(__(err.messages?.[0] || err))
				},
			}
		)
	}
}

const assignmentOptions = computed(() => {
	return [
		{ label: __('assignments.typePdf'), value: 'PDF' },
		{ label: __('assignments.typeImage'), value: 'Image' },
		{ label: __('assignments.typeDocument'), value: 'Document' },
		{ label: __('assignments.typeText'), value: 'Text' },
		{ label: __('assignments.typeUrl'), value: 'URL' },
	]
})
</script>
<style scoped>
.lms-assignment-form__serif {
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
