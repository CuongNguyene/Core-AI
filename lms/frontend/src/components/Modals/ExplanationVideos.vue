<template>
	<Dialog
		v-model="show"
		:options="{
			size: '4xl',
		}"
	>
		<template #body-title>
			<h3 class="lms-explanation-videos__serif text-2xl leading-6 text-ink-gray-9">
				{{ title }}
			</h3>
		</template>
		<template #body-content>
			<div>
				<VideoBlock :file="file" />
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog } from 'frappe-ui'
import { computed } from 'vue'
import VideoBlock from '@/components/VideoBlock.vue'

const show = defineModel()

const props = defineProps({
	type: {
		type: [String, null],
		required: true,
	},
	title: {
		type: [String, null],
		required: true,
	},
})

const file = computed(() => {
	if (props.type == 'youtube') return '/assets/lms/frontend/Youtube.mp4'
	if (props.type == 'quiz') return '/assets/lms/frontend/Quiz.mp4'
	if (props.type == 'upload') return '/assets/lms/frontend/Upload.mp4'
	if (props.type == 'remove') return '/assets/lms/frontend/Remove.mp4'
})
</script>
<style scoped>
.lms-explanation-videos__serif {
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
