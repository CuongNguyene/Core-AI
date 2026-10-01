<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-2 bg-surface-white/90 px-3 py-2.5 backdrop-blur-md sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<div v-if="workspace.request" class="text-xs text-ink-gray-5">
			{{ __('Request') }}: {{ workspace.request.name }}
		</div>
	</header>

	<div class="p-5 pb-10">
		<div v-if="userResource.loading" class="py-12 text-center text-sm text-ink-gray-6">
			{{ __('Loading...') }}
		</div>
		<div
			v-else-if="!hasAuthoringAccess"
			class="rounded-md border border-outline-gray-2 bg-surface-gray-1 px-5 py-12 text-center"
		>
			<h1 class="lms-ai-planning__serif text-xl text-ink-gray-9">
				{{ __('AI Course Planning') }}
			</h1>
			<p class="mt-2 text-sm text-ink-gray-6">
				{{ __('You are not permitted to manage AI course planning.') }}
			</p>
		</div>
		<div v-else-if="workspace.error" class="rounded-md border border-outline-red-2 bg-surface-red-1 px-5 py-8">
			<h1 class="lms-ai-planning__serif text-xl text-ink-gray-9">
				{{ __('AI Course Planning') }}
			</h1>
			<p class="mt-2 text-sm text-ink-gray-7">{{ workspace.error }}</p>
			<Button class="mt-4" @click="reloadWorkspace">{{ __('Try again') }}</Button>
		</div>
		<div v-else class="mx-auto max-w-6xl space-y-5">
			<div class="border-b border-outline-gray-2 pb-5">
				<div class="lms-ai-planning__mono text-[11px] uppercase tracking-[0.14em] text-ink-gray-5">
					{{ __('Authoring workspace') }}
				</div>
				<h1 class="lms-ai-planning__serif mt-1 text-[1.75rem] leading-tight text-ink-gray-9">
					{{ __('AI Course Planning') }}
				</h1>
				<p class="mt-2 max-w-2xl text-sm leading-6 text-ink-gray-6">
					{{ __('Turn a training goal into a confirmed structured brief. Curriculum planning comes later.') }}
				</p>
			</div>

			<section v-if="!workspace.request" class="rounded-md border border-outline-gray-2 bg-surface-white p-5">
				<h2 class="lms-ai-planning__serif text-xl text-ink-gray-9">{{ __('Start with a goal') }}</h2>
				<p class="mt-1 text-sm text-ink-gray-6">
					{{ __('Create a GOAL_DRIVEN brief for a course or learning program.') }}
				</p>
				<div class="mt-5 grid gap-4 lg:grid-cols-2">
					<FormControl v-model="createForm.title" :label="__('Title')" :placeholder="__('Enter a course planning title')" />
					<FormControl v-model="createForm.goal" :label="__('Training goal')" type="textarea" :placeholder="__('What should learners be able to do?')" />
				</div>
				<div class="mt-4 grid gap-4 lg:grid-cols-2">
					<FormControl v-model="createForm.outcomes" :label="__('Desired outcomes')" type="textarea" :description="__('One outcome per line')" />
					<FormControl v-model="createForm.prerequisites" :label="__('Prerequisites')" type="textarea" :description="__('One prerequisite per line')" />
				</div>
				<div class="mt-5 flex justify-end">
					<Button variant="solid" :loading="actions.creating" :disabled="actions.creating" @click="createRequest">
						{{ __('Create brief') }}
					</Button>
				</div>
			</section>

			<template v-else>
				<section class="rounded-md border border-outline-gray-2 bg-surface-white p-5">
					<div class="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
						<div>
							<div class="lms-ai-planning__mono text-[10px] uppercase tracking-[0.12em] text-ink-gray-5">
								{{ workspace.request.pai?.mode || 'GOAL_DRIVEN' }}
							</div>
							<h2 class="lms-ai-planning__serif mt-1 text-2xl text-ink-gray-9">
								{{ workspace.request.pai?.title || workspace.request.title }}
							</h2>
						</div>
						<div class="flex flex-wrap items-center gap-2">
							<span class="rounded-full border border-outline-gray-2 bg-surface-gray-1 px-3 py-1 text-xs text-ink-gray-7">
								{{ latestStatusLabel }}
							</span>
							<span v-if="latestRevision" class="text-xs text-ink-gray-5">
								{{ __('Revision {0}').format(latestRevision.version) }}
							</span>
						</div>
					</div>
				</section>

				<section v-if="latestRevision" class="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
					<div class="space-y-5">
						<div class="rounded-md border border-outline-gray-2 bg-surface-white p-5">
							<div class="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
								<div>
									<h2 class="lms-ai-planning__serif text-xl text-ink-gray-9">{{ __('Structured brief') }}</h2>
									<p class="mt-1 text-sm text-ink-gray-6">{{ __('Edit fields and save a new immutable revision.') }}</p>
								</div>
				<Button variant="subtle" :loading="actions.clarifying" :disabled="mutationInFlight || latestRevision.status === 'CONFIRMED'" @click="clarifyLatest">
									{{ __('Check clarification') }}
								</Button>
							</div>
							<div class="mt-5 grid gap-4">
								<FormControl v-model="editor.training_goal" :label="__('Training goal')" type="textarea" />
								<div class="grid gap-4 lg:grid-cols-2">
									<FormControl v-model="editor.desired_outcomes" :label="__('Desired outcomes')" type="textarea" :description="__('One outcome per line')" />
									<FormControl v-model="editor.prerequisites" :label="__('Prerequisites')" type="textarea" :description="__('One prerequisite per line')" />
								</div>
								<div class="grid gap-4 lg:grid-cols-2">
									<FormControl v-model="editor.learning_horizon" :label="__('Learning horizon')" />
									<FormControl v-model="editor.expected_learning_effort" :label="__('Expected learning effort')" />
								</div>
								<div class="grid gap-4 lg:grid-cols-2">
									<FormControl v-model="editor.excluded_scope" :label="__('Excluded scope')" type="textarea" :description="__('One item per line')" />
									<FormControl v-model="editor.emphasis" :label="__('Emphasis')" type="textarea" :description="__('One item per line')" />
								</div>
								<FormControl v-model="editor.author_feedback" :label="__('Author feedback')" type="textarea" />
							</div>
							<div class="mt-5 flex flex-wrap justify-end gap-2">
								<Button variant="subtle" :disabled="actions.saving" @click="resetEditor">{{ __('Reset changes') }}</Button>
				<Button variant="solid" :loading="actions.saving" :disabled="mutationInFlight || latestRevision.status === 'CONFIRMED'" @click="saveRevision">
									{{ __('Save new revision') }}
								</Button>
							</div>
						</div>

						<div v-if="latestRevision.clarification?.questions?.length" class="rounded-md border border-outline-amber-2 bg-surface-amber-1 p-5">
							<h2 class="lms-ai-planning__serif text-xl text-ink-gray-9">{{ __('Clarification needed') }}</h2>
							<ul class="mt-3 space-y-3 text-sm text-ink-gray-7">
								<li v-for="question in latestRevision.clarification.questions" :key="question.code" class="flex gap-2">
									<span class="font-medium text-ink-amber-3">{{ question.required ? '•' : '○' }}</span>
									<span>{{ question.question }}</span>
								</li>
							</ul>
						</div>
					</div>

					<aside class="space-y-5">
						<div class="rounded-md border border-outline-gray-2 bg-surface-white p-5">
							<h2 class="lms-ai-planning__serif text-xl text-ink-gray-9">{{ __('Confirmation') }}</h2>
							<p class="mt-2 text-sm leading-6 text-ink-gray-6">
								{{ confirmationHelp }}
							</p>
							<div v-if="latestRevision.status === 'CONFIRMED'" class="mt-4 rounded-md border border-outline-green-2 bg-surface-green-1 p-3 text-sm text-ink-green-3">
								{{ __('Confirmed revision {0}').format(latestRevision.version) }}
								<div v-if="latestRevision.confirmed_at" class="mt-1 text-xs">{{ formatDate(latestRevision.confirmed_at) }}</div>
							</div>
			<Button v-else variant="solid" class="mt-4 w-full" :loading="actions.confirming" :disabled="mutationInFlight || latestRevision.status !== 'READY_FOR_CONFIRMATION'" @click="confirmLatest">
								{{ __('Confirm brief') }}
							</Button>
						</div>

						<div class="rounded-md border border-outline-gray-2 bg-surface-white p-5">
							<h2 class="lms-ai-planning__serif text-xl text-ink-gray-9">{{ __('Revision history') }}</h2>
							<div v-if="workspace.revisions.length" class="mt-4 space-y-3">
								<div v-for="revision in workspace.revisions" :key="revision.id" class="border-l-2 border-outline-gray-2 pl-3 text-sm">
									<div class="flex items-center justify-between gap-2">
										<span class="font-medium text-ink-gray-8">{{ __('Revision {0}').format(revision.version) }}</span>
										<span data-cy="revision-history-status" class="text-xs text-ink-gray-5">{{ statusLabel(revision.status) }}</span>
									</div>
									<div class="mt-1 text-xs text-ink-gray-5">{{ formatDate(revision.created_at) }}</div>
								</div>
							</div>
							<div v-else class="mt-3 text-sm text-ink-gray-6">{{ __('No revisions found.') }}</div>
						</div>
					</aside>
				</section>
				<div v-else-if="workspace.loading" class="rounded-md border border-outline-gray-2 p-10 text-center text-sm text-ink-gray-6">{{ __('Loading...') }}</div>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Breadcrumbs, Button, call, FormControl, toast, usePageMeta } from 'frappe-ui'
