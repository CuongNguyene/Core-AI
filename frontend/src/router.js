import { createRouter, createWebHistory } from 'vue-router'
import { usersStore } from './stores/user'
import { sessionStore } from './stores/session'
import { useSettings } from './stores/settings'

const routes = [
	{
		path: '/',
		name: 'Home',
		component: () => import('@/pages/Home/Home.vue'),
	},
	{
		path: '/courses',
		name: 'Courses',
		component: () => import('@/pages/Courses.vue'),
	},
	{
		path: '/courses/:courseName',
		name: 'CourseDetail',
		component: () => import('@/pages/CourseDetail.vue'),
		props: true,
	},
	{
		path: '/courses/:courseName/learn/:chapterNumber-:lessonNumber',
		name: 'Lesson',
		component: () => import('@/pages/Lesson.vue'),
		props: true,
	},
	// {
	// 	path: '/courses/:courseName/certification',
	// 	name: 'CourseCertification',
	// 	component: () => import('@/pages/CourseCertification.vue'),
	// 	props: true,
	// },
	{
		path: '/courses/:courseName/learn/:chapterName',
		name: 'SCORMChapter',
		component: () => import('@/pages/SCORMChapter.vue'),
		props: true,
	},
	{
		path: '/batches',
		name: 'Batches',
		component: () => import('@/pages/Batches.vue'),
	},
	{
		path: '/batches/details/:batchName',
		name: 'BatchDetail',
		component: () => import('@/pages/BatchDetail.vue'),
		props: true,
	},
	{
		path: '/batches/:batchName',
		name: 'Batch',
		component: () => import('@/pages/Batch.vue'),
		props: true,
	},
	{
		path: '/billing/:type/:name',
		name: 'Billing',
		component: () => import('@/pages/Billing.vue'),
		props: true,
	},
	{
		path: '/statistics',
		name: 'Statistics',
		component: () => import('@/pages/Statistics.vue'),
	},
	{
		path: '/user/:username',
		name: 'Profile',
		component: () => import('@/pages/Profile.vue'),
		props: true,
		redirect: { name: 'ProfileAbout' },
		children: [
			{
				name: 'ProfileAbout',
				path: '',
				component: () => import('@/pages/ProfileAbout.vue'),
			},
			{
				name: 'ProfileCertificates',
				path: 'certificates',
				component: () => import('@/pages/ProfileCertificates.vue'),
			},
			{
				name: 'ProfileRoles',
				path: 'roles',
				component: () => import('@/pages/ProfileRoles.vue'),
			},
			// {
			// 	name: 'ProfileEvaluator',
			// 	path: 'slots',
			// 	component: () => import('@/pages/ProfileEvaluator.vue'),
			// },
			// {
			// 	name: 'ProfileEvaluationSchedule',
			// 	path: 'schedule',
			// 	component: () =>
			// 		import('@/pages/ProfileEvaluationSchedule.vue'),
			// },
		],
	},
	// {
	// 	path: '/job-openings',
	// 	name: 'Jobs',
	// 	component: () => import('@/pages/Jobs.vue'),
	// },
	// {
	// 	path: '/job-openings/:job',
	// 	name: 'JobDetail',
	// 	component: () => import('@/pages/JobDetail.vue'),
	// 	props: true,
	// },
	{
		path: '/courses/:courseName/edit',
		name: 'CourseForm',
		component: () => import('@/pages/CourseForm.vue'),
		props: true,
	},
	{
		path: '/courses/:courseName/learn/:chapterNumber-:lessonNumber/edit',
		name: 'LessonForm',
		component: () => import('@/pages/LessonForm.vue'),
		props: true,
	},
	{
		path: '/batches/:batchName/edit',
		name: 'BatchForm',
		component: () => import('@/pages/BatchForm.vue'),
		props: true,
	},
	{
		path: '/job-opening/:jobName/edit',
		name: 'JobForm',
		component: () => import('@/pages/JobForm.vue'),
		props: true,
	},
	{
		path: '/certified-participants',
		name: 'CertifiedParticipants',
		component: () => import('@/pages/CertifiedParticipants.vue'),
	},
	{
		path: '/notifications',
		name: 'Notifications',
		component: () => import('@/pages/Notifications.vue'),
	},
	{
		path: '/badges/:badgeName/:email',
		name: 'Badge',
		component: () => import('@/pages/Badge.vue'),
		props: true,
	},
	{
		path: '/quizzes',
		name: 'Quizzes',
		component: () => import('@/pages/Quizzes.vue'),
	},
	{
		path: '/quizzes/:quizID',
		name: 'QuizForm',
		component: () => import('@/pages/QuizForm.vue'),
		props: true,
	},
	{
		path: '/quiz/:quizID',
		name: 'QuizPage',
		component: () => import('@/pages/QuizPage.vue'),
		props: true,
	},
	{
		path: '/quiz-submissions/:quizID',
		name: 'QuizSubmissionList',
		component: () => import('@/pages/QuizSubmissionList.vue'),
		props: true,
	},
	{
		path: '/quiz-submission/:submission',
		name: 'QuizSubmission',
		component: () => import('@/pages/QuizSubmission.vue'),
		props: true,
	},
	{
		path: '/programs',
		name: 'Programs',
		component: () => import('@/pages/Programs/Programs.vue'),
	},
	{
		path: '/programs/:programName',
		name: 'ProgramDetail',
		component: () => import('@/pages/Programs/ProgramDetail.vue'),
		props: true,
	},
	{
		path: '/assignments',
		name: 'Assignments',
		component: () => import('@/pages/Assignments.vue'),
	},
	{
		path: '/assignment-submission/:assignmentID/:submissionName',
		name: 'AssignmentSubmission',
		component: () => import('@/pages/AssignmentSubmission.vue'),
		props: true,
	},
	{
		path: '/assignment-submissions',
		name: 'AssignmentSubmissionList',
		component: () => import('@/pages/AssignmentSubmissionList.vue'),
	},
	{
		path: '/persona',
		name: 'PersonaForm',
		component: () => import('@/pages/PersonaForm.vue'),
	},
	// {
	// 	path: '/programming-exercises',
	// 	name: 'ProgrammingExercises',
	// 	component: () =>
	// 		import('@/pages/ProgrammingExercises/ProgrammingExercises.vue'),
	// },
	// {
	// 	path: '/programming-exercises/submissions',
	// 	name: 'ProgrammingExerciseSubmissions',
	// 	component: () =>
	// 		import(
	// 			'@/pages/ProgrammingExercises/ProgrammingExerciseSubmissions.vue'
	// 		),
	// 	props: true,
	// },
	// {
	// 	path: '/programming-exercises/:exerciseID/submission/:submissionID',
	// 	name: 'ProgrammingExerciseSubmission',
	// 	component: () =>
	// 		import(
	// 			'@/pages/ProgrammingExercises/ProgrammingExerciseSubmission.vue'
	// 		),
	// 	props: true,
	{
		path: '/:pathMatch(.*)*',
		name: 'NotFound',
		component: () => import('@/pages/NotFound.vue'),
	},
]

