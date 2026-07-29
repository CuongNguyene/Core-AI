<template>
	<div
		class="relative flex h-full flex-col justify-between transition-all duration-300 ease-in-out border-r bg-surface-menu-bar"
		:class="sidebarStore.isSidebarCollapsed ? 'w-14' : 'w-56'"
	>
		<button
			class="hidden lg:flex absolute -right-3 top-1/2 -translate-y-1/2 z-40 items-center justify-center bg-white border border-gray-200 shadow-md p-1 rounded-full hover:bg-gray-50 text-gray-600 transition-all hover:scale-110 active:scale-95"
			@click="toggleSidebar()"
		>
			<ChevronLeft v-if="!sidebarStore.isSidebarCollapsed" class="h-3.5 w-3.5" />
			<ChevronRight v-else class="h-3.5 w-3.5" />
		</button>
		<div
			class="flex flex-col overflow-hidden"
			:class="sidebarStore.isSidebarCollapsed ? 'items-center' : ''"
		>
			<UserDropdown :isCollapsed="sidebarStore.isSidebarCollapsed" />
			<div class="flex flex-col" v-if="sidebarSettings.data">
				<div v-for="link in sidebarLinks" class="mx-2 my-0.5">
					<SidebarLink
						:link="link"
						:isCollapsed="sidebarStore.isSidebarCollapsed"
					/>
				</div>
			</div>
			<div
				v-if="sidebarSettings.data?.web_pages?.length || isModerator"
				class="mt-4"
			>
				<div
					v-if="sidebarSettings.data?.web_pages?.length"
					class="flex flex-col transition-all duration-300 ease-in-out"
					:class="!sidebarStore.isWebpagesCollapsed ? 'block' : 'hidden'"
				>
					<div
						v-for="link in sidebarSettings.data.web_pages"
						class="mx-2 my-0.5"
					>
						<SidebarLink
							:link="link"
							:isCollapsed="sidebarStore.isSidebarCollapsed"
							:showControls="isModerator ? true : false"
							@openModal="openPageModal"
							@deletePage="deletePage"
						/>
					</div>
				</div>
			</div>
		</div>
		<div class="m-2 flex flex-col gap-1">
			<TrialBanner
				v-if="
					userResource.data?.is_system_manager && userResource.data?.is_fc_site
				"
				:isSidebarCollapsed="sidebarStore.isSidebarCollapsed"
			/>
			<GettingStartedBanner
				v-if="showOnboarding && !isOnboardingStepsCompleted"
				:isSidebarCollapsed="sidebarStore.isSidebarCollapsed"
				appName="learning"
			/>
		</div>
		<HelpModal
			v-if="showOnboarding && showHelpModal"
			v-model="showHelpModal"
			v-model:articles="articles"
			appName="learning"
			title="Frappe Learning"
			:logo="LMSLogo"
			:afterSkip="(step) => capture('onboarding_step_skipped_' + step)"
			:afterSkipAll="() => capture('onboarding_steps_skipped')"
			:afterReset="(step) => capture('onboarding_step_reset_' + step)"
			:afterResetAll="() => capture('onboarding_steps_reset')"
			docsLink="https://docs.frappe.io/learning"
		/>
		<IntermediateStepModal
			v-model="showIntermediateModal"
			:currentStep="currentStep"
		/>
	</div>
	<PageModal
		v-model="showPageModal"
		v-model:reloadSidebar="sidebarSettings"
		:page="pageToEdit"
	/>
</template>

<script setup>
import UserDropdown from '@/components/UserDropdown.vue'
import SidebarLink from '@/components/SidebarLink.vue'
import {
	ref,
	onMounted,
	inject,
	watch,
	reactive,
	markRaw,
	h,
	onUnmounted,
} from 'vue'
import { getSidebarLinks } from '@/utils'
import { usersStore } from '@/stores/user'
import { sessionStore } from '@/stores/session'
import { useSidebar } from '@/stores/sidebar'
import { useSettings } from '@/stores/settings'
import { call, createResource } from 'frappe-ui'
import PageModal from '@/components/Modals/PageModal.vue'
import { capture } from '@/telemetry'
import LMSLogo from '@/components/Icons/LMSLogo.vue'
import { useRouter } from 'vue-router'
import InviteIcon from './Icons/InviteIcon.vue'
import {
	BookOpen,
	ChevronRight,
	ChevronLeft,
	CircleHelp,
	FolderTree,
	FileText,
	UserPlus,
	Users,
	BookText,
} from 'lucide-vue-next'
import {
	TrialBanner,
	HelpModal,
	GettingStartedBanner,
	showHelpModal,
	minimize,
	IntermediateStepModal,
} from 'frappe-ui/frappe'
import { useOnboarding, isOnboardingSupported } from '@/utils/onboardingCompat'

