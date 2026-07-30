<template>
	<div
		v-if="title"
		class="flex flex-col h-full rounded-md overflow-auto text-ink-gray-9"
	>
		<div
			class="w-[100%] h-[168px] bg-cover bg-center bg-no-repeat border-t border-x rounded-t-md"
			:style="{
				backgroundImage: getGradientColor(),
				backgroundBlendMode: 'screen',
			}"
		>
			<div
				class="flex items-center justify-center text-white flex-1 font-extrabold my-auto px-5 text-center leading-6 h-full"
				:class="
					title.length > 32
						? 'text-lg'
						: title.length > 20
						? 'text-xl'
						: 'text-2xl'
				"
			>
				{{ title }}
			</div>
		</div>
		<div class="flex flex-col flex-auto p-4 border-x-2 border-b-2 rounded-b-md">
			<div class="flex items-center justify-between">
				<Tooltip :text="__('programs.list.courses')">
					<span class="flex items-center">
						<BookOpen class="h-4 w-4 stroke-1.5 mr-1" />
						{{ program.course_count || 0 }}
					</span>
				</Tooltip>

				<Tooltip :text="__('programs.form.members')">
					<span class="flex items-center">
						<Users class="h-4 w-4 stroke-1.5 mr-1" />
						{{ program.member_count || 0 }}
					</span>
				</Tooltip>

				<Tooltip
					v-if="program.enforce_course_order"
					:text="__('programs.list.sequentialTooltip')"
				>
					<span class="flex items-center text-ink-gray-7">
						<ListOrdered class="h-4 w-4 stroke-1.5" />
					</span>
				</Tooltip>
			</div>

			<div v-if="hasProgress" class="mt-4">
				<ProgressBar :progress="program.progress" />
				<div class="text-sm text-ink-gray-7 mt-1">
					{{ Math.ceil(program.progress) }}% {{ __('programs.completed') }}
				</div>
			</div>

			<div v-if="hasBadges" class="flex items-center gap-2 mt-4">
				<Badge
					v-if="'published' in program"
					:theme="program.published ? 'green' : 'gray'"
					variant="subtle"
					:label="program.published ? __('programs.form.published') : __('programs.list.unpublished')"
				/>
				<Badge
					v-if="program.enforce_course_order"
					theme="blue"
					variant="subtle"
					:label="__('programs.list.sequential')"
				/>
			</div>
		</div>
	</div>
</template>
<script setup>
import { Badge, Tooltip } from 'frappe-ui'
import { BookOpen, ListOrdered, Users } from 'lucide-vue-next'
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

const hasProgress = computed(
	() => 'progress' in props.program && props.program.progress != null
)

const hasBadges = computed(
	() => 'published' in props.program || !!props.program.enforce_course_order
)

const palette = ['blue', 'green', 'orange', 'red', 'purple', 'teal', 'pink']

const getGradientColor = () => {
	const key = title.value
	let sum = 0
	for (let i = 0; i < key.length; i++) sum += key.charCodeAt(i)
	const color = palette[sum % palette.length]
	const colorMap = theme.backgroundColor[color] || theme.backgroundColor.blue
	return `linear-gradient(to top right, black, ${colorMap[400]})`
}
</script>
