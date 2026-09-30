<template>
	<div v-if="allowed" class="min-h-full bg-surface-canvas">
		<header class="border-b border-outline-gray-2 bg-surface-white px-5 py-4">
			<Breadcrumbs
				:items="[{ label: 'PAI Studio', route: { name: 'PAIStudio' } }]"
			/>
		</header>
		<main class="mx-auto max-w-7xl space-y-6 p-5">
			<div>
				<p class="text-sm text-ink-gray-5">AI course authoring</p>
				<h1 class="text-2xl font-semibold text-ink-gray-9">PAI Studio</h1>
				<p class="mt-2 max-w-3xl text-sm text-ink-gray-6">
					Create a course brief, review the proposed curriculum, then generate a
					draft for human review. PAI does not publish a course into LMS
					automatically.
				</p>
			</div>
			<div
				v-if="
					studioStatus.data &&
					(!studioStatus.data.enabled ||
						!studioStatus.data.service_configured ||
						!studioStatus.data.identity_configured)
				"
				class="rounded-lg border border-outline-amber-2 bg-surface-amber-1 px-4 py-3 text-sm text-ink-gray-7"
			>
				PAI Studio is not ready for this account.
				<span
					v-if="
						!studioStatus.data.enabled || !studioStatus.data.service_configured
					"
				>
					A System Manager must complete PAI Settings.
				</span>
				<span v-else
					>A System Manager must map your LMS account to a PAI identity.</span
				>
				<span
					v-if="
						user.data?.is_system_manager &&
						studioStatus.data.missing_configuration?.length
					"
				>
					Missing: {{ studioStatus.data.missing_configuration.join(', ') }}.
				</span>
			</div>

			<div
				class="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]"
			>
				<section
					class="rounded-lg border border-outline-gray-2 bg-surface-white p-5"
				>
					<div class="mb-5 flex items-start justify-between gap-4">
						<div>
							<h2 class="text-base font-semibold text-ink-gray-9">
								New authoring request
							</h2>
							<p class="mt-1 text-sm text-ink-gray-6">
								The request captures the goal and intended learners before AI
								generation starts.
							</p>
						</div>
					</div>
					<div class="grid gap-5 md:grid-cols-2">
						<FormControl
							v-model="form.title"
							label="Course title"
							:required="true"
						/>
						<FormControl
							v-model="form.language"
							label="Language"
							placeholder="vi"
						/>
					</div>
					<FormControl
						v-model="form.goal"
						class="mt-5"
						label="Training goal"
						type="textarea"
						:rows="4"
						:required="true"
						placeholder="What should learners be able to do after this course?"
					/>
					<div class="mt-5 grid gap-5 md:grid-cols-2">
						<FormControl
							v-model="form.duration"
							label="Duration constraint"
							placeholder="For example: 4 hours"
						/>
						<FormControl
							v-model="form.completionContext"
							label="Completion context"
							placeholder="For example: before onboarding ends"
						/>
					</div>
					<FormControl
						v-model="form.learnerRefs"
						class="mt-5"
						label="Learner references"
						type="textarea"
						:rows="3"
						description="Optional. One LMS user reference per line; PAI records an audience snapshot."
						placeholder="learner@example.com"
					/>
					<div class="mt-5 grid gap-5 md:grid-cols-2">
						<FormControl
							v-model="form.outcomes"
							label="Desired outcomes"
							type="textarea"
							:rows="5"
							description="One outcome per line."
						/>
						<FormControl
							v-model="form.prerequisites"
							label="Prerequisites"
							type="textarea"
							:rows="5"
							description="Optional, one prerequisite per line."
						/>
					</div>
					<FormControl
						v-model="form.notes"
						class="mt-5"
						label="Author notes"
						type="textarea"
						:rows="3"
					/>
					<div class="mt-5 flex items-center gap-3">
						<Button
							variant="solid"
							:disabled="!isReady"
							:loading="createRequest.loading"
							@click="submit"
						>
							Create request
						</Button>
						<span v-if="message" class="text-sm text-ink-gray-6">{{
							message
						}}</span>
					</div>
				</section>

				<aside
					class="rounded-lg border border-outline-gray-2 bg-surface-white p-5"
				>
					<div class="flex items-center justify-between gap-3">
						<div>
							<h2 class="text-base font-semibold text-ink-gray-9">
								Your requests
							</h2>
							<p class="mt-1 text-sm text-ink-gray-6">
								Drafts created from this LMS account.
							</p>
						</div>
						<Button
							variant="subtle"
							size="sm"
							:loading="requests.loading"
							@click="requests.reload()"
						>
							Refresh
						</Button>
					</div>
					<div v-if="requests.loading" class="py-8 text-sm text-ink-gray-5">
						Loading requests…
					</div>
					<div
						v-else-if="!requests.data?.length"
						class="py-8 text-sm text-ink-gray-5"
					>
						No authoring requests yet.
					</div>
					<div v-else class="mt-4 space-y-2">
						<button
							v-for="request in requests.data"
							:key="request.name"
							class="w-full rounded-md border p-3 text-left transition"
							:class="
								selectedName === request.name
									? 'border-outline-gray-4 bg-surface-gray-1'
									: 'border-outline-gray-2 hover:bg-surface-gray-1'
							"
							@click="selectRequest(request.name)"
						>
							<div class="flex items-start justify-between gap-3">
								<span class="font-medium text-ink-gray-9">{{
									request.title
								}}</span>
								<Badge theme="gray">{{ request.status }}</Badge>
							</div>
							<p class="mt-1 text-xs text-ink-gray-5">{{ request.modified }}</p>
						</button>
					</div>
				</aside>
			</div>

			<section
				v-if="selectedName"
				class="rounded-lg border border-outline-gray-2 bg-surface-white p-5"
			>
				<div class="flex flex-wrap items-start justify-between gap-4">
					<div>
						<p class="text-sm text-ink-gray-5">Authoring workflow</p>
						<h2 class="text-lg font-semibold text-ink-gray-9">
							{{ detail.data?.pai?.title || selectedName }}
						</h2>
					</div>
					<Button
						variant="subtle"
						size="sm"
						:loading="detail.loading || persistedPlan.loading"
						@click="refreshWorkflow"
					>
						Refresh status
					</Button>
				</div>
				<p v-if="workflowMessage" class="mt-3 text-sm text-ink-gray-6">
					{{ workflowMessage }}
				</p>
				<div class="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
					<div class="rounded-md bg-surface-gray-1 p-4">
						<p class="text-sm font-medium text-ink-gray-9">1. Confirm brief</p>
						<p class="mt-1 text-sm text-ink-gray-6">
							{{
								brief?.status
									? `Brief status: ${brief.status}`
									: 'Check the brief for missing information before planning.'
							}}
						</p>
						<div class="mt-3 flex flex-wrap gap-2">
							<Button
								size="sm"
								:disabled="!isReady"
								:loading="clarifyBrief.loading"
								@click="clarify"
							>
								Check brief
							</Button>
							<Button
								size="sm"
								:disabled="
									!isReady || brief?.status !== 'READY_FOR_CONFIRMATION'
								"
								:loading="confirmBrief.loading"
								@click="confirmBriefRevision"
							>
								Confirm brief
							</Button>
						</div>
					</div>
					<div class="rounded-md bg-surface-gray-1 p-4">
						<p class="text-sm font-medium text-ink-gray-9">
							2. Plan curriculum
						</p>
						<p class="mt-1 text-sm text-ink-gray-6">
							Generate an outline from the approved brief.
						</p>
						<Button
							class="mt-3"
							size="sm"
							:disabled="!isReady || brief?.status !== 'CONFIRMED'"
							:loading="planRequest.loading"
							@click="createPlan"
						>
							Create plan
						</Button>
					</div>
					<div class="rounded-md bg-surface-gray-1 p-4">
						<p class="text-sm font-medium text-ink-gray-9">
							3. Review and confirm
						</p>
						<p class="mt-1 text-sm text-ink-gray-6">
							{{
								plan?.status
									? `Plan status: ${plan.status}`
									: 'Load or create a plan before confirming it.'
							}}
						</p>
						<div class="mt-3 flex flex-wrap gap-2">
							<Button
								size="sm"
								:disabled="!isReady || !plan?.plan_ref"
								:loading="reviewPlan.loading"
								@click="review"
							>
								Review plan
							</Button>
							<Button
								size="sm"
								:disabled="
									!isReady || plan?.status !== 'READY_FOR_CONFIRMATION'
								"
								:loading="confirmPlan.loading"
								@click="confirm"
							>
								Confirm plan
							</Button>
						</div>
					</div>
					<div class="rounded-md bg-surface-gray-1 p-4">
						<p class="text-sm font-medium text-ink-gray-9">4. Generate draft</p>
						<p class="mt-1 text-sm text-ink-gray-6">
							Generation creates a reviewable draft, not a published LMS course.
						</p>
						<Button
							class="mt-3"
							size="sm"
							:disabled="!isReady || plan?.status !== 'CONFIRMED'"
							:loading="generateRequest.loading"
							@click="generate"
						>
							Generate draft
						</Button>
					</div>
				</div>
				<div
					v-if="plan"
					class="mt-5 rounded-md border border-outline-gray-2 p-4"
				>
					<div class="flex items-center justify-between gap-3">
						<h3 class="font-medium text-ink-gray-9">Curriculum plan</h3>
						<Badge theme="gray">{{ plan.status }}</Badge>
					</div>
					<p class="mt-2 text-sm text-ink-gray-6">
						{{ plan.module_count }} modules · {{ plan.lesson_count }} lessons ·
						{{ plan.duration || 'Duration not specified' }}
					</p>
					<ul
						v-if="plan.modules?.length"
						class="mt-3 space-y-2 text-sm text-ink-gray-7"
					>
						<li v-for="module in plan.modules" :key="module.id">
							{{ module.order }}. {{ module.title }}
						</li>
					</ul>
				</div>
				<div
					v-if="brief && brief.status !== 'CONFIRMED'"
					class="mt-5 rounded-md border border-outline-amber-2 bg-surface-amber-1 p-4"
				>
					<h3 class="font-medium text-ink-gray-9">Resolve and revise brief</h3>
					<p class="mt-1 text-sm text-ink-gray-6">
						The edited brief is sent to PAI as a new version. LMS only keeps an
						audit summary.
					</p>
					<ul
						v-if="brief.clarification?.questions?.length"
						class="mt-3 list-disc space-y-1 pl-5 text-sm text-ink-gray-7"
					>
						<li
							v-for="question in brief.clarification.questions"
							:key="question.code"
						>
							{{ question.question }}
						</li>
					</ul>
					<div class="mt-4 grid gap-4 md:grid-cols-2">
						<FormControl
							v-model="briefRevision.trainingGoal"
							label="Training goal"
							type="textarea"
							:rows="3"
						/>
						<FormControl
							v-model="briefRevision.outcomes"
							label="Desired outcomes"
							type="textarea"
							:rows="3"
							description="One outcome per line."
						/>
						<FormControl
							v-model="briefRevision.prerequisites"
							label="Prerequisites"
							type="textarea"
							:rows="3"
							description="One prerequisite per line."
						/>
						<div class="grid gap-4 sm:grid-cols-2">
							<FormControl
								v-model="briefRevision.learningHorizon"
								label="Completion window"
							/>
							<FormControl
								v-model="briefRevision.expectedEffort"
								label="Learning effort"
							/>
						</div>
					</div>
					<FormControl
						v-model="briefRevision.feedback"
						class="mt-4"
						label="Author feedback"
						type="textarea"
						:rows="2"
					/>
					<Button
						class="mt-4"
						:disabled="!isReady || !briefRevision.trainingGoal.trim()"
						:loading="reviseBrief.loading"
						@click="saveBriefRevision"
					>
						Save revised brief
					</Button>
				</div>
				<div
					v-if="generation.data"
					class="mt-5 rounded-md border border-outline-gray-2 p-4"
				>
					<div class="flex flex-wrap items-center justify-between gap-3">
						<div>
							<h3 class="font-medium text-ink-gray-9">Generation progress</h3>
							<p class="mt-1 text-sm text-ink-gray-6">
								{{ generation.data.succeeded_lessons }} of
								{{ generation.data.total_lessons }} lessons completed
							</p>
						</div>
						<Badge theme="gray">{{ generation.data.status }}</Badge>
					</div>
					<div class="mt-3 flex flex-wrap gap-2 text-sm text-ink-gray-6">
						<span>{{ generation.data.pending_lessons }} pending</span>
						<span>{{ generation.data.failed_lessons }} failed</span>
					</div>
					<div class="mt-3 flex flex-wrap gap-2">
						<Button
							size="sm"
							:loading="generation.loading"
							@click="loadGeneration(true)"
						>
							Refresh generation
						</Button>
						<Button
							size="sm"
							:disabled="!isReady || generation.data.failed_lessons === 0"
							:loading="retryGeneration.loading"
							@click="retry"
						>
							Retry failed lessons
						</Button>
					</div>
					<ul class="mt-4 space-y-2 text-sm text-ink-gray-7">
						<li
							v-for="lesson in generation.data.lessons"
							:key="lesson.task_ref"
						>
							{{ lesson.module_order }}.{{ lesson.lesson_order }}
							{{ lesson.title }} — {{ lesson.status }}
							<span v-if="lesson.error_code">({{ lesson.error_code }})</span>
						</li>
					</ul>
				</div>
				<div
					v-if="results.data?.length"
					class="mt-5 rounded-md border border-outline-gray-2 p-4"
				>
					<div class="flex flex-wrap items-center justify-between gap-3">
						<div>
							<h3 class="font-medium text-ink-gray-9">Generated drafts</h3>
							<p class="mt-1 text-sm text-ink-gray-6">
								Approve the PAI draft, mark it ready, then import one
								unpublished LMS Course. Import never publishes or enrolls
								learners automatically.
							</p>
						</div>
						<Button size="sm" :loading="results.loading" @click="loadResults">
							Refresh drafts
						</Button>
					</div>
					<div
						v-if="canChooseImportInstructor"
						class="mt-4 rounded-md border border-outline-gray-2 bg-surface-gray-1 p-3"
					>
						<label
							for="pai-import-instructor"
							class="block text-sm font-medium text-ink-gray-8"
						>
							LMS Instructor for imported draft
						</label>
						<select
							id="pai-import-instructor"
							v-model="importInstructor"
							class="mt-2 w-full rounded border border-outline-gray-2 bg-surface-white px-3 py-2 text-sm text-ink-gray-8"
						>
							<option value="">Use the request owner</option>
							<option
								v-for="instructor in instructors.data || []"
								:key="instructor.name"
								:value="instructor.name"
							>
								{{ instructor.full_name || instructor.name }} ({{
									instructor.name
								}})
							</option>
						</select>
						<p class="mt-1 text-xs text-ink-gray-6">
							Only moderators and system managers can select a different
							instructor.
						</p>
					</div>
					<ul class="mt-4 space-y-3 text-sm text-ink-gray-7">
						<li v-for="result in results.data" :key="result.result_ref">
							<div
								class="flex flex-wrap items-center justify-between gap-3 rounded-md bg-surface-gray-1 p-3"
							>
								<div>
									<p class="font-medium text-ink-gray-9">
										Version {{ result.version }}
									</p>
									<p class="mt-1 text-xs text-ink-gray-6">
										{{ result.status }}
									</p>
								</div>
								<div class="flex flex-wrap gap-2">
									<Button
										size="sm"
										:loading="
											resultDetail.loading &&
											selectedResultRef === result.result_ref
										"
										@click="reviewDraft(result)"
									>
										Review draft
									</Button>
									<Button
										v-if="canApprove(result)"
										size="sm"
										:disabled="selectedResultRef !== result.result_ref"
										:loading="approveResult.loading"
										@click="approveDraft(result)"
									>
										Approve draft
									</Button>
									<Button
										v-if="result.status === 'APPROVED'"
										size="sm"
										:loading="markResultReady.loading"
										@click="markDraftReady(result)"
									>
										Prepare LMS import
									</Button>
									<Button
										v-if="result.status === 'READY_FOR_MATERIALIZATION'"
										variant="solid"
										size="sm"
										:loading="materializeResult.loading"
										@click="importDraft(result)"
									>
										Import LMS draft
									</Button>
								</div>
							</div>
						</li>
					</ul>
					<div
						v-if="resultDetail.data?.generated_course"
						class="mt-5 rounded-md border border-outline-gray-2 bg-surface-gray-1 p-4"
					>
						<div class="flex items-center justify-between gap-3">
							<div>
								<p class="text-sm text-ink-gray-5">Reviewable PAI draft</p>
								<h4 class="font-medium text-ink-gray-9">
									{{ resultDetail.data.generated_course.course?.title }}
								</h4>
							</div>
							<Badge theme="gray">{{ resultDetail.data.status }}</Badge>
						</div>
						<p class="mt-2 whitespace-pre-wrap text-sm text-ink-gray-7">
							{{ resultDetail.data.generated_course.course?.description }}
						</p>
						<div class="mt-4 space-y-4">
							<div
								v-for="module in resultDetail.data.generated_course.modules"
								:key="`${module.order}-${module.title}`"
								class="rounded-md border border-outline-gray-2 bg-surface-white p-3"
							>
								<p class="font-medium text-ink-gray-9">
									{{ module.order }}. {{ module.title }}
								</p>
								<div
									v-for="lesson in module.lessons"
									:key="`${module.order}-${lesson.order}-${lesson.title}`"
									class="mt-3 border-t border-outline-gray-2 pt-3"
								>
									<p class="text-sm font-medium text-ink-gray-8">
										{{ module.order }}.{{ lesson.order }} {{ lesson.title }}
									</p>
									<div
										v-for="section in lesson.sections"
										:key="`${lesson.order}-${section.order}-${section.title}`"
										class="mt-2 text-sm text-ink-gray-7"
									>
										<p v-if="section.title" class="font-medium text-ink-gray-8">
											{{ section.title }}
										</p>
										<p class="mt-1 whitespace-pre-wrap">
											{{ section.content }}
										</p>
									</div>
								</div>
							</div>
						</div>
					</div>
					<p v-else-if="selectedResultRef" class="mt-4 text-sm text-ink-gray-6">
						This result has no materializable course draft yet.
					</p>
					<router-link
						v-if="importedCourseName"
						class="mt-4 inline-flex rounded-md bg-surface-gray-2 px-3 py-2 text-sm font-medium text-ink-gray-8 hover:bg-surface-gray-3"
						:to="{
							name: 'CourseForm',
							params: { courseName: importedCourseName },
						}"
					>
						Open imported LMS draft
					</router-link>
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
import { computed, inject, onMounted, reactive, ref } from 'vue'
import NoPermission from '@/components/NoPermission.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const allowed = computed(
	() =>
		user.data?.is_system_manager ||
		user.data?.is_moderator ||
		user.data?.is_instructor,
)
const message = ref('')
const workflowMessage = ref('')
const selectedName = ref('')
const selectedResultRef = ref('')
const importedCourseName = ref('')
const importInstructor = ref('')
const requestRetryKey = ref('')
const requestPayloadFingerprint = ref('')
const brief = ref(null)
const plan = ref(null)
const form = reactive({
	title: '',
	goal: '',
	language: 'vi',
	duration: '',
	completionContext: '',
	learnerRefs: '',
	outcomes: '',
	prerequisites: '',
	notes: '',
})
const briefRevision = reactive({
	trainingGoal: '',
	outcomes: '',
	prerequisites: '',
	learningHorizon: '',
	expectedEffort: '',
	feedback: '',
})

