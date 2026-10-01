<template>
	<Dialog
		v-model="show"
		:options="{
			size: 'xl',
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					onClick: () => {
						addAssessment()
					},
				},
			],
		}"
	>
		<template #body-title>
			<h3 class="lms-assessment-plugin__serif text-2xl leading-6 text-ink-gray-9">
				{{
					type == 'quiz'
						? __('Add a quiz to your lesson')
						: __('Add an assignment to your lesson')
				}}
			</h3>
		</template>
		<template #body-content>
			<div class="">
				<div>
					<Link
						v-if="type == 'quiz'"
						v-model="quiz"
						doctype="LMS Quiz"
						:label="__('Select a quiz')"
						:onCreate="(value, close) => redirectToForm()"
					/>
					<Link
						v-else
						v-model="assignment"
						doctype="LMS Assignment"
						:label="__('Select an assignment')"
						:onCreate="(value, close) => redirectToForm()"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog } from 'frappe-ui'
import { onMounted, ref, nextTick } from 'vue'
import Link from '@/components/Controls/Link.vue'

const show = ref(false)
const quiz = ref(null)
const assignment = ref(null)

const props = defineProps({
	type: {
		type: String,
		required: true,
	},
	onAddition: {
		type: Function,
		required: true,
	},
})

onMounted(async () => {
	await nextTick()
	show.value = true
})

const addAssessment = () => {
	props.onAddition(props.type == 'quiz' ? quiz.value : assignment.value)
	show.value = false
}

const redirectToForm = () => {
	if (props.type == 'quiz') window.open('/lms/quizzes/new', '_blank')
	else window.open('/lms/assignments/new', '_blank')
}
</script>
<style scoped>
.lms-assessment-plugin__serif {
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
