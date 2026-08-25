<template>
	<div>
		<div
			class="sticky top-0 z-10 flex items-center border-b border-outline-gray-2 bg-surface-white/90 backdrop-blur-md px-3 py-2.5 sm:px-5"
		>
			<Skeleton class="h-5 w-48" />
		</div>
		<div class="m-5">
			<div class="flex justify-between w-full gap-5">
				<div class="md:w-2/3 w-full space-y-4">
					<div v-if="tabs" class="flex gap-2 mb-2">
						<Skeleton class="h-8 w-20" v-for="i in 4" :key="i" />
					</div>
					<Skeleton class="h-8 w-2/3" />
					<Skeleton class="h-4 w-full" />
					<Skeleton class="h-4 w-5/6" />
					<Skeleton class="h-4 w-3/4" />
					<Skeleton class="h-40 w-full mt-6 rounded-md" />
					<Skeleton class="h-4 w-full mt-6" />
					<Skeleton class="h-4 w-11/12" />
					<Skeleton class="h-4 w-4/5" />
				</div>
				<div v-if="sidebar" class="hidden md:block w-72 shrink-0 space-y-3">
					<Skeleton class="h-56 w-full rounded-lg" />
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import Skeleton from '@/components/Skeleton.vue'

defineProps({
	sidebar: {
		type: Boolean,
		default: true,
	},
	tabs: {
		type: Boolean,
		default: false,
	},
})
</script>