let router = createRouter({
	history: createWebHistory('/lms'),
	routes,
})

// After a new deploy, previously-loaded pages reference chunk files (by
// content hash) that no longer exist on the server. Loading a route not yet
// fetched in this session then fails with "Failed to fetch dynamically
// imported module" and silently aborts navigation. Recover by doing a single
// hard reload to pick up the new build instead of leaving the user stuck.
const RELOAD_FLAG = 'lms:reloaded-after-chunk-error'

function isChunkLoadError(error) {
	let message = error?.message || ''
	return (
		/failed to fetch dynamically imported module/i.test(message) ||
		/error loading dynamically imported module/i.test(message) ||
		/importing a module script failed/i.test(message)
	)
}

function reloadOnce() {
	if (sessionStorage.getItem(RELOAD_FLAG)) return
	sessionStorage.setItem(RELOAD_FLAG, '1')
	window.location.reload()
}

router.onError((error, to) => {
	if (isChunkLoadError(error)) {
		reloadOnce()
	}
})

router.afterEach(() => {
	// A route that resolved successfully means the current build's assets are
	// loadable again, so a future genuine error should be allowed to trigger
	// another reload rather than being silently swallowed by the guard.
	sessionStorage.removeItem(RELOAD_FLAG)
})

window.addEventListener('vite:preloadError', () => {
	reloadOnce()
})

router.beforeEach(async (to, from, next) => {
	const { userResource } = usersStore()
	let { isLoggedIn } = sessionStore()
	const { allowGuestAccess } = useSettings()

	try {
		if (isLoggedIn) {
			await userResource.promise
		}
	} catch (error) {
		isLoggedIn = false
	}

	if (!isLoggedIn) {
		if (to.name == 'Home') router.push({ name: 'Courses' })

		await allowGuestAccess.promise
		if (!allowGuestAccess.data) {
			window.location.href = `/login?redirect-to=${encodeURIComponent(
				'/lms' + to.fullPath,
			)}`
			return
		}
	}
	return next()
})

export default router
