<template>
	<Dialog
		v-model="show"
		:options="{
			size: 'sm',
			actions: [
				{
					label: __('courses.batchModal.submit'),
					variant: 'solid',
					onClick: (close) => addCourse(close),
				},
			],
		}"
	>
		<template #body-title>
			<h3 class="lms-batch-course-modal__serif text-2xl leading-6 text-ink-gray-9">
				{{ __('courses.batchModal.addCourse') }}
			</h3>
		</template>
		<template #body-content>
			<Link
				doctype="LMS Course"
				v-model="course"
				:label="__('courses.batchModal.course')"
				:required="true"
				:placeholder="__('courses.batchModal.selectCourse')"
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
	<Dialog
		v-model="showSyncDialog"
		:options="{
			size: 'sm',
			actions: [
				{
					label: __('Do not sync'),
					variant: 'subtle',
					onClick: (close) => skipSync(close),
				},
				{
					label: __('Sync learners'),
					variant: 'solid',
					loading: syncExistingLearners.loading,
					onClick: (close) => syncLearners(close),
				},
			],
		}">
		<template #body-title>
			<h3 class="lms-batch-course-modal__serif text-2xl leading-6 text-ink-gray-9">
				{{ __('Sync existing learners?') }}
			</h3>
		</template>
		<template #body-content>
			<p class="text-sm leading-6 text-ink-gray-6">
				{{
					__(
						'This batch already has {0} learner(s). {1} learner(s) do not have an enrollment in this course yet.',
					).format(
						syncPreview?.existing_members || 0,
						syncPreview?.learners_requiring_enrollment || 0,
					)
				}}
			</p>
			<p class="mt-3 text-sm leading-6 text-ink-gray-6">
				{{
					__(
						'Sync learners creates only the missing enrollments. Do not sync keeps the new course in the batch without enrolling existing learners.',
					)
				}}
			</p>
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
const showSyncDialog = ref(false)
const syncPreview = ref(null)
const addedCourse = ref(null)
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
	url: 'lms.lms.learning_assignment_api.add_course_to_batch',
	makeParams(values) {
		return {
			batch: props.batch,
			course: course.value,
		}
	},
})

const previewBatchCourseSync = createResource({
	url: 'lms.lms.learning_assignment_api.preview_batch_course_sync',
	auto: false,
})

const syncExistingLearners = createResource({
	url: 'lms.lms.learning_assignment_api.sync_batch_course_existing_learners',
	auto: false,
})

const showSyncPrompt = (batchCourse) => {
	previewBatchCourseSync.submit(
		{ batch: props.batch, course: batchCourse },
		{
			onSuccess(data) {
				syncPreview.value = data
				addedCourse.value = batchCourse
				if (data.existing_members) showSyncDialog.value = true
				else toast.success(__('Course added to batch.'))
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		},
	)
}

const skipSync = (close) => {
	close()
	toast.info(__('Course added to batch without enrolling existing learners.'))
}

const syncLearners = (close) => {
	syncExistingLearners.submit(
		{ batch: props.batch, course: addedCourse.value, confirm: 1 },
		{
			onSuccess(data) {
				close()
				toast.success(
					__('Synced {0} learner enrollment(s) to the new course.').format(
						data.created_enrollments,
					),
				)
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		},
	)
}

const addCourse = (close) => {
	const selectedCourse = course.value
	createBatchCourse.submit(
		{},
		{
			onSuccess() {
				if (user.data?.is_system_manager)
					updateOnboardingStep('add_batch_course')

				close()
				courses.value.reload()
				course.value = null
				showSyncPrompt(selectedCourse)
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}
</script>
<style scoped>
.lms-batch-course-modal__serif {
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
