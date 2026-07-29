<template>
	<div class="flex flex-col items-center justify-center mt-60">
		<GraduationCap class="size-10 mx-auto stroke-1 text-ink-gray-5" />
		<div class="text-lg font-semibold text-ink-gray-7 mb-2.5">
			{{ __('common.emptyState.noItems').format(type?.toLowerCase()) }}
		</div>
		<div
			class="leading-5 text-base w-full md:w-2/5 text-base text-center text-ink-gray-7"
		>
			{{
				__(
					'common.emptyState.description'
				).format(type?.toLowerCase())
			}}
		</div>
	</div>
</template>
<script setup lang="ts">
import { BookOpen, GraduationCap } from 'lucide-vue-next'

const props = defineProps({
	type: String,
})
</script>
