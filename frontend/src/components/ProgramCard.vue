<template>
	<div
		v-if="title"
		class="group flex h-full flex-col overflow-hidden rounded-md border border-outline-gray-2 bg-surface-white transition-shadow duration-300 hover:shadow-md motion-reduce:transition-none"
	>
		<!-- Register strip: whether courses in this program must be taken in
		order is the one structural fact that's always true of every program,
		so it's the signature here the way category is for a course card. -->
		<div
			class="flex items-center justify-between border-b border-outline-gray-2 px-3 py-1.5"
		>
			<span
				class="lms-program-card__mono text-[10px] uppercase tracking-[0.12em] text-ink-gray-6"
			>
				{{
					program.enforce_course_order
						? __('programs.card.sequentialTrack')
						: __('programs.card.openTrack')
				}}
			</span>
			<span
				v-if="'published' in program && !program.published"
				class="lms-program-card__mono text-[10px] uppercase tracking-[0.12em] text-ink-gray-6"
			>
				{{ __('programs.card.draft') }}
			</span>
		</div>

		<div class="relative h-[160px] w-full overflow-hidden">
			<div
				class="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-500 ease-out group-hover:scale-[1.05] motion-reduce:transition-none"
				:style="{ backgroundImage: getGradientColor() }"
			></div>
			<div
				class="relative flex h-full items-center justify-center px-6 text-center text-white"
			>
				<span class="lms-program-card__serif leading-tight" :class="titleSize">
					{{ title }}
				</span>
			</div>
		</div>

		<div class="flex flex-1 flex-col p-4">
			<div
				class="lms-program-card__mono mb-1 flex items-center gap-4 border-y border-outline-gray-1 py-2 text-[11px] text-ink-gray-6"
			>
				<Tooltip :text="__('programs.list.courses')">
					<span class="flex items-center gap-1">
						<BookOpen class="h-3.5 w-3.5 stroke-1.5" />
						{{ program.course_count || 0 }}
					</span>
				</Tooltip>

				<Tooltip :text="__('programs.form.members')">
					<span class="flex items-center gap-1">
						<Users class="h-3.5 w-3.5 stroke-1.5" />
						{{ program.member_count || 0 }}
					</span>
				</Tooltip>
			</div>

			<div v-if="hasProgress" class="mt-3">
				<ProgressBar :progress="program.progress" size="md" completionColor />
				<div class="lms-program-card__mono mt-2 text-[11px] text-ink-gray-6">
					{{ Math.ceil(program.progress) }}% {{ __('programs.completed') }}
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import { Tooltip } from 'frappe-ui'
import { BookOpen, Users } from 'lucide-vue-next'
import { computed } from 'vue'
import { theme } from '@/utils/theme'
import ProgressBar from '@/components/ProgressBar.vue'

const props = defineProps({
	program: {
		type: Object,
		default: null,
	},
})

const title = computed(() => props.program?.title || props.program?.name || '')

const titleSize = computed(() => {
	if (title.value.length > 32) return 'text-lg'
	if (title.value.length > 20) return 'text-xl'
	return 'text-2xl'
})

const hasProgress = computed(
	() => 'progress' in props.program && props.program.progress != null,
)

const palette = ['blue', 'green', 'orange', 'red', 'purple', 'teal', 'pink']

const getGradientColor = () => {
	const key = title.value
	let sum = 0
	for (let i = 0; i < key.length; i++) sum += key.charCodeAt(i)
	const color = palette[sum % palette.length]
	const colorMap = theme.backgroundColor[color] || theme.backgroundColor.blue
	return `radial-gradient(ellipse 140% 100% at 100% 0%, ${colorMap[300]} 0%, ${colorMap[600]} 45%, #16222e 100%)`
}
</script>
<style scoped>
.lms-program-card__serif {
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

.lms-program-card__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
	font-variant-numeric: tabular-nums;
}
</style>