const { user } = sessionStore()
const { userResource } = usersStore()
let sidebarStore = useSidebar()
const socket = inject('$socket')
const unreadCount = ref(0)
const sidebarLinks = ref(getSidebarLinks())
const showPageModal = ref(false)
const isModerator = ref(false)
const isInstructor = ref(false)
const pageToEdit = ref(null)
const settingsStore = useSettings()
const { sidebarSettings } = settingsStore
const showOnboarding = ref(false)
const showIntermediateModal = ref(false)
const currentStep = ref({})
const router = useRouter()
let onboardingDetails
let isOnboardingStepsCompleted = false
const readOnlyMode = window.read_only_mode
const iconProps = {
	strokeWidth: 1.5,
	width: 16,
	height: 16,
}

onMounted(() => {
	addNotifications()
	setSidebarLinks()
	setUpOnboarding()
	socket.on('publish_lms_notifications', (data) => {
		unreadNotifications.reload()
	})
})

const setSidebarLinks = () => {
	sidebarSettings.reload(
		{},
		{
			onSuccess(data) {
				Object.keys(data).forEach((key) => {
					if (!parseInt(data[key])) {
						sidebarLinks.value = sidebarLinks.value.filter(
							(link) => link.label.toLowerCase().split(' ').join('_') !== key
						)
					}
				})
			},
		}
	)
}

const unreadNotifications = createResource({
	cache: 'Unread Notifications Count',
	url: 'lms.lms.api.get_unread_notification_count',
	onSuccess(data) {
		unreadCount.value = data
		sidebarLinks.value = sidebarLinks.value.map((link) => {
			if (link.label === 'Notifications') {
				link.count = data
			}
			return link
		})
	},
	auto: user ? true : false,
})

const addNotifications = () => {
	if (user) {
		sidebarLinks.value.push({
			label: 'Notifications',
			icon: 'Bell',
			to: 'Notifications',
			activeFor: ['Notifications'],
			count: unreadCount.value,
		})
	}
}

const addQuizzes = () => {
	if (isInstructor.value || isModerator.value) {
		sidebarLinks.value.splice(4, 0, {
			label: 'Quizzes',
			icon: 'CircleHelp',
			to: 'Quizzes',
			activeFor: [
				'Quizzes',
				'QuizForm',
				'QuizSubmissionList',
				'QuizSubmission',
			],
		})
	}
}

const addAssignments = () => {
	if (isInstructor.value || isModerator.value) {
		sidebarLinks.value.splice(5, 0, {
			label: 'Assignments',
			icon: 'Pencil',
			to: 'Assignments',
			activeFor: [
				'Assignments',
				'AssignmentForm',
				'AssignmentSubmissionList',
				'AssignmentSubmission',
			],
		})
	}
}

// const addProgrammingExercises = () => {
// 	if (isInstructor.value || isModerator.value) {
// 		sidebarLinks.value.splice(3, 0, {
// 			label: 'Programming Exercises',
// 			icon: 'Code',
// 			to: 'ProgrammingExercises',
// 			activeFor: [
// 				'ProgrammingExercises',
// 				'ProgrammingExerciseForm',
// 				'ProgrammingExerciseSubmissions',
// 				'ProgrammingExerciseSubmission',
// 			],
// 		})
// 	}
// }

const addPrograms = async () => {
	let canAddProgram = await checkIfCanAddProgram()
	if (!canAddProgram) return
	let activeFor = ['Programs', 'ProgramDetail']
	let index = 2

	sidebarLinks.value.splice(index, 0, {
		label: 'Programs',
		icon: 'Route',
		to: 'Programs',
		activeFor: activeFor,
	})
}

