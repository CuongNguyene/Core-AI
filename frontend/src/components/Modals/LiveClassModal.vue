<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('batches.liveClass.createLiveClass'),
			size: 'xl',
			actions: [
				{
					label: __('batches.liveClass.submit'),
					variant: 'solid',
					onClick: ({ close }) => submitLiveClass(close),
				},
			],
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<div class="grid grid-cols-2 gap-4">
					<div class="space-y-4">
						<FormControl
							type="text"
							v-model="liveClass.title"
							:label="__('batches.liveClass.title')"
							:required="true"
						/>
						<FormControl
							v-model="liveClass.date"
							type="date"
							:label="__('batches.liveClass.date')"
							:required="true"
						/>
						<Tooltip :text="__('batches.liveClass.durationTooltip')">
							<FormControl
								type="number"
								v-model="liveClass.duration"
								:label="__('batches.liveClass.duration')"
								:required="true"
							/>
						</Tooltip>
					</div>
					<div class="space-y-4">
						<Tooltip
							:text="
								__(
									'batches.liveClass.timeTooltip'
								)
							"
						>
							<FormControl
								v-model="liveClass.time"
								type="time"
								:label="__('batches.liveClass.time')"
								:required="true"
							/>
						</Tooltip>

						<div class="space-y-1.5">
							<label class="block text-ink-gray-5 text-xs" for="batchTimezone">
								{{ __('batches.liveClass.timezone') }}
								<span class="text-ink-red-3">*</span>
							</label>
							<Autocomplete
								@update:modelValue="(opt) => (liveClass.timezone = opt.value)"
								:modelValue="liveClass.timezone"
								:options="getTimezoneOptions()"
								:required="true"
							/>
						</div>
						<FormControl
							v-model="liveClass.auto_recording"
							type="select"
							:options="getRecordingOptions()"
							:label="__('batches.liveClass.autoRecording')"
						/>
					</div>
				</div>
				<FormControl
					v-model="liveClass.description"
					type="textarea"
					:label="__('batches.liveClass.description')"
				/>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	Dialog,
	createResource,
	Tooltip,
	FormControl,
	Autocomplete,
	toast,
} from 'frappe-ui'
import { reactive, inject, onMounted } from 'vue'
import { getTimezones, getUserTimezone } from '@/utils/'

const liveClasses = defineModel('reloadLiveClasses')
const show = defineModel()
const user = inject('$user')
const dayjs = inject('$dayjs')

const props = defineProps({
	batch: {
		type: String,
		required: true,
	},
	zoomAccount: {
		type: String,
		required: true,
	},
})

let liveClass = reactive({
	title: '',
	description: '',
	date: '',
	time: '',
	duration: '',
	timezone: '',
	auto_recording: 'No Recording',
	batch: props.batch,
	host: user.data.name,
})

onMounted(() => {
	liveClass.timezone = getUserTimezone()
})

const getTimezoneOptions = () => {
	return getTimezones().map((timezone) => {
		return {
			label: timezone,
			value: timezone,
		}
	})
}

const getRecordingOptions = () => {
	return [
		{
			label: __('batches.liveClass.noRecording'),
			value: 'No Recording',
		},
		{
			label: __('batches.liveClass.local'),
			value: 'Local',
		},
		{
			label: __('batches.liveClass.cloud'),
			value: 'Cloud',
		},
	]
}

const createLiveClass = createResource({
	url: 'lms.lms.doctype.lms_batch.lms_batch.create_live_class',
	makeParams(values) {
		return {
			doctype: 'LMS Live Class',
			batch_name: values.batch,
			zoom_account: props.zoomAccount,
			...values,
		}
	},
})

const submitLiveClass = (close) => {
	return createLiveClass.submit(liveClass, {
		validate() {
			validateFormFields()
		},
		onSuccess() {
			liveClasses.value.reload()
			refreshForm()
			close()
		},
		onError(err) {
			toast.error(err.messages?.[0] || err)
		},
	})
}

const validateFormFields = () => {
	if (!liveClass.title) {
		return __('batches.liveClass.titleRequired')
	}
	if (!liveClass.date) {
		return __('batches.liveClass.dateRequired')
	}
	if (!liveClass.time) {
		return __('batches.liveClass.timeRequired')
	}
	if (!liveClass.timezone) {
		return __('batches.liveClass.timezoneRequired')
	}
	if (!valideTime()) {
		return __('batches.liveClass.invalidTimeFormat')
	}
	const liveClassDateTime = dayjs(`${liveClass.date}T${liveClass.time}`).tz(
		liveClass.timezone,
		true
	)
	if (
		liveClassDateTime.isSameOrBefore(
			dayjs().tz(liveClass.timezone, false),
			'minute'
		)
	) {
		return __('batches.liveClass.futureDateTimeRequired')
	}
	if (!liveClass.duration) {
		return __('batches.liveClass.durationRequired')
	}
}

const valideTime = () => {
	let time = liveClass.time.split(':')
	if (time.length != 2) {
		return false
	}
	if (time[0] < 0 || time[0] > 23) {
		return false
	}
	if (time[1] < 0 || time[1] > 59) {
		return false
	}
	return true
}

const refreshForm = () => {
	liveClass.title = ''
	liveClass.description = ''
	liveClass.date = ''
	liveClass.time = ''
	liveClass.duration = ''
	liveClass.timezone = getUserTimezone()
	liveClass.auto_recording = 'No Recording'
}
</script>
