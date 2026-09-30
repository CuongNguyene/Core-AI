<template>
	<FileUploader
		:fileTypes="['image/*', 'video/*', 'audio/*', '.pdf']"
		:validateFile="validateFile"
		@success="(data) => addFile(data)"
		@failure="onFailure"
		ref="fileUploader"
	>
		<template v-slot="{ uploading, progress, error }">
			<div
				v-if="loadingResources || uploading"
				class="flex items-center gap-2 p-3 text-sm text-ink-gray-6"
			>
				<LoadingIndicator class="h-4 w-4" />
				<span v-if="uploading">
					{{ __('Uploading...') }} {{ progress }}%
				</span>
				<span v-else>{{ __('Loading...') }}</span>
			</div>
			<div v-else-if="error" class="p-3 text-sm text-ink-red-4">
				{{ error }}
			</div>
		</template>
	</FileUploader>
	<Dialog v-model="showPicker" :options="{ size: 'lg' }">
		<template #body-title>
			<h3 class="lms-upload-plugin__serif text-2xl leading-6 text-ink-gray-9">
				{{ __('Add File') }}
			</h3>
		</template>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<Button @click="uploadNew">
					{{ __('Upload a new file') }}
				</Button>
				<div v-if="resources.data?.length">
					<div class="text-sm text-ink-gray-6 mb-2">
						{{ __('Or reuse a file already uploaded to this course') }}
					</div>
					<div class="divide-y border rounded-md max-h-64 overflow-y-auto">
						<div
							v-for="resource in resources.data"
							:key="resource.name"
							class="flex items-center px-3 py-2 cursor-pointer hover:bg-surface-gray-2"
							@click="useResource(resource)"
						>
							<FileText class="h-4 w-4 mr-2 shrink-0 text-ink-gray-6" />
							<span class="truncate">{{ resource.title }}</span>
						</div>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	FileUploader,
	LoadingIndicator,
	Dialog,
	Button,
	createResource,
	toast,
} from 'frappe-ui'
import { FileText } from 'lucide-vue-next'
import { onMounted, ref, nextTick } from 'vue'

const fileUploader = ref(null)
const showPicker = ref(false)
const loadingResources = ref(false)

const props = defineProps({
	onFileUploaded: {
		type: Function,
		required: true,
	},
	courseName: {
		type: String,
		default: '',
	},
})

const resources = createResource({
	url: 'lms.lms.doctype.lms_course_resource.lms_course_resource.get_course_resources',
	makeParams() {
		return {
			course: props.courseName || undefined,
		}
	},
})

onMounted(async () => {
	await nextTick()
	if (!props.courseName) {
		openFilePicker()
		return
	}

	loadingResources.value = true
	resources.fetch().then(() => {
		loadingResources.value = false
		if (resources.data?.length) {
			showPicker.value = true
		} else {
			openFilePicker()
		}
	}).catch(() => {
		loadingResources.value = false
		openFilePicker()
	})
})

const openFilePicker = () => {
	const fileInput = fileUploader.value.$el.querySelector('input[type="file"]')
	if (fileInput) {
		fileInput.click()
	}
}

const uploadNew = () => {
	showPicker.value = false
	nextTick(() => openFilePicker())
}

const useResource = (resource) => {
	showPicker.value = false
	const extension = (resource.attachment.split('.').pop() || '').toLowerCase()
	props.onFileUploaded({
		file_url: resource.attachment,
		file_type: extension,
	})
}

const addFile = (file) => {
	props.onFileUploaded({
		file_url: file.file_url,
		file_type: file.file_type,
	})
}

const onFailure = (error) => {
	toast.error(error?.messages?.[0] || __('Error uploading file'))
}

const validateFile = (file) => {
	let extension = file.name.split('.').pop().toLowerCase()
	if (!['jpg', 'jpeg', 'png', 'mp4', 'mov', 'mp3', 'pdf'].includes(extension)) {
		return 'Only image and video files are allowed.'
	}
}

const isVideo = (type) => {
	return ['mov', 'mp4', 'avi', 'mkv', 'webm'].includes(type.toLowerCase())
}

const isAudio = (type) => {
	return ['mp3', 'wav', 'ogg'].includes(type.toLowerCase())
}
</script>
<style scoped>
.lms-upload-plugin__serif {
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
</style>