const addContactUsDetails = () => {
	if (settingsStore.contactUsEmail?.data || settingsStore.contactUsURL?.data) {
		sidebarLinks.value.push({
			label: 'Contact Us',
			icon: settingsStore.contactUsURL?.data ? 'Headset' : 'Mail',
			to: settingsStore.contactUsURL?.data
				? settingsStore.contactUsURL.data
				: settingsStore.contactUsEmail?.data,
		})
	}
}

const checkIfCanAddProgram = async () => {
	if (isModerator.value || isInstructor.value) {
		return true
	}
	const programs = await call('lms.lms.utils.get_programs')
	return programs.enrolled.length > 0 || programs.published.length > 0
}

const addHome = () => {
	sidebarLinks.value.unshift({
		label: 'Home',
		icon: 'Home',
		to: 'Home',
		activeFor: ['Home'],
	})
}

const openPageModal = (link) => {
	showPageModal.value = true
	pageToEdit.value = link
}

const deletePage = (link) => {
	createResource({
		url: 'lms.lms.api.delete_sidebar_item',
		makeParams(values) {
			return {
				webpage: link.web_page,
			}
		},
	}).submit(
		{},
		{
			onSuccess() {
				sidebarSettings.reload()
			},
		}
	)
}

const toggleSidebar = () => {
	sidebarStore.isSidebarCollapsed = !sidebarStore.isSidebarCollapsed
	localStorage.setItem(
		'isSidebarCollapsed',
		JSON.stringify(sidebarStore.isSidebarCollapsed)
	)
}

// const toggleWebPages = () => {
// 	sidebarStore.isWebpagesCollapsed = !sidebarStore.isWebpagesCollapsed
// 	localStorage.setItem(
// 		'isWebpagesCollapsed',
// 		JSON.stringify(sidebarStore.isWebpagesCollapsed)
// 	)
// }

const getFirstCourse = async () => {
	let firstCourse = localStorage.getItem('firstCourse')
	if (firstCourse) return firstCourse
	return await call('lms.lms.onboarding.get_first_course')
}

const getFirstBatch = async () => {
	let firstBatch = localStorage.getItem('firstBatch')
	if (firstBatch) return firstBatch
	return await call('lms.lms.onboarding.get_first_batch')
}

const steps = reactive([
	{
		name: 'create_first_course',
		title: __('sidebar.onboarding.createFirstCourse'),
		icon: markRaw(h(BookOpen, iconProps)),
		completed: false,
		onClick: () => {
			minimize.value = true
			router.push({
				name: 'Courses',
			})
		},
	},
	{
		name: 'create_first_chapter',
		title: __('sidebar.onboarding.addFirstChapter'),
		icon: markRaw(h(FolderTree, iconProps)),
		completed: false,
		dependsOn: 'create_first_course',
		onClick: async () => {
			minimize.value = true
			let course = await getFirstCourse()
			if (course) {
				router.push({ name: 'CourseForm', params: { courseName: course } })
			} else {
				router.push({ name: 'CourseForm' })
			}
		},
	},
	{
		name: 'create_first_lesson',
		title: __('sidebar.onboarding.addFirstLesson'),
		icon: markRaw(h(FileText, iconProps)),
		completed: false,
		dependsOn: 'create_first_chapter',
		onClick: async () => {
			minimize.value = true
			let course = await getFirstCourse()
			if (course) {
				router.push({
					name: 'CourseForm',
					params: { courseName: course },
				})
			} else {
				router.push({ name: 'Courses' })
			}
		},
	},
	{
		name: 'create_first_quiz',
		title: __('sidebar.onboarding.createFirstQuiz'),
		icon: markRaw(h(CircleHelp, iconProps)),
		completed: false,
		dependsOn: 'create_first_course',
		onClick: () => {
			minimize.value = true
			router.push({ name: 'Quizzes' })
		},
	},
	{
		name: 'invite_students',
		title: __('sidebar.onboarding.inviteTeamAndStudents'),
		icon: markRaw(h(InviteIcon, iconProps)),
		completed: false,
		onClick: () => {
			minimize.value = true
			settingsStore.activeTab = 'Members'
			settingsStore.isSettingsOpen = true
		},
	},
	{
		name: 'create_first_batch',
		title: __('sidebar.onboarding.createFirstBatch'),
		icon: markRaw(h(Users, iconProps)),
		completed: false,
		onClick: () => {
			minimize.value = true
			router.push({ name: 'Batches' })
		},
	},
	{
		name: 'add_batch_student',
		title: __('sidebar.onboarding.addStudentsToBatch'),
		icon: markRaw(h(UserPlus, iconProps)),
		completed: false,
		dependsOn: 'create_first_batch',
		onClick: async () => {
			minimize.value = true
			let batch = await getFirstBatch()
			if (batch) {
				router.push({
					name: 'Batch',
					params: {
						batchName: batch,
					},
				})
			} else {
				router.push({ name: 'Batch' })
			}
		},
	},
	{
		name: 'add_batch_course',
		title: __('sidebar.onboarding.addCoursesToBatch'),
		icon: markRaw(h(BookText, iconProps)),
		completed: false,
		dependsOn: 'create_first_batch',
		onClick: async () => {
			minimize.value = true
			let batch = await getFirstBatch()
			if (batch) {
				router.push({
					name: 'Batch',
					params: {
						batchName: batch,
					},
					hash: '#courses',
				})
			} else {
				router.push({ name: 'Batch' })
			}
		},
	},
])