import { useRoute, useRouter } from 'vue-router'
import { usersStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const { userResource } = usersStore()

const workspace = reactive({ request: null, revisions: [], loading: false, error: '' })
const actions = reactive({ creating: false, clarifying: false, saving: false, confirming: false })
const createForm = reactive({ title: '', goal: '', outcomes: '', prerequisites: '' })
const editor = reactive({
	training_goal: '',
	desired_outcomes: '',
	prerequisites: '',
	learning_horizon: '',
	expected_learning_effort: '',
	excluded_scope: '',
	emphasis: '',
	author_feedback: '',
})
const createIdempotencyKey = ref('')
let reloadSequence = 0

const hasAuthoringAccess = computed(() => {
	const user = userResource.data
	return Boolean(user?.is_system_manager || user?.is_moderator || user?.is_instructor)
})
const latestRevision = computed(() =>
	[...workspace.revisions].sort((a, b) => Number(b.version || 0) - Number(a.version || 0))[0] || null,
)
const mutationInFlight = computed(() => Object.values(actions).some(Boolean))
const latestStatusLabel = computed(() => statusLabel(latestRevision.value?.status))
const confirmationHelp = computed(() => {
	if (latestRevision.value?.status === 'CONFIRMED') return __('This brief is confirmed in Core-AI.')
	if (latestRevision.value?.status === 'READY_FOR_CONFIRMATION') return __('The latest revision is structurally complete and can be confirmed.')
	return __('Resolve required clarification questions before confirming the latest revision.')
})
const breadcrumbs = computed(() => [
	{ label: __('AI Course Planning'), route: { name: 'AICoursePlanning' } },
])

const statusLabel = (status) => ({
	DRAFT: __('Draft'),
	NEEDS_CLARIFICATION: __('Needs clarification'),
	READY_FOR_CONFIRMATION: __('Ready to confirm'),
	CONFIRMED: __('Confirmed'),
}[status] || status || __('Unknown'))

const formatDate = (value) => {
	if (!value) return ''
	return new Date(value).toLocaleString()
}

const linesToList = (value) => String(value || '').split('\n').map((item) => item.trim()).filter(Boolean)
const listToLines = (value) => Array.isArray(value) ? value.join('\n') : ''
const newIdempotencyKey = () => {
	if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
	return `lms-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}

const resetEditor = () => {
	const payload = latestRevision.value?.payload || {}
	editor.training_goal = payload.training_goal || ''
	editor.desired_outcomes = listToLines(payload.desired_outcomes)
	editor.prerequisites = listToLines(payload.prerequisites)
	editor.learning_horizon = payload.learning_horizon || ''
	editor.expected_learning_effort = payload.expected_learning_effort || ''
	editor.excluded_scope = listToLines(payload.excluded_scope)
	editor.emphasis = listToLines(payload.emphasis)
	editor.author_feedback = latestRevision.value?.author_feedback || ''
}

const errorCode = (error) => {
	const text = [error?.message, error?.exc, ...(error?.messages || [])].filter(Boolean).join(' ')
	return Object.keys(errorMessages).find((code) => text.includes(code)) || ''
}
const errorMessages = {
	course_authoring_request_not_found: __('This authoring request no longer exists.'),
	course_authoring_access_denied: __('You do not have access to this authoring request.'),
	revision_not_found: __('The brief revision could not be found. Refresh and try again.'),
	revision_request_mismatch: __('This revision does not belong to the current request.'),
	revision_not_latest: __('A newer revision exists. The latest brief has been reloaded.'),
	required_clarification_unresolved: __('Resolve the required clarification questions before confirming.'),
	revision_not_ready_for_confirmation: __('The latest revision is not ready for confirmation.'),
	course_authoring_idempotency_conflict: __('This create attempt conflicts with an existing request. Start a new request.'),
	course_authoring_unavailable: __('AI course planning is temporarily unavailable.'),
}
const safeError = (error, fallback = __('Something went wrong. Please try again.')) => errorMessages[errorCode(error)] || fallback

const reloadWorkspace = async ({ preserveEditor = false } = {}) => {
	const name = route.params.requestId
	const sequence = ++reloadSequence
	if (!name) {
		workspace.request = null
		workspace.revisions = []
		workspace.error = ''
		workspace.loading = false
		resetEditor()
		return
	}
	workspace.loading = true
	workspace.error = ''
	try {
		const [request, revisions] = await Promise.all([
			call('pai_frappe.api.get_course_authoring_request', { name }),
			call('pai_frappe.api.list_authoring_brief_revisions', { name }),
		])
		if (sequence !== reloadSequence || route.params.requestId !== name) return
		workspace.request = request
		workspace.revisions = Array.isArray(revisions) ? revisions : []
		if (!preserveEditor) resetEditor()
	} catch (error) {
		if (sequence !== reloadSequence || route.params.requestId !== name) return
		workspace.error = safeError(error, __('Unable to load this authoring workspace.'))
	} finally {
		if (sequence === reloadSequence) workspace.loading = false
	}
}

const createRequest = async () => {
	if (actions.creating) return
	if (!createForm.title.trim() || !createForm.goal.trim()) {
		toast.error(__('A title and training goal are required.'))
		return
	}
	if (!createIdempotencyKey.value) createIdempotencyKey.value = newIdempotencyKey()
	actions.creating = true
	workspace.error = ''
	try {
		const result = await call('pai_frappe.api.create_course_authoring_request', {
			data: {
				title: createForm.title.trim(),
				mode: 'GOAL_DRIVEN',
				learner_refs: [],
				training_brief: {
					goal: createForm.goal.trim(),
					desired_outcomes: linesToList(createForm.outcomes),
					prerequisites: linesToList(createForm.prerequisites),
				},
			},
			idempotency_key: createIdempotencyKey.value,
		})
		await router.replace({ name: 'AICoursePlanning', params: { requestId: result.name } })
		createIdempotencyKey.value = ''
		await reloadWorkspace()
		await clarifyLatest({ internal: true })
	} catch (error) {
		workspace.error = safeError(error, __('Unable to create the authoring request.'))
	} finally {
		actions.creating = false
	}
}

const clarifyLatest = async ({ internal = false } = {}) => {
	if (!latestRevision.value || (!internal && mutationInFlight.value)) return
	actions.clarifying = true
	try {
		await call('pai_frappe.api.clarify_authoring_brief', { name: route.params.requestId })
		await reloadWorkspace()
	} catch (error) {
		if (errorCode(error) === 'revision_not_latest') await reloadWorkspace()
		else toast.error(safeError(error, __('Unable to check clarification.')))
	} finally {
		actions.clarifying = false
	}
}

const saveRevision = async () => {
	if (!latestRevision.value || mutationInFlight.value) return
	actions.saving = true
	try {
		await call('pai_frappe.api.revise_authoring_brief', {
			name: route.params.requestId,
			data: {
				training_goal: editor.training_goal.trim(),
				desired_outcomes: linesToList(editor.desired_outcomes),
				prerequisites: linesToList(editor.prerequisites),
				learning_horizon: editor.learning_horizon.trim() || null,
				expected_learning_effort: editor.expected_learning_effort.trim() || null,
				excluded_scope: linesToList(editor.excluded_scope),
				emphasis: linesToList(editor.emphasis),
				author_feedback: editor.author_feedback.trim() || null,
			},
		})
		await reloadWorkspace()
		await clarifyLatest({ internal: true })
	} catch (error) {
		if (errorCode(error) === 'revision_not_latest') {
			await reloadWorkspace({ preserveEditor: true })
			toast.error(errorMessages.revision_not_latest)
		} else toast.error(safeError(error, __('Unable to save the new revision.')))
	} finally {
		actions.saving = false
	}
}

const confirmLatest = async () => {
	if (!latestRevision.value || latestRevision.value.status !== 'READY_FOR_CONFIRMATION' || mutationInFlight.value) return
	actions.confirming = true
	try {
		await call('pai_frappe.api.confirm_authoring_brief', {
			name: route.params.requestId,
			revision_id: latestRevision.value.id,
		})
		await reloadWorkspace()
	} catch (error) {
		if (errorCode(error) === 'revision_not_latest') await reloadWorkspace()
		else toast.error(safeError(error, __('Unable to confirm this brief.')))
	} finally {
		actions.confirming = false
	}
}

watch(() => route.params.requestId, reloadWorkspace, { immediate: true })
usePageMeta(() => ({ title: __('AI Course Planning') }))
</script>
