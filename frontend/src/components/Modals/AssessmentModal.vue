<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('batches.assessments.addAssessmentTitle'),
			size: 'sm',
			actions: [
				{
					label: __('batches.assessments.submit'),
					variant: 'solid',
					onClick: (close) => addAssessment(close),
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<Autocomplete
					:modelValue="assessmentType"
					@update:modelValue="(opt) => (assessmentType = opt.value)"
					:options="assessmentTypes"
					:label="__('batches.assessments.type')"
					size="sm"
				/>
				<Link
					v-model="assessment"
					:doctype="assessmentType"
					:label="__('batches.assessments.assessmentLabel')"
					:onCreate="
						(value, close) => {
							close()
							if (assessmentType === 'LMS Quiz') {
								router.push({
									name: 'QuizForm',
									params: {
										quizID: 'new',
									},
								})
							} else if (assessmentType === 'LMS Assignment') {
								router.push({
									name: 'Assignments',
								})
							}
						}
					"
				/>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, createResource, toast } from 'frappe-ui'
import Link from '@/components/Controls/Link.vue'
import Autocomplete from '@/components/Controls/Autocomplete.vue'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

const show = defineModel()
const assessmentType = ref(null)
const assessment = ref(null)
const assessments = defineModel('assessments')
const router = useRouter()

const props = defineProps({
	batch: {
		type: String,
		default: null,
	},
})

const assessmentResource = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'LMS Assessment',
				parent: props.batch,
				parenttype: 'LMS Batch',
				parentfield: 'assessment',
				assessment_type: assessmentType.value,
				assessment_name: assessment.value,
			},
		}
	},
})

const addAssessment = (close) => {
	assessmentResource.submit(
		{},
		{
			onSuccess(data) {
				assessments.value.reload()
				toast.success(__('batches.assessments.addedSuccess'))
				close()
			},
		}
	)
}

const assessmentTypes = computed(() => {
	return [
		{ label: __('batches.assessments.quiz'), value: 'LMS Quiz' },
		{ label: __('batches.assessments.assignment'), value: 'LMS Assignment' },
		{ label: __('batches.assessments.programmingExercise'), value: 'LMS Programming Exercise' },
	]
})
</script>
