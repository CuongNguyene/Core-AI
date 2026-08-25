<template>
	<div class="mt-7 mb-10">
		<h2 class="lms-profile-certificates__serif mb-3 text-lg text-ink-gray-9">
			{{ __('certification.certificatesHeading') }}
		</h2>
		<div
			v-if="certificates.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
		>
			<div
				v-for="certificate in certificates.data"
				:key="certificate.name"
				class="flex items-start gap-3 rounded-md border border-outline-gray-2 bg-surface-white p-3 cursor-pointer hover:shadow-sm transition-shadow"
				@click="openCertificate(certificate)"
			>
				<div
					class="lms-profile-certificates__seal flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
				>
					<GraduationCap class="h-4 w-4 stroke-2" />
				</div>
				<div class="min-w-0 flex-1">
					<div class="lms-profile-certificates__serif leading-5 mb-2 text-ink-gray-9">
						{{ certificate.course_title || certificate.batch_title }}
					</div>
					<div class="lms-profile-certificates__mono text-sm text-ink-gray-6">
						{{ __('certification.issuedOn') }}
						{{ dayjs(certificate.issue_date).format('L') }}
					</div>
				</div>
			</div>
		</div>
		<div v-else class="text-sm italic text-ink-gray-5">
			{{ __('certification.noCertificatesYet') }}
		</div>
	</div>
</template>
<script setup>
import { createListResource } from 'frappe-ui'
import { GraduationCap } from 'lucide-vue-next'
import { inject, onMounted } from 'vue'

const dayjs = inject('$dayjs')
const props = defineProps({
	profile: {
		type: Object,
		required: true,
	},
})

onMounted(() => {
	if (props.profile.data?.name) {
		certificates.reload()
	}
})

const certificates = createListResource({
	doctype: 'LMS Certificate',
	filters: {
		member: props.profile.data?.name,
	},
	fields: ['name', 'course_title', 'batch_title', 'issue_date', 'template'],
	cache: ['certificates', props.profile.data?.name],
})

const openCertificate = (certificate) => {
	window.open(
		`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate&name=${
			certificate.name
		}&format=${encodeURIComponent(certificate.template)}`
	)
}
</script>
<style scoped>
.lms-profile-certificates__serif {
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

.lms-profile-certificates__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}

.lms-profile-certificates__seal {
	background: #efe8d8;
	color: #8a6a22;
}
</style>