const articles = ref([
	{
		title: __('sidebar.help.introduction'),
		opened: false,
		subArticles: [
			{ name: 'introduction', title: __('sidebar.help.introduction') },
			{ name: 'setting-up', title: __('sidebar.help.settingUp') },
		],
	},
	{
		title: __('sidebar.help.creatingACourse'),
		opened: false,
		subArticles: [
			{ name: 'create-a-course', title: __('sidebar.help.createACourse') },
			{ name: 'add-a-chapter', title: __('sidebar.help.addAChapter') },
			{ name: 'add-a-lesson', title: __('sidebar.help.addALesson') },
		],
	},
	{
		title: __('sidebar.help.creatingABatch'),
		opened: false,
		subArticles: [
			{ name: 'create-a-batch', title: __('sidebar.help.createABatch') },
			{ name: 'create-a-live-class', title: __('sidebar.help.createALiveClass') },
		],
	},
	{
		title: __('sidebar.help.learningPaths'),
		opened: false,
		subArticles: [{ name: 'add-a-program', title: __('sidebar.help.addAProgram') }],
	},
	{
		title: __('sidebar.help.assessments'),
		opened: false,
		subArticles: [
			{ name: 'quizzes', title: __('quiz.builder.quizzes') },
			{ name: 'assignments', title: __('assignments.assignments') },
		],
	},
	{
		title: __('sidebar.help.certification'),
		opened: false,
		subArticles: [
			{ name: 'issue-a-certificate', title: __('sidebar.help.issueACertificate') },
			{
				name: 'custom-certificate-templates',
				title: __('sidebar.help.customCertificateTemplates'),
			},
		],
	},
	{
		title: __('sidebar.help.monetization'),
		opened: false,
		subArticles: [
			{
				name: 'setting-up-payment-gateway',
				title: __('sidebar.help.settingUpPaymentGateway'),
			},
		],
	},
	{
		title: __('sidebar.settings'),
		opened: false,
		subArticles: [{ name: 'roles', title: __('sidebar.help.roles') }],
	},
])

const setUpOnboarding = () => {
	// TEMP (Frappe v15 compat): skip onboarding entirely when the backend has no
	// frappe.onboarding module, so the GettingStartedBanner / HelpModal (which
	// call the missing API internally) never mount. Remove with onboardingCompat.
	if (!isOnboardingSupported()) return
	if (userResource.data?.is_system_manager) {
		onboardingDetails = useOnboarding('learning')
		onboardingDetails.setUp(steps)
		isOnboardingStepsCompleted = onboardingDetails.isOnboardingStepsCompleted
		showOnboarding.value = true
	}
}

watch(userResource, () => {
	addContactUsDetails()
	if (userResource.data) {
		isModerator.value = userResource.data.is_moderator
		isInstructor.value = userResource.data.is_instructor
		addHome()
		addPrograms()
		// addProgrammingExercises()
		addQuizzes()
		addAssignments()
		setUpOnboarding()
	}
})

onUnmounted(() => {
	socket.off('publish_lms_notifications')
})
</script>
