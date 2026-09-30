<template>
	<div class="mt-10">
		<div
			class="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
		>
			<span class="lms-leaderboard__serif text-lg text-ink-gray-9">
				{{ __('home.leaderboard.title') }}
			</span>
			<TabButtons :buttons="periodTabs" v-model="period" class="w-fit" />
		</div>
		<div class="overflow-hidden rounded-md border border-outline-gray-2">
			<div
				v-if="leaderboard.loading && !leaderboard.data"
				class="p-6 text-center text-sm text-ink-gray-5"
			>
				{{ __('home.leaderboard.loading') }}
			</div>
			<div
				v-else-if="!leaderboard.data?.length"
				class="p-6 text-center text-sm text-ink-gray-5"
			>
				{{ __('home.leaderboard.empty') }}
			</div>
			<div v-else>
				<div
					v-for="(row, idx) in leaderboard.data"
					:key="row.user"
					class="flex items-center gap-3 px-4 py-2.5"
					:class="
						idx !== leaderboard.data.length - 1
							? 'border-b border-outline-gray-1'
							: ''
					"
				>
					<span
						class="lms-leaderboard__mono flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs"
						:class="idx === 0 ? 'lms-leaderboard__gold' : 'text-ink-gray-5'"
					>
						{{ idx + 1 }}
					</span>
					<UserAvatar
						:user="{ full_name: row.full_name, user_image: row.user_image }"
						size="lg"
					/>
					<span class="min-w-0 flex-1 truncate text-sm text-ink-gray-8">
						{{ row.full_name }}
					</span>
					<div
						class="lms-leaderboard__mono flex shrink-0 items-center gap-4 text-xs text-ink-gray-6"
					>
						<span>{{ row.hours }}{{ __('home.leaderboard.hoursSuffix') }}</span>
						<span class="flex items-center gap-1">
							<GraduationCap class="h-3.5 w-3.5 stroke-1.5" />
							{{ row.certificates }}
						</span>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { createResource, TabButtons } from 'frappe-ui'
import { GraduationCap } from 'lucide-vue-next'
import UserAvatar from '@/components/UserAvatar.vue'

const period = ref('all')

const periodTabs = computed(() => [
	{ label: __('home.leaderboard.month'), value: 'month' },
	{ label: __('home.leaderboard.year'), value: 'year' },
	{ label: __('home.leaderboard.allTime'), value: 'all' },
])

const leaderboard = createResource({
	url: 'lms.lms.api.get_leaderboard',
	makeParams() {
		return { period: period.value }
	},
	auto: true,
})

watch(period, () => {
	leaderboard.reload()
})
</script>
<style scoped>
.lms-leaderboard__serif {
	font-family:
		'Source Serif 4',
		Georgia,
		'Iowan Old Style',
		'Palatino Linotype',
		'Book Antiqua',
		Palatino,
		serif;
	letter-spacing: -0.01em;
}

.lms-leaderboard__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
	font-variant-numeric: tabular-nums;
}

.lms-leaderboard__gold {
	background: #efe8d8;
	color: #8a6a22;
}
</style>
