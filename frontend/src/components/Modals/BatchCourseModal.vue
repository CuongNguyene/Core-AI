<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Add a course'),
			size: 'sm',
			actions: [
				{
					label: __('Submit'),
					variant: 'solid',
					onClick: (close) => addCourse(close),
				},
			],
		}"
	>
		<template #body-content>
			<Link
				doctype="LMS Course"
				v-model="course"
				:label="__('Course')"
				:required="true"
				:placeholder="__('Select a course')"
				:onCreate="
					(value, close) => {
						close()
						router.push({
							name: 'CourseForm',
							params: {
								courseName: 'new',
							},
						})
					}
				"
			/>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, createResource, toast } from 'frappe-ui'
import { ref, inject } from 'vue'
import Link from '@/components/Controls/Link.vue'
import { useOnboarding } from '@/utils/onboardingCompat'
import { useRouter } from 'vue-router'

const show = defineModel()
const course = ref(null)
const user = inject('$user')
const courses = defineModel('courses')
const router = useRouter()
const { updateOnboardingStep } = useOnboarding('learning')

const props = defineProps({
	batch: {
		type: String,
		default: null,
	},
})

const createBatchCourse = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Batch Course',
				parent: props.batch,
				parenttype: 'LMS Batch',
				parentfield: 'courses',
				course: course.value,
			},
		}
	},
})

const addCourse = (close) => {
	createBatchCourse.submit(
		{},
		{
			onSuccess() {
				if (user.data?.is_system_manager)
					updateOnboardingStep('add_batch_course')

				close()
				courses.value.reload()
				course.value = null
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}
</script>