const requests = createResource({
	url: 'pai_frappe.api.list_course_authoring_requests',
	auto: false,
	transform(data) {
		return data.map((request) => ({
			...request,
			modified: dayjs(request.modified).fromNow(),
		}))
	},
})
const studioStatus = createResource({
	url: 'pai_frappe.api.get_pai_studio_status',
	auto: false,
})
const isReady = computed(
	() =>
		Boolean(studioStatus.data?.enabled) &&
		Boolean(studioStatus.data?.service_configured) &&
		Boolean(studioStatus.data?.identity_configured),
)
const canChooseImportInstructor = computed(
	() => user.data?.is_system_manager || user.data?.is_moderator,
)
const createRequest = createResource({
	url: 'pai_frappe.api.create_course_authoring_request',
})
const detail = createResource({
	url: 'pai_frappe.api.get_course_authoring_request',
	auto: false,
})
const briefRevisions = createResource({
	url: 'pai_frappe.api.list_authoring_brief_revisions',
	auto: false,
})
const clarifyBrief = createResource({
	url: 'pai_frappe.api.clarify_authoring_brief',
	auto: false,
})
const reviseBrief = createResource({
	url: 'pai_frappe.api.revise_authoring_brief',
	auto: false,
})
const confirmBrief = createResource({
	url: 'pai_frappe.api.confirm_authoring_brief',
	auto: false,
})
const planRequest = createResource({
	url: 'pai_frappe.api.plan_course_authoring_request',
	auto: false,
})
const persistedPlan = createResource({
	url: 'pai_frappe.api.get_course_authoring_plan',
	auto: false,
})
const reviewPlan = createResource({
	url: 'pai_frappe.api.review_course_authoring_plan',
	auto: false,
})
const confirmPlan = createResource({
	url: 'pai_frappe.api.confirm_course_authoring_plan',
	auto: false,
})
const generateRequest = createResource({
	url: 'pai_frappe.api.generate_course_authoring_request',
	auto: false,
})
const generation = createResource({
	url: 'pai_frappe.api.get_course_generation_progress',
	auto: false,
})
const retryGeneration = createResource({
	url: 'pai_frappe.api.retry_course_generation',
	auto: false,
})
const results = createResource({
	url: 'pai_frappe.api.list_course_authoring_results',
	auto: false,
})
const resultDetail = createResource({
	url: 'pai_frappe.api.get_course_authoring_result',
	auto: false,
})
const approveResult = createResource({
	url: 'pai_frappe.api.approve_course_authoring_result',
	auto: false,
})
const markResultReady = createResource({
	url: 'pai_frappe.api.mark_course_authoring_result_ready',
	auto: false,
})
const materializeResult = createResource({
	url: 'pai_frappe.api.materialize_course_authoring_result',
	auto: false,
})
const instructors = createResource({
	url: 'pai_frappe.api.list_lms_instructors',
	auto: false,
})

