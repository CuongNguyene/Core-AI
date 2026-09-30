<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center border-b border-outline-gray-2 bg-surface-white/90 backdrop-blur-md px-3 py-2.5 sm:px-5"
		>
			<Skeleton class="h-5 w-40" />
		</header>
		<Skeleton class="h-[130px] w-full rounded-none" />
		<div class="mx-auto -mt-10 md:-mt-4 max-w-4xl translate-x-0 px-5">
			<div class="flex flex-col md:flex-row items-center">
				<Skeleton rounded class="h-[100px] w-[100px] border-4 border-white shrink-0" />
				<div class="ml-0 md:ml-6 mt-3 md:mt-2 space-y-2 w-full md:w-auto">
					<Skeleton class="h-6 w-48" />
					<Skeleton class="h-4 w-32" />
				</div>
			</div>
			<div class="flex gap-2 mb-4 mt-6">
				<Skeleton class="h-8 w-20" v-for="i in 2" :key="i" />
			</div>
			<div class="space-y-3">
				<Skeleton class="h-4 w-full" />
				<Skeleton class="h-4 w-5/6" />
				<Skeleton class="h-4 w-2/3" />
			</div>
		</div>
	</div>
</template>
<script setup>
import Skeleton from '@/components/Skeleton.vue'
</script>
