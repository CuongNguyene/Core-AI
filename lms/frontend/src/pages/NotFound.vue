<template>
	<div class="flex flex-col items-center justify-center h-full my-32">
		<div class="text-6xl font-bold text-ink-gray-5 mb-4">404</div>
		<div class="text-xl font-semibold text-ink-gray-8 mb-2">
			{{ __('Page Not Found') }}
		</div>
		<div class="text-base text-ink-gray-6 mb-6 text-center max-w-md">
			{{
				__(
					'The page you are looking for does not exist or has been moved.'
				)
			}}
		</div>
		<router-link :to="{ name: 'Courses' }">
			<Button variant="solid">
				{{ __('Go to Courses') }}
			</Button>
		</router-link>
	</div>
</template>

<script setup>
import { Button } from 'frappe-ui'
</script>
