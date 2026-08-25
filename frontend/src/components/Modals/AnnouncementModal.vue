<template>
	<Dialog
		v-model="show"
		:options="{
			size: 'xl',
			actions: [
				{
					label: __('batches.announcements.submit'),
					variant: 'solid',
					onClick: (close) => makeAnnouncement(close),
				},
			],
		}"
	>
		<template #body-title>
			<h3 class="lms-announcement-modal__serif text-2xl leading-6 text-ink-gray-9">
				{{ __('batches.announcements.makeAnnouncement') }}
			</h3>
		</template>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<div class="">
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('batches.announcements.subject') }}
						<span class="text-ink-red-3">*</span>
					</div>
					<Input type="text" v-model="announcement.subject" />
				</div>
				<div class="">
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('batches.announcements.replyTo') }}
						<span class="text-ink-red-3">*</span>
					</div>
					<Input type="text" v-model="announcement.replyTo" />
				</div>
				<div class="mb-4">
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('batches.announcements.announcementLabel') }}
						<span class="text-ink-red-3">*</span>
					</div>
					<TextEditor
						:fixedMenu="true"
						@change="(val) => (announcement.announcement = val)"
						editorClass="prose-sm py-2 px-2 min-h-[200px] border-outline-gray-2 hover:border-outline-gray-3 rounded-b-md bg-surface-gray-3"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, Input, TextEditor, createResource, toast } from 'frappe-ui'
import { reactive } from 'vue'

const show = defineModel()

const props = defineProps({
	batch: {
		type: String,
		required: true,
	},
	students: {
		type: Array,
		required: true,
	},
})

const announcement = reactive({
	subject: '',
	replyTo: '',
	announcement: '',
})

const announcementResource = createResource({
	url: 'frappe.core.doctype.communication.email.make',
	makeParams(values) {
		return {
			recipients: announcement.replyTo,
			bcc: props.students.join(', '),
			subject: announcement.subject,
			content: announcement.announcement,
			doctype: 'LMS Batch',
			name: props.batch,
			send_email: 1,
		}
	},
})

const makeAnnouncement = (close) => {
	announcementResource.submit(
		{},
		{
			validate() {
				if (!props.students.length) {
					return __('batches.announcements.noStudents')
				}
				if (!announcement.subject) {
					return __('batches.announcements.subjectRequired')
				}
				if (!announcement.announcement) {
					return __('batches.announcements.announcementRequired')
				}
				if (!announcement.replyTo) {
					return __('batches.announcements.replyToRequired')
				}
			},
			onSuccess() {
				close()
				toast.success(__('batches.announcements.sentSuccess'))
			},
			onError(err) {
				toast.error(__(err.messages?.[0] || err))
			},
		}
	)
}
</script>
<style scoped>
.lms-announcement-modal__serif {
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
