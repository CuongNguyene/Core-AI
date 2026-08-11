<template>
	<div class="h-full">
		<div class="grid grid-cols-1 md:grid-cols-[70%,30%] h-full">
			<div>
				<div
					class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
				>
					<Skeleton class="h-5 w-48" />
					<div class="flex items-center space-x-2">
						<Skeleton class="h-8 w-8" />
						<Skeleton class="h-8 w-20" />
					</div>
				</div>
				<div class="mt-5 mb-5">
					<div
						v-for="section in 3"
						:key="section"
						class="px-5 md:px-10 pb-5 mb-5 space-y-5 border-b"
					>
						<Skeleton class="h-5 w-32 mb-4" />
						<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
							<div class="space-y-2">
								<Skeleton class="h-3 w-16" />
								<Skeleton class="h-8 w-full" />
							</div>
							<div class="space-y-2">
								<Skeleton class="h-3 w-16" />
								<Skeleton class="h-8 w-full" />
							</div>
						</div>
					</div>
				</div>
			</div>
			<div class="border-l p-5 space-y-3">
				<Skeleton class="h-5 w-32" />
				<Skeleton class="h-10 w-full rounded-md" />
				<Skeleton class="h-10 w-full rounded-md" />
				<Skeleton class="h-10 w-full rounded-md" />
			</div>
		</div>
	</div>
</template>
<script setup>
import Skeleton from '@/components/Skeleton.vue'
</script>
