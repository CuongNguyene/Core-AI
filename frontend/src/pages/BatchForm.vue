<template>
	<div class="">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<div class="flex items-center space-x-2">
				<Button v-if="batchDetail.data?.name" @click="deleteBatch">
					<template #icon>
						<Trash2 class="size-4 stroke-1.5" />
					</template>
				</Button>
				<Button variant="solid" @click="saveBatch()">
					{{ __('batches.form.save') }}
				</Button>
			</div>
		</header>
		<div class="py-5">
			<div class="px-5 md:px-20 pb-5 space-y-5 border-b mb-5">
				<div class="text-lg text-ink-gray-9 font-semibold mb-4">
					{{ __('batches.form.details') }}
				</div>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
					<div class="space-y-5">
						<FormControl
							v-model="batch.title"
							:label="__('batches.form.title')"
							:required="true"
							class="w-full"
							:placeholder="__('batches.form.enterTitle')"
						/>
						<MultiSelect
							v-model="instructors"
							doctype="Course Evaluator"
							:label="__('batches.form.instructors')"
							:required="true"
							:onCreate="(close) => openSettings('Evaluators', close)"
							:filters="{ ignore_user_type: 1 }"
						/>
					</div>
					<FormControl
						v-model="batch.description"
						:label="__('batches.form.shortDescription')"
						type="textarea"
						:rows="8"
						:placeholder="__('batches.form.shortDescriptionPlaceholder')"
						:required="true"
					/>
				</div>
			</div>

			<div class="px-5 md:px-20 pb-5 space-y-5 border-b mb-5">
				<div class="text-lg text-ink-gray-9 font-semibold mb-4">
					{{ __('batches.form.settings') }}
				</div>
				<div class="grid grid-cols-1 md:grid-cols-3 gap-5">
					<FormControl
						v-model="batch.published"
						type="checkbox"
						:label="__('batches.form.published')"
					/>
					<FormControl
						v-model="batch.allow_self_enrollment"
						type="checkbox"
						:label="__('batches.form.allowSelfEnrollment')"
					/>
					<FormControl
						v-model="batch.certification"
						type="checkbox"
						:label="__('batches.form.certification')"
					/>
				</div>
			</div>

			<div class="px-5 md:px-20 pb-5 space-y-5 border-b mb-5">
				<div class="text-lg text-ink-gray-9 font-semibold mb-4">
					{{ __('batches.form.dateAndTime') }}
				</div>
				<div class="grid grid-cols-1 md:grid-cols-3 gap-10">
					<div class="space-y-5">
						<FormControl
							v-model="batch.start_date"
							:label="__('batches.form.batchStartDate')"
							type="date"
							class="mb-4"
							:required="true"
						/>
						<FormControl
							v-model="batch.end_date"
							:label="__('batches.form.batchEndDate')"
							type="date"
							class="mb-4"
							:required="true"
						/>
					</div>
					<div class="space-y-5">
						<FormControl
							v-model="batch.start_time"
							:label="__('batches.form.sessionStartTime')"
							type="time"
							class="mb-4"
							:required="true"
						/>
						<FormControl
							v-model="batch.end_time"
							:label="__('batches.form.sessionEndTime')"
							type="time"
							class="mb-4"
							:required="true"
						/>
					</div>
					<div class="space-y-5">
						<FormControl
							v-model="batch.timezone"
							:label="__('batches.form.timezone')"
							type="text"
							:placeholder="__('batches.form.timezonePlaceholder')"
							class="mb-4"
							:required="true"
						/>
						<FormControl
							v-model="batch.evaluation_end_date"
							:label="__('batches.form.evaluationEndDate')"
							type="date"
							class="mb-4"
						/>
					</div>
				</div>
			</div>

			<div class="px-5 md:px-20 pb-5 space-y-5 border-b mb-5">
				<div>
					<label class="block text-sm text-ink-gray-5 mb-1">
						{{ __('batches.form.batchDetails') }}
						<span class="text-ink-red-3">*</span>
					</label>
					<TextEditor
						:content="batch.batch_details"
						@change="(val) => (batch.batch_details = val)"
						:editable="true"
						:fixedMenu="true"
						editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem] max-h-[20rem] overflow-y-scroll mb-4"
						:placeholder="__('batches.form.batchDetailsPlaceholder')"
					/>
				</div>
			</div>

			<div class="px-5 md:px-20 pb-5 space-y-5 border-b mb-5">
				<div class="text-lg text-ink-gray-9 font-semibold mb-4">
					{{ __('batches.form.configurations') }}
				</div>
				<div class="grid grid-cols-1 md:grid-cols-3 gap-10">
					<div class="space-y-5">
						<FormControl
							v-model="batch.seat_count"
							:label="__('batches.form.seatCount')"
							type="number"
							class="mb-4"
							:placeholder="__('batches.form.seatCountPlaceholder')"
						/>
						<Link
							doctype="Email Template"
							:filters="{ is_lms_template: 1 }"
							:label="__('batches.form.emailTemplate')"
							v-model="batch.confirmation_email_template"
							:onCreate="
								(value, close) => {
									openSettings('Email Templates', close)
								}
							"
							:placeholder="__('batches.form.emailTemplatePlaceholder')"
						/>
						<Link
							doctype="LMS Zoom Settings"
							:label="__('batches.form.zoomAccount')"
							v-model="batch.zoom_account"
							:onCreate="
								(value, close) => {
									openSettings('Zoom Accounts', close)
								}
							"
							:placeholder="__('batches.form.zoomAccountPlaceholder')"
						/>
					</div>
					<div class="space-y-5">
						<FormControl
							v-model="batch.medium"
							type="select"
							:options="[
								{
									label: 'Online',
									value: 'Online',
								},
								{
									label: 'Offline',
									value: 'Offline',
								},
							]"
							:label="__('batches.form.medium')"
							class="mb-4"
						/>
						<Link
							doctype="LMS Category"
							:label="__('batches.form.category')"
							v-model="batch.category"
							:onCreate="(value, close) => openSettings('Categories', close)"
							:placeholder="__('batches.form.categoryPlaceholder')"
						/>
					</div>
					<div class="space-y-5">
						<div>
							<div class="text-xs text-ink-gray-5">
								{{ __('batches.form.metaImage') }}
							</div>
							<FileUploader
								v-if="!batch.image"
								:fileTypes="['image/*']"
								:validateFile="validateFile"
								@success="(file) => saveImage(file)"
							>
								<template
									v-slot="{ file, progress, uploading, openFileSelector }"
								>
									<div class="flex items-center">
										<div
											class="border rounded-md w-fit py-5 px-5 md:px-20 cursor-pointer"
											@click="openFileSelector"
										>
											<Image class="size-5 stroke-1 text-ink-gray-7" />
										</div>
										<div class="ml-4">
											<Button @click="openFileSelector">
												{{ __('batches.form.upload') }}
											</Button>
											<div class="mt-1 text-ink-gray-5 text-sm leading-5">
												{{
													__('batches.form.metaImageHintUpload')
												}}
											</div>
										</div>
									</div>
								</template>
							</FileUploader>
							<div v-else class="mb-4">
								<div class="flex items-center">
									<img
										:src="batch.image.file_url"
										class="border rounded-md w-40"
									/>
									<div class="ml-4">
										<Button @click="removeImage()">
											{{ __('batches.form.remove') }}
										</Button>
										<div class="mt-2 text-ink-gray-5 text-sm">
											{{
												__(
													'batches.form.metaImageHint'
												)
											}}
										</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>

			<!-- <div class="px-5 md:px-20 pb-5 space-y-5">
				<div class="text-lg text-ink-gray-9 font-semibold">
					{{ __('Pricing') }}
				</div>
				<FormControl
					v-model="batch.paid_batch"
					type="checkbox"
					:label="__('Paid Batch')"
				/>
				<div
					v-if="batch.paid_batch"
					class="grid grid-cols-1 md:grid-cols-3 gap-5"
				>
					<FormControl
						v-model="batch.amount"
						:label="__('Amount')"
						type="number"
					/>
					<Link
						doctype="Currency"
						v-model="batch.currency"
						:filters="{ enabled: 1 }"
						:label="__('Currency')"
					/>
				</div>
			</div> -->

			<div class="px-5 md:px-20 pb-5 space-y-5 border-b">
				<div class="text-lg text-ink-gray-9 font-semibold">
					{{ __('batches.form.metaTags') }}
				</div>
				<div class="space-y-5">
					<FormControl
						v-model="meta.description"
						:label="__('batches.form.metaDescription')"
						type="textarea"
						:rows="7"
					/>
					<FormControl
						v-model="meta.keywords"
						:label="__('batches.form.metaKeywords')"
						type="textarea"
						:rows="7"
						:placeholder="__('batches.form.metaKeywordsPlaceholder')"
					/>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import {
	computed,
	getCurrentInstance,
	inject,
	onMounted,
	onBeforeUnmount,
	reactive,
	ref,
} from 'vue'
import {
	Breadcrumbs,
	FormControl,
	FileUploader,
	Button,
	TextEditor,
	createResource,
	usePageMeta,
	toast,
	call,
	Toast,
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import { Image, Trash2 } from 'lucide-vue-next'
import { capture } from '@/telemetry'
import { useOnboarding } from '@/utils/onboardingCompat'
import { sessionStore } from '../stores/session'
import MultiSelect from '@/components/Controls/MultiSelect.vue'
import Link from '@/components/Controls/Link.vue'
import {
	openSettings,
	getMetaInfo,
	updateMetaInfo,
	validateFile,
} from '@/utils'

const router = useRouter()
const user = inject('$user')
const { brand } = sessionStore()
const { updateOnboardingStep } = useOnboarding('learning')
const instructors = ref([])
const app = getCurrentInstance()
const { $dialog } = app.appContext.config.globalProperties

const props = defineProps({
	batchName: {
		type: String,
		required: true,
	},
})

const batch = reactive({
	title: '',
	published: false,
	description: '',
	batch_details: '',
	start_date: '',
	end_date: '',
	start_time: '',
	end_time: '',
	timezone: '',
	evaluation_end_date: '',
	confirmation_email_template: '',
	seat_count: '',
	medium: '',
	category: '',
	allow_self_enrollment: false,
	certification: false,
	image: null,
	paid_batch: false,
	currency: '',
	amount: 0,
	zoom_account: '',
})

const meta = reactive({
	description: '',
	keywords: '',
})

onMounted(() => {
	if (!user.data) window.location.href = '/login'
	if (props.batchName != 'new') {
		fetchBatchInfo()
	} else {
		capture('batch_form_opened')
	}
	window.addEventListener('keydown', keyboardShortcut)
})

const fetchBatchInfo = () => {
	batchDetail.reload()
	getMetaInfo('batches', props.batchName, meta)
}

const keyboardShortcut = (e) => {
	if (
		e.key === 's' &&
		(e.ctrlKey || e.metaKey) &&
		!e.target.classList.contains('ProseMirror')
	) {
		saveBatch()
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
})

const newBatch = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'LMS Batch',
				meta_image: batch.image?.file_url,
				instructors: instructors.value.map((instructor) => ({
					instructor: instructor,
				})),
				...batch,
			},
		}
	},
})