const lines = (value) =>
	value
		.split('\n')
		.map((item) => item.trim())
		.filter(Boolean)

function payload() {
	return {
		title: form.title.trim(),
		training_brief: {
			goal: form.goal.trim(),
			language: form.language.trim() || null,
			duration_constraint: form.duration.trim() || null,
			target_completion_context: form.completionContext.trim() || null,
			notes: form.notes.trim() || null,
			desired_outcomes: lines(form.outcomes),
			prerequisites: lines(form.prerequisites),
		},
		learner_refs: lines(form.learnerRefs),
		mode: 'GOAL_DRIVEN',
	}
}

function requestFingerprint() {
	return JSON.stringify(payload())
}

function retryKeyForCurrentRequest() {
	const fingerprint = requestFingerprint()
	if (requestPayloadFingerprint.value !== fingerprint) {
		requestPayloadFingerprint.value = fingerprint
		requestRetryKey.value = globalThis.crypto.randomUUID()
	}
	return requestRetryKey.value
}

function errorMessage(error) {
	return error?.messages?.[0] || error?.message || String(error)
}

function submit() {
	message.value = ''
	if (!isReady.value) {
		message.value = 'PAI Studio must be configured before creating a request.'
		return
	}
	if (!form.title.trim() || !form.goal.trim() || !lines(form.outcomes).length) {
		message.value =
			'Course title, training goal, and at least one desired outcome are required.'
		return
	}
	createRequest.submit(
		{ data: payload(), idempotency_key: retryKeyForCurrentRequest() },
		{
			onSuccess(result) {
				message.value = `Request ${result.name} created.`
				requestRetryKey.value = ''
				requestPayloadFingerprint.value = ''
				requests.reload()
				selectRequest(result.name)
			},
			onError(error) {
				message.value = errorMessage(error)
			},
		},
	)
}

