<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="flex flex-col gap-4 text-base">
				<div class="flex items-end gap-3">
					<FormControl
						type="number"
						:min="1"
						:max="questions.length"
						v-model="from"
						:label="__('quiz.export.from')"
						class="w-28"
					/>
					<FormControl
						type="number"
						:min="1"
						:max="questions.length"
						v-model="to"
						:label="__('quiz.export.to')"
						class="w-28"
					/>
					<Button @click="selectRange()">
						{{ __('quiz.export.selectRange') }}
					</Button>
				</div>
				<div v-if="rangeError" class="-mt-2 text-sm text-ink-red-3">
					{{ rangeError }}
				</div>

				<div class="flex items-center justify-between">
					<div class="text-ink-gray-7">
						{{ __('quiz.export.selectedCount').format(selected.length, questions.length) }}
					</div>
					<Button variant="ghost" @click="toggleAll()">
						{{
							selected.length
								? __('quiz.export.clearAll')
								: __('quiz.export.selectAll')
						}}
					</Button>
				</div>

				<div class="max-h-80 overflow-y-auto border rounded-md divide-y">
					<label
						v-for="(question, index) in questions"
						:key="question.name"
						class="flex items-start gap-3 p-2 cursor-pointer hover:bg-surface-gray-1"
					>
						<input
							type="checkbox"
							class="mt-1 rounded border-outline-gray-2"
							:value="index + 1"
							v-model="selected"
						/>
						<span class="text-sm text-ink-gray-5 w-6 shrink-0">
							{{ index + 1 }}
						</span>
						<span class="text-sm text-ink-gray-5 w-32 shrink-0 truncate">
							{{ question.question }}
						</span>
						<span
							class="text-sm text-ink-gray-8 truncate"
							v-html="question.question_detail"
						></span>
					</label>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Button, Dialog, FormControl, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const show = defineModel()

const props = defineProps({
	quizName: {
		type: String,
		required: true,
	},
	questions: {
		type: Array,
		default: () => [],
	},
})

const from = ref(1)
const to = ref(1)
const selected = ref([])

watch(show, (value) => {
	if (!value) return
	from.value = 1
	to.value = props.questions.length || 1
	selected.value = props.questions.map((question, index) => index + 1)
})

const rangeError = computed(() => {
	const total = props.questions.length
	const start = parseInt(from.value)
	const end = parseInt(to.value)

	if (!start || !end) return __('quiz.export.rangeRequired')
	if (start < 1 || end < 1) return __('quiz.export.rangeMin')
	if (start > end) return __('quiz.export.rangeOrder')
	if (end > total) return __('quiz.export.rangeMax').format(total)
	return ''
})

const selectRange = () => {
	if (rangeError.value) {
		toast.error(rangeError.value)
		return
	}

	const start = parseInt(from.value)
	const end = parseInt(to.value)
	selected.value = Array.from({ length: end - start + 1 }, (_, i) => start + i)
}

const toggleAll = () => {
	if (selected.value.length) {
		selected.value = []
	} else {
		selected.value = props.questions.map((question, index) => index + 1)
	}
}

// Consecutive positions become '2-4' so the download URL stays short.
const collapse = (positions) => {
	const sorted = [...positions].sort((a, b) => a - b)
	const parts = []
	let start = sorted[0]
	let previous = sorted[0]

	for (const position of sorted.slice(1)) {
		if (position === previous + 1) {
			previous = position
			continue
		}
		parts.push(start === previous ? `${start}` : `${start}-${previous}`)
		start = previous = position
	}

	parts.push(start === previous ? `${start}` : `${start}-${previous}`)
	return parts.join(',')
}

const startExport = (close) => {
	if (!selected.value.length) {
		toast.error(__('quiz.export.noneSelected'))
		return
	}

	const params = new URLSearchParams({
		quiz: props.quizName,
		rows: collapse(selected.value),
	})

	window.open(
		`/api/method/lms.lms.doctype.lms_quiz.quiz_import_export.export_quiz?${params}`
	)
	close()
}

const dialogOptions = computed(() => {
	return {
		title: __('quiz.export.title'),
		size: 'xl',
		actions: [
			{
				label: __('quiz.io.export'),
				variant: 'solid',
				onClick: (close) => startExport(close),
			},
		],
	}
})
</script>