const batchDetail = createResource({
	url: 'frappe.client.get',
	makeParams(values) {
		return {
			doctype: 'LMS Batch',
			name: props.batchName,
		}
	},
	onSuccess(data) {
		Object.keys(data).forEach((key) => {
			if (key == 'instructors') {
				data.instructors.forEach((instructor) => {
					instructors.value.push(instructor.instructor)
				})
			} else if (['start_time', 'end_time'].includes(key)) {
				let [hours, minutes, seconds] = data[key].split(':')
				hours = hours.length == 1 ? '0' + hours : hours
				batch[key] = `${hours}:${minutes}`
			} else if (Object.hasOwn(batch, key)) batch[key] = data[key]
		})
		let checkboxes = [
			'published',
			'paid_batch',
			'allow_self_enrollment',
			'certification',
		]
		for (let idx in checkboxes) {
			let key = checkboxes[idx]
			batch[key] = batch[key] ? true : false
		}
		if (data.meta_image) imageResource.reload({ image: data.meta_image })
	},
})

const editBatch = createResource({
	url: 'frappe.client.set_value',
	makeParams(values) {
		return {
			doctype: 'LMS Batch',
			name: props.batchName,
			fieldname: {
				meta_image: batch.image?.file_url,
				instructors: instructors.value.map((instructor) => ({
					instructor: instructor,
				})),
				...batch,
			},
		}
	},
})