function selectRequest(name) {
	if (!isReady.value) {
		workflowMessage.value =
			'PAI Studio must be configured before loading an authoring request.'
		return
	}
	selectedName.value = name
	brief.value = null
	plan.value = null
	selectedResultRef.value = ''
	importedCourseName.value = ''
	importInstructor.value = ''
	generation.reset()
	results.reset()
	resultDetail.reset()
	workflowMessage.value = ''
	loadRequest(name)
	loadBriefs(name)
	loadPlan(name)
	loadGeneration()
	loadResults()
}

onMounted(() => {
	if (!allowed.value) return
	studioStatus.reload()
	requests.reload()
	if (canChooseImportInstructor.value) instructors.reload()
})

function loadRequest(name) {
	detail.submit(
		{ name },
		{
			onSuccess(data) {
				setBriefRevisionForm(data.pai?.training_brief)
			},
			onError: (error) => (workflowMessage.value = errorMessage(error)),
		},
	)
}

function loadBriefs(name) {
	briefRevisions.submit(
		{ name },
		{
			onSuccess(data) {
				brief.value = data[0] || null
				if (brief.value) setBriefRevisionForm(brief.value.payload)
			},
			onError: planCourseError,
		},
	)
}

function loadPlan(name) {
	persistedPlan.submit(
		{ name },
		{
			onSuccess(data) {
				plan.value = data
			},
			onError() {
				// A brief that has not been planned has no plan route yet. Keep the
				// workflow usable and wait for the explicit Create plan action.
				plan.value = null
			},
		},
	)
}

