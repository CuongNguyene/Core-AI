<template>
	<div class="animate-pulse rounded bg-surface-gray-3" :class="rounded ? 'rounded-full' : ''"></div>
</template>
<script setup>
defineProps({
	rounded: {
		type: Boolean,
		default: false,
	},
})
</script>
