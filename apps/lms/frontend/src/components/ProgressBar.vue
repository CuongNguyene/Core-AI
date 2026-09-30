<template>
	<Tooltip :text="`${props.progress}%`">
		<div class="w-full bg-surface-gray-3 rounded-full h-1">
			<div
				class="rounded-full transition-colors"
				:class="[progressBarHeight, isComplete && completionColor ? 'bg-surface-green-3' : 'bg-surface-gray-7']"
				:style="{ width: progressBarWidth }"
			></div>
		</div>
	</Tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { Tooltip } from 'frappe-ui'

const props = defineProps({
	progress: {
		type: Number,
		default: 0,
	},
	size: {
		type: String,
		default: 'sm',
	},
	// Only meaningful for progress that represents completion (course/program/lesson
	// progress) — turns the bar green at 100%. Left off for non-completion meters like
	// Quiz.vue's countdown timer, where 100% means time is up, not "done well".
	completionColor: {
		type: Boolean,
		default: false,
	},
})

const progressBarWidth = computed(() => {
	const formattedPercentage = Math.min(Math.ceil(props.progress), 100)
	return `${formattedPercentage}%`
})

const isComplete = computed(() => Math.ceil(props.progress) >= 100)

const progressBarHeight = computed(() => {
	if (props.size === 'sm') {
		return 'h-1'
	}
	if (props.size === 'md') {
		return 'h-2'
	}
	if (props.size === 'lg') {
		return 'h-3'
	}
})
</script>