function refreshWorkflow() {
	if (!selectedName.value) return
	workflowMessage.value = ''
	loadRequest(selectedName.value)
	loadBriefs(selectedName.value)
	loadPlan(selectedName.value)
	loadGeneration(true)
	loadResults()
}

function planCourseResponse(data) {
	plan.value = data
	workflowMessage.value = `Curriculum plan ${data.status?.toLowerCase() || 'created'}. Review it before generation.`
}

function planCourseError(error) {
	workflowMessage.value = errorMessage(error)
}

function createPlan() {
	planRequest.submit(
		{ name: selectedName.value },
		{ onSuccess: planCourseResponse, onError: planCourseError },
	)
}

function clarify() {
	clarifyBrief.submit(
		{ name: selectedName.value },
		{
			onSuccess(data) {
				brief.value = data
				setBriefRevisionForm(data.payload)
				workflowMessage.value = `Brief check finished with status ${data.status?.toLowerCase() || 'updated'}.`
			},
			onError: planCourseError,
		},
	)
}

function setBriefRevisionForm(source = {}) {
	briefRevision.trainingGoal = source.training_goal || source.goal || ''
	briefRevision.outcomes = (source.desired_outcomes || []).join('\n')
	briefRevision.prerequisites = (source.prerequisites || []).join('\n')
	briefRevision.learningHorizon = source.learning_horizon || ''
	briefRevision.expectedEffort = source.expected_learning_effort || ''
}

