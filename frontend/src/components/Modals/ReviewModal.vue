<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('courses.reviews.writeAReview'),
			size: 'xl',
			actions: [
				{
					label: __('courses.reviews.submit'),
					variant: 'solid',
					onClick: (close) => submitReview(close),
				},
			],
		}"
	>
		<template #body-title>
			<h3 class="lms-review-modal__serif text-2xl leading-6 text-ink-gray-9">
				{{ __('courses.reviews.writeAReview') }}
			</h3>
		</template>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<Rating v-model="review.rating" :label="__('courses.reviews.rating')" />
				<FormControl
					:label="__('courses.reviews.review')"
					type="textarea"
					v-model="review.review"
					:rows="5"
				/>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, FormControl, createResource, toast, Rating } from 'frappe-ui'
import { reactive } from 'vue'

const show = defineModel()
const reviews = defineModel('reloadReviews')
const hasReviewed = defineModel('hasReviewed')

let review = reactive({
	review: '',
	rating: 0,
})

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
})

const createReview = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'LMS Course Review',
				course: props.courseName,
				...values,
			},
		}
	},
})
function submitReview(close) {
	review.rating = review.rating / 5
	createReview.submit(review, {
		validate() {
			if (!review.rating) {
				return __('courses.reviews.ratingRequired')
			}
		},
		onSuccess() {
			reviews.value.reload()
			hasReviewed.value.reload()
		},
		onError(err) {
			toast.error(err.messages?.[0] || err)
		},
	})
	close()
}
</script>
<style scoped>
.lms-review-modal__serif {
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
