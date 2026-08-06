<template>
	<div
		v-if="count > 0"
		class="flex items-center gap-3 px-3 py-2 sm:px-5 bg-surface-gray-7"
	>
		<span class="relative flex items-center justify-center size-2.5 shrink-0">
			<span
				class="absolute inline-flex h-full w-full rounded-full bg-ink-red-3 animate-ping"
			/>
			<span class="relative inline-flex rounded-full size-2 bg-ink-red-3" />
		</span>
		<div class="flex-1 min-w-0 flex items-baseline gap-2 flex-wrap">
			<span
				class="text-[11px] font-semibold uppercase tracking-widest text-ink-red-3 shrink-0"
			>
				{{ __('integrity.recordingLabel') }}
			</span>
			<span class="text-sm text-ink-gray-4 truncate">
				{{ __('integrity.tabSwitchWarning').format(count) }}
			</span>
		</div>
		<div
			class="flex items-center gap-1.5 shrink-0 font-mono text-xs text-ink-gray-4 border border-outline-gray-3 rounded px-2 py-1"
		>
			<span>{{ __('integrity.violationsLabel') }}</span>
			<span class="font-semibold text-ink-white">{{
				String(count).padStart(2, '0')
			}}</span>
		</div>
	</div>
</template>
<script setup>
defineProps({
	count: {
		type: Number,
		default: 0,
	},
	criticalThreshold: {
		type: Number,
		default: 3,
	},
})
</script>