function revisedBriefPayload() {
	const data = {
		training_goal: briefRevision.trainingGoal.trim(),
		desired_outcomes: lines(briefRevision.outcomes),
		prerequisites: lines(briefRevision.prerequisites),
	}
	if (briefRevision.learningHorizon.trim()) {
		data.learning_horizon = briefRevision.learningHorizon.trim()
	}
	if (briefRevision.expectedEffort.trim()) {
		data.expected_learning_effort = briefRevision.expectedEffort.trim()
	}
	if (briefRevision.feedback.trim()) {
		data.author_feedback = briefRevision.feedback.trim()
	}
	return data
}

function saveBriefRevision() {
	reviseBrief.submit(
		{ name: selectedName.value, data: revisedBriefPayload() },
		{
			onSuccess(data) {
				brief.value = data
				setBriefRevisionForm(data.payload)
				briefRevision.feedback = ''
				workflowMessage.value = `Brief revision ${data.version} saved. Check it before confirming.`
			},
			onError: planCourseError,
		},
	)
}

function confirmBriefRevision() {
	confirmBrief.submit(
		{ name: selectedName.value, revision_id: brief.value.id },
		{
			onSuccess(data) {
				brief.value = data
				workflowMessage.value =
					'Authoring brief confirmed. You can now create the curriculum plan.'
			},
			onError: planCourseError,
		},
	)
}

