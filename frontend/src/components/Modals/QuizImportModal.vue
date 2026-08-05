<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="flex flex-col gap-4 text-base">
				<div class="flex items-start justify-between gap-4">
					<p class="text-ink-gray-7">
						{{ __('quiz.io.importDescription') }}
					</p>
					<Button class="shrink-0" @click="downloadTemplate()">
						<template #prefix>
							<Download class="size-4 stroke-1.5" />
						</template>
						{{ __('quiz.io.downloadTemplate') }}
					</Button>
				</div>

				<FileUploader
					v-if="!file"
					:fileTypes="['.xlsx']"
					:validateFile="validateFile"
					@success="onUpload"
				>
					<template v-slot="{ progress, uploading, openFileSelector }">
						<Button variant="subtle" :loading="uploading" @click="openFileSelector">
							<template #prefix>
								<Upload class="size-4 stroke-1.5" />
							</template>
							{{
								uploading
									? __('quiz.io.uploading').format(progress)
									: __('quiz.io.uploadFile')
							}}
						</Button>
					</template>
				</FileUploader>

				<div v-else class="flex items-center justify-between border rounded-md p-3">
					<div class="flex items-center">
						<FileSpreadsheet class="size-5 stroke-1.5 text-ink-gray-7 mr-2" />
						<span class="text-ink-gray-9">{{ file.file_name }}</span>
					</div>
					<Button variant="ghost" @click="reset()">
						{{ __('quiz.io.remove') }}
					</Button>
				</div>

				<div v-if="validation.loading" class="text-ink-gray-6">
					{{ __('quiz.io.validating') }}
				</div>

				<div v-if="report" class="flex flex-col gap-3">
					<div v-if="hasErrors">
						<div class="text-ink-red-3 font-medium mb-2">
							{{ __('quiz.io.validationFailed').format(report.errors.length) }}
						</div>
						<div class="max-h-60 overflow-y-auto border rounded-md divide-y">
							<div
								v-for="(error, index) in report.errors"
								:key="index"
								class="flex gap-3 p-2 text-sm"
							>
								<span class="shrink-0 text-ink-gray-5 w-20">
									{{ __('quiz.io.row').format(error.row) }}
								</span>
								<span class="shrink-0 text-ink-gray-5 w-44 truncate">
									{{ error.column || '-' }}
								</span>
								<span class="text-ink-gray-8">{{ error.message }}</span>
							</div>
						</div>
						<div v-if="report.truncated" class="text-sm text-ink-gray-5 mt-2">
							{{ __('quiz.io.errorsTruncated') }}
						</div>
					</div>

					<div v-else class="flex flex-col gap-2">
						<div class="text-ink-gray-9 font-medium">
							{{ __('quiz.io.readyToImport').format(newQuestionCount) }}
						</div>
						<div
							v-for="quiz in report.quizzes"
							:key="quiz.quiz_title"
							class="flex items-center gap-2 text-sm"
						>
							<Badge
								:theme="quiz.exists ? 'blue' : 'green'"
								variant="subtle"
								:label="
									quiz.exists ? __('quiz.io.existing') : __('quiz.io.new')
								"
							/>
							<span class="text-ink-gray-8">{{ quiz.quiz_title }}</span>
							<span class="text-ink-gray-5">
								{{ __('quiz.io.quizSummary').format(quiz.new_questions, quiz.skipped) }}
							</span>
						</div>
						<div v-if="report.skipped?.length" class="text-sm text-ink-gray-5">
							{{ __('quiz.io.skippedNote').format(report.skipped.length) }}
						</div>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Badge, Button, Dialog, FileUploader, createResource, toast } from 'frappe-ui'
import { Download, FileSpreadsheet, Upload } from 'lucide-vue-next'
import { computed, ref } from 'vue'

const show = defineModel()
const emit = defineEmits(['imported'])

const file = ref(null)
const report = ref(null)

const hasErrors = computed(() => !!report.value?.errors?.length)

const newQuestionCount = computed(() =>
	(report.value?.quizzes || []).reduce((sum, quiz) => sum + quiz.new_questions, 0)
)

const canImport = computed(
	() => !!report.value && !hasErrors.value && newQuestionCount.value > 0
)

const validateFile = (uploadedFile) => {
	if (!uploadedFile.name.toLowerCase().endsWith('.xlsx')) {
		return __('quiz.io.onlyXlsx')
	}
}

const downloadTemplate = () => {
	window.open(
		'/api/method/lms.lms.doctype.lms_quiz.quiz_import_export.download_template'
	)
}

const reset = () => {
	file.value = null
	report.value = null
}

const onUpload = (uploadedFile) => {
	file.value = uploadedFile
	report.value = null
	validation.submit({ file_url: uploadedFile.file_url })
}

const validation = createResource({
	url: 'lms.lms.doctype.lms_quiz.quiz_import_export.validate_import',
	onSuccess(data) {
		report.value = data
	},
	onError(err) {
		reset()
		toast.error(err.messages?.[0] || err)
	},
})

const importResource = createResource({
	url: 'lms.lms.doctype.lms_quiz.quiz_import_export.import_quiz',
	onError(err) {
		toast.error(err.messages?.[0] || err)
	},
})

const startImport = (close) => {
	importResource.submit(
		{ file_url: file.value.file_url },
		{
			onSuccess(data) {
				if (!data.success) {
					report.value = data
					return
				}
				const questions = data.imported.reduce(
					(sum, quiz) => sum + quiz.new_questions,
					0
				)
				toast.success(
					__('quiz.io.importSuccess').format(questions, data.imported.length)
				)
				emit('imported')
				reset()
				close()
			},
		}
	)
}

const dialogOptions = computed(() => {
	return {
		title: __('quiz.io.import'),
		size: '2xl',
		actions: canImport.value
			? [
					{
						label: __('quiz.io.importAction'),
						variant: 'solid',
						loading: importResource.loading,
						onClick: (close) => startImport(close),
					},
			  ]
			: [],
	}
})
</script>
