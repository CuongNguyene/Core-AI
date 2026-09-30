<template>
	<div class="flex items-center w-full space-x-3 px-3 py-2 sm:h-15">
		<Skeleton rounded class="size-8 shrink-0" />
		<div class="flex flex-col md:flex-row w-full gap-2">
			<div class="flex-1 space-y-2">
				<Skeleton class="h-4 w-40" />
				<Skeleton class="h-3 w-56" />
			</div>
			<div class="flex items-center gap-3 md:gap-8">
				<Skeleton class="h-3 w-20" />
				<Skeleton class="h-3 w-16" />
			</div>
		</div>
	</div>
</template>
<script setup>
import Skeleton from '@/components/Skeleton.vue'
</script>