function review() {
	reviewPlan.submit(
		{ name: selectedName.value, plan_id: plan.value.plan_ref },
		{
			onSuccess(data) {
				plan.value = data
				workflowMessage.value = `Plan review finished with status ${data.status?.toLowerCase() || 'updated'}.`
			},
			onError: planCourseError,
		},
	)
}

function confirm() {
	confirmPlan.submit(
		{ name: selectedName.value, plan_id: plan.value.plan_ref },
		{
			onSuccess(data) {
				plan.value = data
				workflowMessage.value =
					'Curriculum plan confirmed. You can now generate a draft.'
			},
			onError: planCourseError,
		},
	)
}

function generate() {
	generateRequest.submit(
		{ name: selectedName.value },
		{
			onSuccess(data) {
				workflowMessage.value = `Generation ${data.status?.toLowerCase() || 'started'}. Refresh status after the worker finishes.`
				loadGeneration()
				loadResults()
			},
			onError: planCourseError,
		},
	)
}

function loadGeneration(showError = false) {
	if (!selectedName.value) return
	generation.submit(
		{ name: selectedName.value },
		{ onError: (error) => showError && planCourseError(error) },
	)
}

function loadResults() {
	if (!selectedName.value) return
	results.submit({ name: selectedName.value }, { onError: planCourseError })
}

