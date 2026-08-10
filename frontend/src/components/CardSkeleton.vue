<template>
	<div class="flex flex-col h-full rounded-md overflow-hidden border" style="min-height: 350px">
		<Skeleton class="w-full h-[168px] rounded-none" />
		<div class="flex flex-col flex-auto p-4 space-y-3">
			<div class="flex items-center justify-between">
				<Skeleton class="h-4 w-16" />
				<Skeleton class="h-4 w-10" />
			</div>
			<Skeleton class="h-5 w-4/5" />
			<Skeleton class="h-4 w-full" />
			<Skeleton class="h-4 w-2/3" />
			<div class="flex items-center gap-2 pt-2">
				<Skeleton rounded class="size-6" />
				<Skeleton class="h-3 w-24" />
			</div>
		</div>
	</div>
</template>
<script setup>
import Skeleton from '@/components/Skeleton.vue'
</script>