const imageResource = createResource({
	url: 'lms.lms.api.get_file_info',
	makeParams(values) {
		return {
			file_url: values.image,
		}
	},
	auto: false,
	onSuccess(data) {
		batch.image = data
	},
})

const saveBatch = () => {
	if (batchDetail.data) {
		editBatchDetails()
	} else {
		createNewBatch()
	}
}

const createNewBatch = () => {
	newBatch.submit(
		{},
		{
			onSuccess(data) {
				if (user.data?.is_system_manager) {
					updateOnboardingStep('create_first_batch', true, false, () => {
						localStorage.setItem('firstBatch', data.name)
					})
				}
				updateMetaInfo('batches', data.name, meta)
				capture('batch_created')
				router.push({
					name: 'BatchDetail',
					params: {
						batchName: data.name,
					},
				})
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const editBatchDetails = () => {
	editBatch.submit(
		{},
		{
			onSuccess(data) {
				updateMetaInfo('batches', data.name, meta)
				router.push({
					name: 'BatchDetail',
					params: {
						batchName: data.name,
					},
				})
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const deleteBatch = () => {
	$dialog({
		title: __('batches.form.confirmDelete'),
		message: __(
			'batches.form.deleteMessage'
		),
		actions: [
			{
				label: __('batches.form.delete'),
				theme: 'red',
				variant: 'solid',
				onClick({ close }) {
					trashBatch(close)
					close()
				},
			},
		],
	})
}

const trashBatch = (close) => {
	call('lms.lms.api.delete_batch', {
		batch: props.batchName,
	}).then(() => {
		toast.success(__('batches.form.batchDeleted'))
		close()
		router.push({
			name: 'Batches',
		})
	})
}

const saveImage = (file) => {
	batch.image = file
}

const removeImage = () => {
	batch.image = null
}

const breadcrumbs = computed(() => {
	let crumbs = [
		{
			label: __('batches.form.batches'),
			route: {
				name: 'Batches',
			},
		},
	]
	if (batchDetail.data) {
		crumbs.push({
			label: batchDetail.data.title,
			route: {
				name: 'BatchDetail',
				params: {
					batchName: props.batchName,
				},
			},
		})
	}
	crumbs.push({
		label: props.batchName == 'new' ? __('batches.form.newBatch') : __('batches.form.editBatch'),
		route: { name: 'BatchForm', params: { batchName: props.batchName } },
	})
	return crumbs
})

usePageMeta(() => {
	return {
		title: props.batchName == 'new' ? __('batches.form.newBatch') : batchDetail.data?.title,
		icon: brand.favicon,
	}
})
</script>
