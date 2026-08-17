<template>
	<div
		class="flex items-center gap-3 px-3 py-2 sm:px-5 bg-surface-gray-7 transition-colors duration-300"
		:class="justFlagged ? 'bg-ink-red-4' : 'bg-surface-gray-7'"
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
			<span
				v-if="count > 0"
				:key="count"
				class="text-sm truncate"
				:class="justFlagged ? 'text-ink-white font-medium' : 'text-ink-gray-4'"
			>
				{{ __('integrity.violationWarning').format(eventLabel, count) }}
			</span>
		</div>
		<div
			v-if="studyTime !== undefined"
			class="flex items-center gap-1.5 shrink-0 font-mono text-xs text-ink-gray-4 border border-outline-gray-3 rounded px-2 py-1"
		>
			<span>{{ __('Time') }}</span>
			<span class="font-semibold text-ink-white">{{
				formatTimer(studyTime)
			}}</span>
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
import { computed, ref, watch } from 'vue'

const props = defineProps({
	count: {
		type: Number,
		default: 0,
	},
	studyTime: {
		type: Number,
		default: undefined,
	},
	// One of LMS Activity Log's event_type options (Tab Hidden, Copy Attempt,
	// Right Click, Print Screen Attempt, DevTools Opened, Concurrent Session).
	// Drives which specific action the banner names on the latest violation -
	// previously this always said "left the screen" regardless of what was
	// actually flagged (e.g. a copy attempt showed the tab-switch message).
	lastEventType: {
		type: String,
		default: undefined,
	},
})

// Vietnamese/English phrase per event_type; falls back to the generic
// tab-hidden phrasing for anything unrecognized (defensive, not expected).
const EVENT_LABEL_KEYS = {
	'Tab Hidden': 'integrity.events.tabHidden',
	'Copy Attempt': 'integrity.events.copyAttempt',
	'Right Click': 'integrity.events.rightClick',
	'Print Screen Attempt': 'integrity.events.printScreen',
	'DevTools Opened': 'integrity.events.devTools',
	'Concurrent Session': 'integrity.events.concurrentSession',
}

const eventLabel = computed(() => {
	const key = EVENT_LABEL_KEYS[props.lastEventType] || EVENT_LABEL_KEYS['Tab Hidden']
	return __(key)
})

// Brief flash on every new violation so it reads as a startling, in-the-
// moment notice rather than a number that quietly changed in a corner.
const justFlagged = ref(false)
let flashTimeout = null
watch(
	() => props.count,
	(newCount, oldCount) => {
		if (newCount <= (oldCount || 0)) return
		justFlagged.value = true
		clearTimeout(flashTimeout)
		flashTimeout = setTimeout(() => {
			justFlagged.value = false
		}, 1500)
	}
)

const formatTimer = (seconds) => {
	const hrs = Math.floor(seconds / 3600)
		.toString()
		.padStart(2, '0')
	const mins = Math.floor((seconds % 3600) / 60)
		.toString()
		.padStart(2, '0')
	const secs = (seconds % 60).toString().padStart(2, '0')
	return hrs != '00' ? `${hrs}:${mins}:${secs}` : `${mins}:${secs}`
}
</script>
