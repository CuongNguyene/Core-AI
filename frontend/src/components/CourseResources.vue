<template>
	<div v-if="resources.data?.length || canManage">
		<div class="flex items-center justify-between mb-4">
			<div class="text-lg font-semibold text-ink-gray-9">
				{{ title || __('courses.resources.title') }}
			</div>
			<FileUploader v-if="canManage" :validateFile="validateFile" @success="onUploaded">
				<template v-slot="{ openFileSelector, uploading, progress }">
					<Button variant="subtle" @click="openFileSelector" :loading="uploading">
						<template #prefix>
							<Plus class="h-4 w-4" />
						</template>
						{{
							uploading
								? __('courses.resources.uploading').format(progress)
								: __('courses.resources.upload')
						}}
					</Button>
				</template>
			</FileUploader>
		</div>
		<div v-if="resources.data?.length" class="divide-y border rounded-md">
			<div
				v-for="resource in resources.data"
				:key="resource.name"
				class="flex items-center justify-between px-4 py-2.5"
			>
				<a
					:href="resource.attachment"
					target="_blank"
					download
					class="flex items-center min-w-0 text-ink-gray-8 hover:text-ink-gray-9"
				>
					<FileText class="h-4 w-4 mr-2 shrink-0 text-ink-gray-6" />
					<span class="truncate">{{ resource.title }}</span>
				</a>
				<Button
					v-if="canManage"
					variant="ghost"
					@click="deleteResource(resource.name)"
				>
					<Trash2 class="h-4 w-4 text-ink-gray-6" />
				</Button>
			</div>
		</div>
		<div v-else class="text-sm text-ink-gray-5">
			{{ __('courses.resources.empty') }}
		</div>
	</div>
</template>
<script setup>
import { createResource, FileUploader, Button, toast } from 'frappe-ui'
import { FileText, Plus, Trash2 } from 'lucide-vue-next'

const props = defineProps({
	courseName: {
		type: String,
		default: '',
	},
	batchName: {
		type: String,
		default: '',
	},
	canManage: {
		type: Boolean,
		default: false,
	},
	title: {
		type: String,
		default: '',
	},
})

const resources = createResource({
	url: 'lms.lms.doctype.lms_course_resource.lms_course_resource.get_course_resources',
	cache: ['course_resources', props.courseName, props.batchName],
	makeParams() {
		return {
			course: props.courseName || undefined,
			batch: props.batchName || undefined,
		}
	},
	auto: true,
})

const newResource = createResource({
	url: 'frappe.client.insert',
})

const deleteResourceCall = createResource({
	url: 'frappe.client.delete',
})

const validateFile = (file) => {
	if (file.size > 25 * 1024 * 1024) {
		return __('courses.resources.fileTooLarge')
	}
}

const onUploaded = (file) => {
	newResource.submit(
		{
			doc: {
				doctype: 'LMS Course Resource',
				title: file.file_name || file.name,
				attachment: file.file_url,
				course: props.courseName || null,
				batch: props.batchName || null,
			},
		},
		{
			onSuccess() {
				toast.success(__('courses.resources.uploadSuccess'))
				resources.reload()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const deleteResource = (name) => {
	deleteResourceCall.submit(
		{
			doctype: 'LMS Course Resource',
			name: name,
		},
		{
			onSuccess() {
				toast.success(__('courses.resources.deleteSuccess'))
				resources.reload()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}
</script>
