<template>
	<div v-if="allowed" class="min-h-full bg-surface-canvas">
		<header class="border-b border-outline-gray-2 bg-surface-white px-5 py-4">
			<Breadcrumbs
				:items="[{ label: 'PAI Governance', route: { name: 'PAIGovernance' } }]"
			/>
		</header>
		<main class="mx-auto max-w-6xl space-y-6 p-5">
			<div>
				<p class="text-sm text-ink-gray-5">PAI Role & Policy Governance</p>
				<h1 class="text-2xl font-semibold text-ink-gray-9">
					Role profiles and semantic policies
				</h1>
				<p class="mt-2 text-sm text-ink-gray-6">
					Policies are explicitly version-pinned; no profile uses an implicit
					latest policy.
				</p>
			</div>
			<section class="grid gap-6 lg:grid-cols-2">
				<div
					class="rounded-lg border border-outline-gray-2 bg-surface-white p-5"
				>
					<h2 class="font-semibold text-ink-gray-9">Create role profile</h2>
					<FormControl v-model="title" class="mt-4" label="Title" /><FormControl
						v-model="requirements"
						class="mt-4"
						label="Requirements summary"
						type="textarea"
						:rows="3"
					/><Button
						class="mt-4"
						variant="solid"
						:loading="createProfile.loading"
						@click="create"
						>Create draft</Button
					>
				</div>
				<div
					class="rounded-lg border border-outline-gray-2 bg-surface-white p-5"
				>
					<div class="flex items-center justify-between">
						<h2 class="font-semibold text-ink-gray-9">Role profiles</h2>
						<Button
							size="sm"
							variant="subtle"
							:loading="profiles.loading"
							@click="profiles.reload()"
							>Refresh</Button
						>
					</div>
					<p v-if="!profiles.data?.length" class="py-8 text-sm text-ink-gray-5">
						No role profiles yet.
					</p>
					<div v-else class="mt-3 divide-y divide-outline-gray-2">
						<div
							v-for="profile in profiles.data"
							:key="profile.name"
							class="flex items-center justify-between gap-3 py-3"
						>
							<div>
								<p class="font-medium text-ink-gray-9">{{ profile.title }}</p>
								<p class="text-xs text-ink-gray-5">
									v{{ profile.profile_version }} ·
									{{ profile.semantic_policy_version || 'Policy not pinned' }}
								</p>
							</div>
							<Badge theme="gray">{{ profile.status }}</Badge>
						</div>
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
const allowed = computed(
	() =>
		user.data?.is_system_manager ||
		user.data?.is_moderator ||
		user.data?.is_instructor,
)
const title = ref('')
const requirements = ref('')
const profiles = createResource({
	url: 'pai_frappe.api.list_role_profiles',
	auto: false,
})
const createProfile = createResource({
	url: 'pai_frappe.api.create_role_profile',
})
function create() {
	if (!title.value.trim()) return
	createProfile.submit(
		{ title: title.value, requirements_summary: requirements.value },
		{
			onSuccess() {
				title.value = ''
				requirements.value = ''
				profiles.reload()
			},
		},
	)
}
onMounted(() => {
	if (allowed.value) profiles.reload()
})
</script>
