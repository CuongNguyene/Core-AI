<template>
	<div
		v-if="count > 0"
		class="flex items-center gap-3 mb-4 p-3 rounded-md border transition-colors"
		:class="
			isCritical
				? 'bg-surface-red-2 border-outline-red-2'
				: 'bg-surface-amber-2 border-outline-amber-2'
		"
	>
		<div
			class="flex items-center justify-center size-9 rounded-full shrink-0"
			:class="isCritical ? 'bg-surface-red-3' : 'bg-surface-amber-3'"
		>
			<ShieldAlert
				class="size-5"
				:class="isCritical ? 'text-ink-red-4' : 'text-ink-amber-4'"
			/>
		</div>
		<div class="flex-1 min-w-0">
			<div
				class="font-semibold text-sm"
				:class="isCritical ? 'text-ink-red-4' : 'text-ink-amber-4'"
			>
				{{
					isCritical
						? __('integrity.warningTitleCritical')
						: __('integrity.warningTitle')
				}}
			</div>
			<div
				class="text-sm leading-5"
				:class="isCritical ? 'text-ink-red-3' : 'text-ink-amber-3'"
			>
				{{ __('integrity.tabSwitchWarning').format(count) }}
			</div>
		</div>
		<div
			class="flex flex-col items-center justify-center shrink-0 rounded-md px-3 py-1 min-w-14"
			:class="isCritical ? 'bg-surface-red-3' : 'bg-surface-amber-3'"
		>
			<span
				class="text-lg font-bold leading-none"
				:class="isCritical ? 'text-ink-red-4' : 'text-ink-amber-4'"
			>
				{{ count }}
			</span>
			<span
				class="text-[10px] uppercase tracking-wide mt-0.5"
				:class="isCritical ? 'text-ink-red-3' : 'text-ink-amber-3'"
			>
				{{ __('integrity.violationsLabel') }}
			</span>
		</div>
	</div>
</template>
<script setup>
import { computed } from 'vue'
import { ShieldAlert } from 'lucide-vue-next'

const props = defineProps({
	count: {
		type: Number,
		default: 0,
	},
	criticalThreshold: {
		type: Number,
		default: 3,
	},
})

const isCritical = computed(() => props.count >= props.criticalThreshold)
</script>
