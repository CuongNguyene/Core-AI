<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('home.streak.title'),
		}"
	>
		<template #body-content>
			<div class="text-base">
				<div class="text-center">
					<div class="text-[30px]">🔥</div>
					<div class="mt-3">
						<div class="text-ink-gray-5 mb-1">
							{{
								streakInfo.data?.current_streak < 1
									? __('home.streak.low')
									: streakInfo.data?.current_streak < 10
									? __('home.streak.mid')
									: __('home.streak.high')
							}}
							{{ __('home.streak.youAreOnA') }}
						</div>
						<div class="font-semibold text-xl text-ink-gray-9">
							{{ streakInfo.data?.current_streak }} {{ __('home.streak.dayStreak') }}
						</div>
					</div>
				</div>

				<div
					class="grid grid-cols-2 bg-surface-gray-1 px-2.5 py-2 rounded-md mt-8"
				>
					<div class="space-y-1 border-r border-outline-gray-2 mr-4">
						<div class="text-ink-gray-6">
							{{ __('home.streak.current') }}
						</div>
						<div class="font-semibold text-lg text-ink-gray-9">
							{{ streakInfo.data?.current_streak }} {{ __('home.streak.days') }}
						</div>
					</div>
					<div class="space-y-1">
						<div class="text-ink-gray-6">
							{{ __('home.streak.longest') }}
						</div>
						<div class="font-semibold text-lg text-ink-gray-9">
							{{ streakInfo.data?.longest_streak }} {{ __('home.streak.days') }}
						</div>
					</div>
				</div>

				<div
					class="text-ink-gray-7 border border-outline-gray-1 px-2.5 py-2 rounded-md text-xs leading-5 mt-5"
				>
					{{ __('home.streak.description') }}
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { Dialog } from 'frappe-ui'

const show = defineModel<boolean>({
	default: false,
})

const props = defineProps<{
	streakInfo: {
		data: {
			current_streak: number
			longest_streak: number
		}
	}
}>()
</script>
