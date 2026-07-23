<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Generate Certificates'),
			size: 'lg',
			actions: [
				{
					label: 'Create',
					variant: 'solid',
					onClick: ({ close }) => {
						generateCertificates(close)
					},
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<Autocomplete
					:modelValue="details.evaluator"
					@update:modelValue="(opt) => (details.evaluator = opt?.value)"
					:label="__('Instructor')"
					:options="getInstructors()"
				/>
				<FormControl
					type="date"
					v-model="details.issue_date"
					:label="__('Issue Date')"
				/>
				<FormControl
					type="date"
					v-model="details.expiry_date"
					:label="__('Expiry Date')"
				/>
				<Autocomplete
					:modelValue="details.course"
					@update:modelValue="(opt) => (details.course = opt?.value)"
					:label="__('Course')"
					:options="getCourses()"
				/>
				<Autocomplete
					:modelValue="details.template"
					@update:modelValue="(opt) => (details.template = opt?.value)"
					:label="__('Template')"
					:options="templates.data || []"
				/>
				<Switch
					size="sm"
					:label="__('Published')"
					:description="
						__(
							'Enabling this will publish the certificate on the certified participants page.'
						)
					"
					v-model="details.published"
				/>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { inject, reactive } from 'vue'
import {
	call,
	createResource,
	createListResource,
	Dialog,
	FormControl,
	Switch,
	toast,
} from 'frappe-ui'
import Autocomplete from '@/components/Controls/Autocomplete.vue'

const show = defineModel()
const dayjs = inject('$dayjs')
const details = reactive({
	issue_date: dayjs().format('YYYY-MM-DD'),
	expiry_date: null,
	template: null,
	evaluator: null,
	course: null,
	published: true,
})

const props = defineProps({
	batch: {
		type: [Object, null],
		required: true,
	},
})

const templates = createListResource({
	doctype: 'Print Format',
	fields: ['name'],
	filters: {
		doc_type: 'LMS Certificate',
	},
	orderBy: 'name asc',
	pageLength: 100,
	auto: true,
	transform(data) {
		return data.map((template) => ({
			label: template.name,
			value: template.name,
		}))
	},
})

const createCertificate = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'LMS Certificate',
				issue_date: details.issue_date,
				expiry_date: details.expiry_date,
				template: details.template,
				published: details.published,
				course: values.course,
				batch_name: values.batch,
				member: values.member,
				evaluator: details.evaluator,
			},
		}
	},
})

const generateCertificates = async (close) => {
	let students = props.batch?.students || []

	let [courseDuplicates, batchDuplicates] = await Promise.all([
		call('frappe.client.get_list', {
			doctype: 'LMS Certificate',
			filters: {
				course: details.course,
				member: ['in', students],
			},
			fields: ['member'],
			limit_page_length: 0,
		}),
		call('frappe.client.get_list', {
			doctype: 'LMS Certificate',
			filters: {
				batch_name: props.batch.name,
				member: ['in', students],
			},
			fields: ['member'],
			limit_page_length: 0,
		}),
	])

	let alreadyCertified = new Set([
		...courseDuplicates.map((d) => d.member),
		...batchDuplicates.map((d) => d.member),
	])
	let eligibleStudents = students.filter((student) => !alreadyCertified.has(student))

	eligibleStudents.forEach((student) => {
		createCertificate.submit(
			{
				course: details.course,
				batch: props.batch.name,
				member: student,
			},
			{
				onError(err) {
					toast.error(err.messages?.[0] || err)
				},
			}
		)
	})
	close()

	if (eligibleStudents.length) {
		toast.success(__('Certificates generated successfully'))
	}
	if (alreadyCertified.size) {
		toast.info(
			__('{0} student(s) were already certified and were skipped').format(
				alreadyCertified.size
			)
		)
	}
}

const getCourses = () => {
	return props.batch?.courses.map((course) => {
		return {
			label: course.title || course.course,
			value: course.course,
		}
	})
}

const getInstructors = () => {
	return props.batch?.instructors.map((instructor) => {
		return {
			label: instructor.full_name,
			value: instructor.name,
		}
	})
}
</script>
