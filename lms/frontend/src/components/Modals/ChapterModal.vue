<template>
	<Dialog
		v-model="show"
		:options="{
			title: chapterDetail ? __('courses.chapterModal.editChapter') : __('courses.chapterModal.addChapter'),
			size: 'lg',
			actions: [
				{
					label: chapterDetail ? __('courses.chapterModal.edit') : __('courses.chapterModal.create'),
					variant: 'solid',
					onClick: (close) =>
						chapterDetail ? editChapter(close) : addChapter(close),
				},
			],
		}"
	>
		<template #body-title>
			<h3 class="lms-chapter-modal__serif text-2xl leading-6 text-ink-gray-9">
				{{ chapterDetail ? __('courses.chapterModal.editChapter') : __('courses.chapterModal.addChapter') }}
			</h3>
		</template>
		<template #body-content>
			<div class="space-y-4 text-base">
				<FormControl :label="__('courses.chapterModal.title')" v-model="chapter.title" :required="true" />
				<!-- SCORM package upload is not currently used, hidden until needed.
				<Switch
					size="sm"
					:label="__('courses.chapterModal.scormPackage')"
					:description="
						__(
							'courses.chapterModal.scormDescription'
						)
					"
					v-model="chapter.is_scorm_package"
				/>
				<div v-if="chapter.is_scorm_package">
					<FileUploader
						v-if="!chapter.scorm_package"
						:fileTypes="['.zip']"
						:validateFile="validateFile"
						@success="(file) => (chapter.scorm_package = file)"
					>
						<template v-slot="{ file, progress, uploading, openFileSelector }">
							<div class="mb-4">
								<Button @click="openFileSelector" :loading="uploading">
									{{
										uploading ? __('courses.chapterModal.uploading').format(progress) : __('courses.chapterModal.uploadZip')
									}}
								</Button>
							</div>
						</template>
					</FileUploader>
					<div v-else class="">
						<div class="flex items-center">
							<div class="border rounded-md p-2 mr-2">
								<FileText class="h-5 w-5 stroke-1.5 text-ink-gray-7" />
							</div>
							<div class="flex flex-col">
								<span>
									{{ chapter.scorm_package.file_name }}
								</span>
								<span class="text-sm text-ink-gray-4 mt-1">
									{{ getFileSize(chapter.scorm_package.file_size) }}
								</span>
							</div>
							<X
								@click="() => (chapter.scorm_package = null)"
								class="bg-surface-gray-3 rounded-md cursor-pointer stroke-1.5 w-5 h-5 p-1 ml-4"
							/>
						</div>
					</div>
				</div>
				-->
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	Button,
	createResource,
	Dialog,
	FileUploader,
	FormControl,
	Switch,
	toast,
} from 'frappe-ui'
import { reactive, watch, inject } from 'vue'
import { getFileSize } from '@/utils/'
import { useTelemetry } from '@/telemetry'
import { FileText, X } from 'lucide-vue-next'
import { useOnboarding } from '@/utils/onboardingCompat'

const show = defineModel()
const outline = defineModel('outline')
const user = inject('$user')
const { capture } = useTelemetry()
const { updateOnboardingStep } = useOnboarding('learning')

const props = defineProps({
	course: {
		type: String,
		required: true,
	},
	chapterDetail: {
		type: Object,
	},
})

const chapter = reactive({
	title: '',
	is_scorm_package: 0,
	scorm_package: null,
})

const chapterResource = createResource({
	url: 'lms.lms.api.upsert_chapter',
	makeParams(values) {
		return {
			title: chapter.title,
			course: props.course,
			is_scorm_package: chapter.is_scorm_package,
			scorm_package: chapter.scorm_package,
			name: props.chapterDetail?.name,
		}
	},
})

const chapterReference = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Chapter Reference',
				chapter: values.name,
				parent: props.course,
				parenttype: 'LMS Course',
				parentfield: 'chapters',
			},
		}
	},
})

const addChapter = async (close) => {
	chapterResource.submit(
		{},
		{
			validate() {
				return validateChapter()
			},
			onSuccess: (data) => {
				if (user.data?.is_system_manager)
					updateOnboardingStep('create_first_chapter')

				capture('chapter_created')
				chapterReference.submit(
					{ name: data.name },
					{
						onSuccess(data) {
							cleanChapter()
							outline.value.reload()
							toast.success(__('courses.chapterModal.chapterAdded'))
						},
						onError(err) {
							toast.error(err.messages?.[0] || err)
						},
					}
				)
				close()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const validateChapter = () => {
	if (!chapter.title) {
		return __('courses.chapterModal.titleRequired')
	}
	if (chapter.is_scorm_package && !chapter.scorm_package) {
		return __('courses.chapterModal.scormRequired')
	}
}

const cleanChapter = () => {
	chapter.title = ''
	chapter.is_scorm_package = 0
	chapter.scorm_package = null
}

const editChapter = (close) => {
	chapterResource.submit(
		{},
		{
			validate() {
				if (!chapter.title) {
					return __('courses.chapterModal.titleRequired')
				}
			},
			onSuccess() {
				outline.value.reload()
				toast.success(__('courses.chapterModal.chapterUpdated'))
				close()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

watch(
	() => props.chapterDetail,
	(newChapter) => {
		chapter.title = newChapter?.title
		chapter.is_scorm_package = newChapter?.is_scorm_package
		chapter.scorm_package = newChapter?.scorm_package
	}
)

const validateFile = (file) => {
	let extension = file.name.split('.').pop().toLowerCase()
	if (extension !== 'zip') {
		return __('courses.chapterModal.onlyZipAllowed')
	}
}
</script>
<style scoped>
.lms-chapter-modal__serif {
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
