<template>
	<Dialog
		v-model="show"
		class="text-base"
		:options="{
			title: __('jobApplication.applyForJob'),
			size: 'lg',
			actions: [
				{
					label: __('jobApplication.submit'),
					variant: 'solid',
					onClick: (close) => {
						submitResume(close)
					},
				},
			],
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<p class="text-ink-gray-9">
					{{
						__(
							'jobApplication.description'
						)
					}}
				</p>
				<div v-if="!resume">
					<FileUploader
						:fileTypes="['.pdf']"
						:validateFile="validateFile"
						@success="
							(file) => {
								resume = file
							}
						"
					>
						<template v-slot="{ file, progress, uploading, openFileSelector }">
							<div class="">
								<Button @click="openFileSelector" :loading="uploading">
									{{
										uploading ? __('profile.coverImage.uploading').format(progress) : __('jobApplication.uploadResume')
									}}
								</Button>
							</div>
						</template>
					</FileUploader>
				</div>
				<div v-else class="flex items-center">
					<div class="border rounded-md p-2 mr-2">
						<FileText class="h-5 w-5 stroke-1.5 text-ink-gray-7" />
					</div>
					<div class="flex flex-col">
						<span class="text-ink-gray-9">
							{{ resume.file_name }}
						</span>
						<span class="text-sm text-ink-gray-4 mt-1">
							{{ getFileSize(resume.file_size) }}
						</span>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, FileUploader, Button, createResource, toast } from 'frappe-ui'
import { FileText } from 'lucide-vue-next'
import { ref, inject } from 'vue'
import { getFileSize } from '@/utils/'

const resume = ref(null)
const show = defineModel()
const user = inject('$user')
const application = defineModel('application')

const props = defineProps({
	job: {
		type: String,
		required: true,
	},
})

const validateFile = (file) => {
	let extension = file.name.split('.').pop().toLowerCase()
	if (extension != 'pdf') {
		return __('jobApplication.onlyPdfAllowed')
	}
}

const jobApplication = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'LMS Job Application',
				user: user.data?.name,
				resume: resume.value?.file_name,
				job: props.job,
			},
		}
	},
})

const submitResume = (close) => {
	jobApplication.submit(
		{},
		{
			validate() {
				if (!resume.value) {
					return __('jobApplication.uploadRequired')
				}
			},
			onSuccess() {
				toast.success(__('jobApplication.submittedSuccess'))
				application.value.reload()
				close()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}
</script>
