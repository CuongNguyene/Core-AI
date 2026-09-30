<template>
	<div v-if="allowed" class="min-h-full bg-surface-canvas">
		<header class="border-b border-outline-gray-2 bg-surface-white px-5 py-4">
			<Breadcrumbs
				:items="[{ label: 'PAI Evidence', route: { name: 'PAIEvidence' } }]"
			/>
		</header>
		<main class="mx-auto max-w-6xl space-y-6 p-5">
			<div>
				<p class="text-sm text-ink-gray-5">PAI Evidence Center</p>
				<h1 class="text-2xl font-semibold text-ink-gray-9">Evidence cases</h1>
				<p class="mt-2 max-w-3xl text-sm text-ink-gray-6">
					Track CV and job-description evidence without retaining source
					documents in LMS.
				</p>
			</div>
			<div
				class="rounded-lg border border-outline-amber-2 bg-surface-amber-1 px-4 py-3 text-sm text-ink-gray-7"
			>
				Upload, extraction, and reviewer decisions will be available after the
				signed PAI Evidence API is connected. This page stores only the case
				lifecycle and safe references.
			</div>
			<section
				class="rounded-lg border border-outline-gray-2 bg-surface-white p-5"
			>
				<div class="flex flex-wrap items-end justify-between gap-4">
					<div>
						<h2 class="text-base font-semibold text-ink-gray-9">
							Create evidence case
						</h2>
						<p class="mt-1 text-sm text-ink-gray-6">
							Create a tracking case before a PAI upload is connected.
						</p>
					</div>
					<div class="flex items-end gap-3">
						<FormControl
							v-model="documentKind"
							type="select"
							label="Document kind"
							:options="documentKinds"
						/><Button
							variant="solid"
							:loading="createCase.loading"
							@click="create"
							>Create case</Button
						>
					</div>
				</div>
				<p v-if="message" class="mt-3 text-sm text-ink-gray-6">{{ message }}</p>
			</section>
			<section
				class="rounded-lg border border-outline-gray-2 bg-surface-white p-5"
			>
				<div class="flex items-center justify-between gap-3">
					<div>
						<h2 class="text-base font-semibold text-ink-gray-9">
							Your evidence cases
						</h2>
						<p class="mt-1 text-sm text-ink-gray-6">
							Reviewers see cases within their permitted scope.
						</p>
					</div>
					<Button
						size="sm"
						variant="subtle"
						:loading="cases.loading"
						@click="cases.reload()"
						>Refresh</Button
					>
				</div>
				<div v-if="cases.loading" class="py-8 text-sm text-ink-gray-5">
					Loading evidence cases…
				</div>
				<div
					v-else-if="!cases.data?.length"
					class="py-8 text-sm text-ink-gray-5"
				>
					No evidence cases yet.
				</div>
				<div v-else class="mt-4 divide-y divide-outline-gray-2">
					<div
						v-for="item in cases.data"
						:key="item.name"
						class="flex flex-wrap items-center justify-between gap-4 py-4"
					>
						<div>
							<p class="font-medium text-ink-gray-9">
								{{ item.document_kind }} evidence case
							</p>
							<p class="mt-1 text-sm text-ink-gray-6">
								{{ item.name }} · updated {{ item.modified }}
							</p>
							<p v-if="item.safe_summary" class="mt-2 text-sm text-ink-gray-7">
								{{ item.safe_summary }}
							</p>
						</div>
						<Badge theme="gray">{{ item.status }}</Badge>
					</div>
				</div>
			</section>
		</main>
	</div>
	<NoPermission v-else />
</template>

<script setup>
import {
	Badge,
	Breadcrumbs,
	Button,
	FormControl,
	createResource,
} from 'frappe-ui'
import { computed, inject, onMounted, ref } from 'vue'
import NoPermission from '@/components/NoPermission.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const allowed = computed(
	() =>
		user.data?.is_system_manager ||
		user.data?.is_moderator ||
		user.data?.is_instructor ||
		user.data?.is_student,
)
const documentKind = ref('CV')
const message = ref('')
const documentKinds = [
	{ label: 'CV', value: 'CV' },
	{ label: 'Job description', value: 'JD' },
]
const cases = createResource({
	url: 'pai_frappe.api.list_evidence_cases',
	auto: false,
	transform(data) {
		return data.map((item) => ({
			...item,
			modified: dayjs(item.modified).fromNow(),
		}))
	},
})
const createCase = createResource({
	url: 'pai_frappe.api.create_evidence_case',
})
const errorMessage = (error) =>
	error?.messages?.[0] || error?.message || String(error)
function create() {
	message.value = ''
	createCase.submit(
		{ document_kind: documentKind.value },
		{
			onSuccess(data) {
				message.value = `${documentKind.value} case ${data.name} was created.`
				cases.reload()
			},
			onError(error) {
				message.value = errorMessage(error)
			},
		},
	)
}
onMounted(() => {
	if (allowed.value) cases.reload()
})
</script>