function retry() {
	retryGeneration.submit(
		{ name: selectedName.value },
		{
			onSuccess(data) {
				workflowMessage.value = `Retry ${data.status?.toLowerCase() || 'queued'}.`
				loadGeneration()
			},
			onError: planCourseError,
		},
	)
}

function canApprove(result) {
	return ['DRAFT', 'IN_REVIEW', 'REVIEW_REQUIRED'].includes(result.status)
}

function reviewDraft(result) {
	selectedResultRef.value = result.result_ref
	resultDetail.reset()
	resultDetail.submit(
		{ name: selectedName.value, result_ref: result.result_ref },
		{ onError: planCourseError },
	)
}

function approveDraft(result) {
	approveResult.submit(
		{ name: selectedName.value, result_ref: result.result_ref },
		{
			onSuccess() {
				workflowMessage.value =
					'PAI draft approved. It can now be prepared for LMS import.'
				loadResults()
			},
			onError: planCourseError,
		},
	)
}

function markDraftReady(result) {
	markResultReady.submit(
		{ name: selectedName.value, result_ref: result.result_ref },
		{
			onSuccess() {
				workflowMessage.value = 'PAI draft is ready for LMS import.'
				loadResults()
			},
			onError: planCourseError,
		},
	)
}

function importDraft(result) {
	materializeResult.submit(
		{
			name: selectedName.value,
			result_ref: result.result_ref,
			instructor: importInstructor.value || undefined,
		},
		{
			onSuccess(data) {
				workflowMessage.value = data.already_imported
					? `This PAI draft is already linked to LMS Course ${data.lms_course}.`
					: `LMS Course ${data.lms_course} was created as an unpublished draft.`
				importedCourseName.value = data.lms_course
				loadResults()
			},
			onError: planCourseError,
		},
	)
}
</script>
