<template>
	<div class="flex flex-col items-center justify-center mt-60">
		<GraduationCap class="size-10 mx-auto stroke-1 text-ink-gray-5" />
		<div class="text-lg font-semibold text-ink-gray-7 mb-2.5">
			{{ __('common.emptyState.noItems').format(translatedType) }}
		</div>
		<div
			class="leading-5 text-base w-full md:w-2/5 text-base text-center text-ink-gray-7"
		>
			{{ __('common.emptyState.description').format(translatedType) }}
		</div>
	</div>
</template>
<script setup lang="ts">
import { BookOpen, GraduationCap } from 'lucide-vue-next'
import { computed } from 'vue'

const props = defineProps({
	type: String,
})

const typeKeys: Record<string, string> = {
	Batches: 'common.emptyState.type.batches',
	Courses: 'common.emptyState.type.courses',
	Quizzes: 'common.emptyState.type.quizzes',
	Assignments: 'common.emptyState.type.assignments',
	Submissions: 'common.emptyState.type.submissions',
	'Certified Members': 'common.emptyState.type.certifiedMembers',
	'Job Openings': 'common.emptyState.type.jobOpenings',
	'Programming Exercises': 'common.emptyState.type.programmingExercises',
	'Programming Exercise Submissions':
		'common.emptyState.type.programmingExerciseSubmissions',
	Programs: 'common.emptyState.type.programs',
}

const translatedType = computed(() => {
	if (!props.type) return ''
	const key = typeKeys[props.type]
	return key ? __(key) : props.type.toLowerCase()
})
</script>
