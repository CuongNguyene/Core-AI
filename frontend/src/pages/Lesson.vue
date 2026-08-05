<template>
	<div v-if="lesson.data" class="">
		<header
			class="sticky top-0 z-10 flex items-center justify-between gap-x-3 border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<div class="min-w-0 flex-1 overflow-hidden">
				<Breadcrumbs class="h-7" :items="breadcrumbs" />
			</div>
			<div class="flex items-center space-x-2 shrink-0">
				<Tooltip v-if="canGoZen()" :text="__('Zen Mode')">
					<Button @click="goFullScreen()">
						<template #icon>
							<Focus class="w-4 h-4 stroke-2" />
						</template>
					</Button>
				</Tooltip>
				<Button v-if="canSeeStats()" @click="showVideoStats()">
					<template #icon>
						<TrendingUp class="size-4 stroke-1.5" />
					</template>
				</Button>
				<CertificationLinks :courseName="courseName" />
				<Button v-if="lesson.data.prev" @click="switchLesson('prev')">
					<template #prefix>
						<ChevronLeft class="w-4 h-4 stroke-1" />
					</template>
					<span>
						{{ __('Previous') }}
					</span>
				</Button>

				<router-link
					v-if="allowEdit()"
					:to="{
						name: 'LessonForm',
						params: {
							courseName: courseName,
							chapterNumber: props.chapterNumber,
							lessonNumber: props.lessonNumber,
						},
					}"
				>
					<Button>
						{{ __('Edit') }}
					</Button>
				</router-link>

				<Button v-if="lesson.data.next" @click="switchLesson('next')">
					<template #suffix>
						<ChevronRight class="w-4 h-4 stroke-1" />
					</template>
					<span>
						{{ __('Next') }}
					</span>
				</Button>

				<router-link
					v-else
					:to="{
						name: 'CourseDetail',
						params: { courseName: courseName },
					}"
				>
					<Button>
						{{ __('Back to Course') }}
					</Button>
				</router-link>
			</div>
		</header>
		<div class="grid md:grid-cols-[70%,30%] h-screen">
			<div v-if="lesson.data.no_preview" class="border-r">
				<div class="shadow rounded-md w-3/4 mt-10 mx-auto text-center p-4">
					<div class="flex items-center justify-center mt-4 space-x-2">
						<LockKeyholeIcon class="size-4 stroke-2 text-ink-gray-5" />
						<div class="text-lg font-semibold text-ink-gray-7">
							{{ __('This lesson is locked') }}
						</div>
					</div>
					<div class="mt-1 mb-4 text-ink-gray-7">
						{{
							__(
								'This lesson is not available for preview. Please enroll in the course to access it.'
							)
						}}
					</div>
					<Button
						v-if="user.data && !lesson.data.disable_self_learning"
						@click="enrollStudent()"
						variant="solid"
					>
						{{ __('Start Learning') }}
					</Button>
					<Badge
						theme="blue"
						size="lg"
						v-else-if="lesson.data.disable_self_learning"
						class="mt-2"
					>
						{{ __('Contact the Administrator to enroll for this course.') }}
					</Badge>
					<Button v-else @click="redirectToLogin()">
						<template #prefix>
							<LogIn class="w-4 h-4 stroke-1" />
						</template>
						{{ __('Login') }}
					</Button>
				</div>
			</div>
			<div v-else-if="lesson.data.locked" class="border-r">
				<div class="shadow rounded-md w-3/4 mt-10 mx-auto text-center p-4">
					<div class="flex items-center justify-center mt-4 space-x-2">
						<LockKeyholeIcon class="size-4 stroke-2 text-ink-gray-5" />
						<div class="text-lg font-semibold text-ink-gray-7">
							{{ __('This lesson is locked') }}
						</div>
					</div>
					<div class="mt-1 mb-4 text-ink-gray-7">
						{{
							__(
								'Complete the previous lesson to unlock {0}.'
							).format(lesson.data.title)
						}}
					</div>
					<Button v-if="lesson.data.prev" @click="switchLesson('prev')">
						{{ __('Go to Previous Lesson') }}
					</Button>
				</div>
			</div>
			<div
				v-else
				ref="lessonContainer"
				class="bg-surface-white"
				:class="{
					'overflow-y-auto': zenModeEnabled,
				}"
			>
				<div
					class="border-r pt-5 pb-10 h-full"
					:class="{
						'w-full md:w-3/5 mx-auto border-none !pt-10': zenModeEnabled,
					}"
				>
					<div class="px-5">
						<IntegrityWarningBanner
							v-if="lesson.data.enable_integrity_warnings"
							:count="violationCount"
						/>
						<div
							class="flex flex-col space-y-3 md:space-y-0 md:flex-row md:items-center justify-between"
						>
							<div class="flex flex-col">
								<div class="text-3xl font-semibold text-ink-gray-9">
									{{ lesson.data.title }}
								</div>

								<div
									v-if="zenModeEnabled"
									class="relative flex items-center space-x-2 text-sm mt-1 text-ink-gray-7 group w-fit mt-2"
								>
									<span>
										{{ lesson.data.chapter_title }} -
										{{ lesson.data.course_title }}
									</span>
									<Info class="size-3" />
									<div
										class="hidden group-hover:block rounded bg-gray-900 px-2 py-1 text-xs text-white shadow-xl absolute left-0 top-full mt-2"
									>
										{{ Math.ceil(lesson.data.membership.progress) }}%
										{{ __('completed') }}
									</div>
								</div>
							</div>

							<div
								v-if="zenModeEnabled"
								class="flex items-center space-x-2 mt-2 md:mt-0"
							>
								<Button @click="showDiscussionsInZenMode()">
									<template #icon>
										<MessageCircleQuestion class="w-4 h-4 stroke-1.5" />
									</template>
								</Button>
								<Button v-if="lesson.data.prev" @click="switchLesson('prev')">
									<template #prefix>
										<ChevronLeft class="w-4 h-4 stroke-1" />
									</template>
									<span>
										{{ __('Previous') }}
									</span>
								</Button>

								<router-link
									v-if="allowEdit()"
									:to="{
										name: 'LessonForm',
										params: {
											courseName: courseName,
											chapterNumber: props.chapterNumber,
											lessonNumber: props.lessonNumber,
										},
									}"
								>
									<Button>
										{{ __('Edit') }}
									</Button>
								</router-link>

								<Button v-if="lesson.data.next" @click="switchLesson('next')">
									<template #suffix>
										<ChevronRight class="w-4 h-4 stroke-1" />
									</template>
									<span>
										{{ __('Next') }}
									</span>
								</Button>

								<router-link
									v-else
									:to="{
										name: 'CourseDetail',
										params: { courseName: courseName },
									}"
								>
									<Button>
										{{ __('Back to Course') }}
									</Button>
								</router-link>
							</div>
						</div>

						<div v-if="!zenModeEnabled" class="flex items-center mt-4 md:mt-2">
							<span
								class="h-6 mr-1"
								:class="{
									'avatar-group overlap': lesson.data.instructors?.length > 1,
								}"
							>
								<UserAvatar
									v-for="instructor in lesson.data.instructors"
									:user="instructor"
								/>
							</span>
							<CourseInstructors
								v-if="lesson.data?.instructors"
								:instructors="lesson.data.instructors"
							/>
						</div>

						<div
							v-if="
								lesson.data.instructor_content &&
								JSON.parse(lesson.data.instructor_content)?.blocks?.length >
									1 &&
								allowInstructorContent()
							"
							class="bg-surface-gray-2 p-3 rounded-md mt-6"
						>
							<div class="text-ink-gray-5 font-medium">
								{{ __('Instructor Notes') }}
							</div>
							<div
								id="instructor-content"
								class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal"
							></div>
						</div>
						<div
							v-else-if="lesson.data.instructor_notes"
							class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal mt-8"
						>
							<LessonContent :content="lesson.data.instructor_notes" />
						</div>
						<div
							v-if="lesson.data.content"
							@mouseup="toggleInlineMenu"
							class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal mt-8"
						>
							<div id="editor"></div>
						</div>
						<div
							v-else
							class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal mt-8"
						>
							<LessonContent
								v-if="lesson.data?.body"
								:content="lesson.data.body"
								:youtube="lesson.data.youtube"
								:quizId="lesson.data.quiz_id"
							/>
						</div>
					</div>

					<!-- Reading Timer Bar -->
					<div
						v-if="lesson.data.membership && lesson.data.min_reading_time > 0 && !readingTimeMet"
						class="mt-6 px-5"
					>
						<div class="flex items-center justify-between mb-1 text-sm text-ink-gray-5">
							<span>{{ __('Reading time required') }}</span>
							<span>{{ readingTimeElapsed }}s / {{ lesson.data.min_reading_time }}s</span>
						</div>
						<div class="w-full h-1.5 bg-surface-gray-3 rounded-full overflow-hidden">
							<div
								class="h-full bg-blue-500 rounded-full transition-all duration-1000"
								:style="{ width: (readingTimeElapsed / lesson.data.min_reading_time * 100) + '%' }"
							></div>
						</div>
					</div>

					<!-- Completion Quiz -->
					<div
						v-if="lesson.data.completion_quiz && lesson.data.membership"
						class="mt-8 px-5"
					>
						<div class="flex items-center gap-2 mb-4 pb-3 border-b">
							<MessageCircleQuestion class="w-5 h-5 text-blue-500" />
							<span class="font-semibold text-ink-gray-9">{{ __('Lesson Quiz') }}</span>
							<span class="text-sm text-ink-gray-5">{{ __('(required to complete this lesson)') }}</span>
						</div>
						<QuizBlock :quiz="lesson.data.completion_quiz" />
					</div>

					<!-- Manual completion fallback -->
					<div v-if="lesson.data.membership && !lesson.data.progress" class="mt-8 px-5">
						<Button @click="markLessonCompleteManually()">
							<template #prefix>
								<CircleCheck class="w-4 h-4 stroke-1.5" />
							</template>
							{{ __('Mark as Complete') }}
						</Button>
					</div>

					<div
						v-if="lesson.data"
						class="mt-10 pb-20 pt-5 border-t px-5"
						ref="discussionsContainer"
					>
						<TabButtons
							v-if="tabs.length > 1"
							:buttons="tabs"
							v-model="currentTab"
							class="w-fit mb-10"
						/>
						<Notes
							v-if="currentTab === 'Notes'"
							:lesson="lesson.data?.name"
							v-model:notes="notes"
							@updateNotes="updateNotes"
						/>
						<Discussions
							v-else-if="allowDiscussions"
							:title="'Questions'"
							:doctype="'Course Lesson'"
							:docname="lesson.data.name"
							:key="lesson.data.name"
							:emptyStateText="
								__('Ask a question to get help from the community.')
							"
						/>
					</div>
				</div>
			</div>
			<div class="sticky top-10">
				<div class="bg-surface-menu-bar py-5 px-2 border-b">
					<div class="text-lg font-semibold text-ink-gray-9">
						{{ lesson.data.course_title }}
					</div>
					<div
						v-if="user && lesson.data.membership"
						class="text-sm mt-4 mb-2 text-ink-gray-5"
					>
						{{ Math.ceil(lessonProgress) }}% {{ __('completed') }}
					</div>

					<ProgressBar
						v-if="user && lesson.data.membership"
						:progress="lessonProgress"
					/>
				</div>
				<CourseOutline
					:courseName="courseName"
					:key="chapterNumber"
					:getProgress="lesson.data.membership ? true : false"
					:lessonProgress="lessonProgress"
				/>
			</div>
		</div>
	</div>
	<DetailSkeleton v-else />
	<InlineLessonMenu
		v-if="lesson.data"
		v-model="showInlineMenu"
		:lesson="lesson.data?.name"
		v-model:notes="notes"
		@updateNotes="updateNotes"
	/>
	<VideoStatistics
		v-model="showStatsDialog"
		:lessonName="lesson.data?.name"
		:lessonTitle="lesson.data?.title"
	/>
</template>
<script setup>
import {
	Badge,
	Breadcrumbs,
	Button,
	call,
	createListResource,
	createResource,
	TabButtons,
	toast,
	Tooltip,
	usePageMeta,
} from 'frappe-ui'
import {
	computed,
	watch,
	inject,
	ref,
	onMounted,
	onBeforeUnmount,
	nextTick,
} from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
	ChevronLeft,
	ChevronRight,
	CircleCheck,
	LockKeyholeIcon,
	LogIn,
	Focus,
	Info,
	MessageCircleQuestion,
	TrendingUp,
} from 'lucide-vue-next'
import { getEditorTools, enablePlyr, highlightText } from '@/utils'
import { useVisibilityLog } from '@/composables/useVisibilityLog'
import { useExamGuards } from '@/composables/useExamGuards'
import IntegrityWarningBanner from '@/components/IntegrityWarningBanner.vue'
import { sessionStore } from '@/stores/session'
import { useSidebar } from '@/stores/sidebar'
import { useSettings } from '@/stores/settings'
import EditorJS from '@editorjs/editorjs'
import LessonContent from '@/components/LessonContent.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import Discussions from '@/components/Discussions.vue'
import CertificationLinks from '@/components/CertificationLinks.vue'
import VideoStatistics from '@/components/Modals/VideoStatistics.vue'
import CourseOutline from '@/components/CourseOutline.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import Notes from '@/components/Notes/Notes.vue'
import InlineLessonMenu from '@/components/Notes/InlineLessonMenu.vue'
import QuizBlock from '@/components/QuizBlock.vue'
import DetailSkeleton from '@/components/DetailSkeleton.vue'

const user = inject('$user')
const socket = inject('$socket')
const router = useRouter()
const route = useRoute()
const allowDiscussions = ref(false)
const editor = ref(null)
const instructorEditor = ref(null)
const lessonProgress = ref(0)
const lessonContainer = ref(null)
const zenModeEnabled = ref(false)
const showStatsDialog = ref(false)
const hasQuiz = ref(false)
const discussionsContainer = ref(null)
const timer = ref(0)
const readingTimeElapsed = ref(0)
const readingTimeMet = ref(false)
const { brand } = sessionStore()
const sidebarStore = useSidebar()
const settingsStore = useSettings()
const threshold = computed(
	() => Number(settingsStore.videoCompletionThreshold?.data) || 90
)
const plyrSources = ref([])
const showInlineMenu = ref(false)
const currentTab = ref('Notes')
let timerInterval
let studyTimeInterval
let visibilityLog = { start: () => {}, stop: () => {} }
let examGuards = { start: () => {}, stop: () => {} }
const violationCount = ref(0)

const tabs = ref([
	{
		label: __('Notes'),
		value: 'Notes',
	},
])

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
	chapterNumber: {
		type: String,
		required: true,
	},
	lessonNumber: {
		type: String,
		required: true,
	},
})

onMounted(() => {
	startTimer()
	startStudyTimeTracking()
	sidebarStore.isSidebarCollapsed = true
	document.addEventListener('fullscreenchange', attachFullscreenEvent)
	socket.on('update_lesson_progress', (data) => {
		if (data.course === props.courseName) {
			lessonProgress.value = data.progress
		}
	})
})

const STUDY_TIME_HEARTBEAT_SECONDS = 30

// Tracks actual elapsed wall-clock time since the last flush, rather than
// blindly recording a fixed 30s per tick, so a partial window (tab hidden,
// lesson switched, or the page closed before the next tick) is still
// recorded instead of being silently dropped.
let studyHeartbeatAt = null

const flushStudyTime = () => {
	const trackedSince = studyHeartbeatAt
	const now = Date.now()
	studyHeartbeatAt = document.visibilityState === 'visible' ? now : null

	if (!trackedSince || !lesson.data?.membership) return
	const elapsed = Math.round((now - trackedSince) / 1000)
	if (elapsed <= 0) return

	call('lms.lms.api.record_study_time', {
		course: props.courseName,
		seconds: elapsed,
	})
}

const onStudyVisibilityChange = () => {
	if (document.visibilityState === 'visible') {
		studyHeartbeatAt = Date.now()
	} else {
		flushStudyTime()
	}
}

const startStudyTimeTracking = () => {
	clearInterval(studyTimeInterval)
	studyHeartbeatAt = document.visibilityState === 'visible' ? Date.now() : null
	document.addEventListener('visibilitychange', onStudyVisibilityChange)
	window.addEventListener('beforeunload', flushStudyTime)
	studyTimeInterval = setInterval(flushStudyTime, STUDY_TIME_HEARTBEAT_SECONDS * 1000)
}

const stopStudyTimeTracking = () => {
	clearInterval(studyTimeInterval)
	flushStudyTime()
	document.removeEventListener('visibilitychange', onStudyVisibilityChange)
	window.removeEventListener('beforeunload', flushStudyTime)
}

const attachFullscreenEvent = () => {
	if (document.fullscreenElement) {
		zenModeEnabled.value = true
		allowDiscussions.value = false
	} else {
		zenModeEnabled.value = false
		if (!hasQuiz.value) {
			allowDiscussions.value = true
		}
	}
}

onBeforeUnmount(() => {
	document.removeEventListener('fullscreenchange', attachFullscreenEvent)
	sidebarStore.isSidebarCollapsed = false
	trackVideoWatchDuration()
})

const lesson = createResource({
	url: 'lms.lms.utils.get_lesson',
	makeParams(values) {
		return {
			course: props.courseName,
			chapter: values ? values.chapter : props.chapterNumber,
			lesson: values ? values.lesson : props.lessonNumber,
		}
	},
	auto: true,
})

const setupLesson = (data) => {
	if (Object.keys(data).length === 0) {
		router.push({
			name: 'CourseDetail',
			params: { courseName: props.courseName },
		})
		return
	}
	if (data.is_scorm_package) {
		router.push({
			name: 'SCORMChapter',
			params: {
				courseName: props.courseName,
				chapterName: data.chapter_name,
			},
		})
	}
	lessonProgress.value = data.membership?.progress
	if (data.content) editor.value = renderEditor('editor', data.content)
	if (
		data.instructor_content &&
		JSON.parse(data.instructor_content)?.blocks?.length > 1
	)
		instructorEditor.value = renderEditor(
			'instructor-content',
			data.instructor_content
		)
	editor.value?.isReady.then(() => {
		checkIfDiscussionsAllowed()
	})
	checkQuiz()

	// By default this is silent — switching tabs while reading/watching a
	// lesson is normal (e.g. listening while multitasking). It's only used
	// server-side to exclude backgrounded time from min_reading_time (see
	// has_met_reading_time), not to warn the student. Instructors can opt a
	// course into the same visible warning banner + exam guards used during
	// quizzes via Course.enable_integrity_warnings.
	visibilityLog.stop()
	examGuards.stop()
	violationCount.value = 0

	if (data.name) {
		const onLog = data.enable_integrity_warnings
			? (count) => {
					violationCount.value = count || 0
				}
			: undefined

		visibilityLog = useVisibilityLog({
			referenceDoctype: 'Course Lesson',
			referenceName: data.name,
			onLog,
		})
		visibilityLog.start()

		if (data.enable_integrity_warnings) {
			examGuards = useExamGuards({
				referenceDoctype: 'Course Lesson',
				referenceName: data.name,
				onLog,
			})
			examGuards.start(lessonContainer.value)
		}
	}
}

const checkQuiz = () => {
	if (!editor.value && lesson.body) {
		const quizRegex = /\{\{ Quiz\(".*"\) \}\}/
		hasQuiz.value = quizRegex.test(lesson.body)
		if (!hasQuiz.value && !zenModeEnabled) {
			allowDiscussions.value = true
		} else {
			allowDiscussions.value = false
		}
	}
}

const renderEditor = (holder, content) => {
	if (document.getElementById(holder))
		document.getElementById(holder).innerHTML = ''
	return new EditorJS({
		holder: holder,
		tools: getEditorTools(),
		data: JSON.parse(content),
		readOnly: true,
		defaultBlock: 'embed',
	})
}

const markProgress = () => {
	if (user.data && lesson.data && !lesson.data.progress) {
		progress.submit()
	}
}

const markLessonCompleteManually = () => {
	clearInterval(timerInterval)
	readingTimeMet.value = true
	progress.submit(
		{},
		{
			async onSuccess() {
				await lesson.reload({
					chapter: props.chapterNumber,
					lesson: props.lessonNumber,
				})
				if (lesson.data?.progress) {
					toast.success(__('Lesson marked as complete'))
				} else {
					toast.info(
						__(
							'Please finish the quiz, video or assignment above before this lesson can be marked complete'
						)
					)
				}
			},
		}
	)
}

const progress = createResource({
	url: 'lms.lms.doctype.course_lesson.course_lesson.save_progress',
	makeParams() {
		return {
			lesson: lesson.data.name,
			course: props.courseName,
		}
	},
	onSuccess(data) {
		lessonProgress.value = data
	},
})

const notes = createListResource({
	doctype: 'LMS Lesson Note',
	filters: {
		lesson: lesson.data?.name,
		member: user.data?.name,
	},
	fields: ['name', 'color', 'highlighted_text', 'note'],
	cache: ['notes', lesson.data?.name, user.data?.name],
	onSuccess(data) {
		data.forEach((note) => {
			setTimeout(() => {
				highlightText(note)
			}, 500)
		})
	},
})

const breadcrumbs = computed(() => {
	let items = [{ label: 'Courses', route: { name: 'Courses' } }]
	items.push({
		label: lesson?.data?.course_title,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	})
	items.push({
		label: lesson?.data?.title,
		route: {
			name: 'Lesson',
			params: {
				courseName: props.courseName,
				chapterNumber: props.chapterNumber,
				lessonNumber: props.lessonNumber,
			},
		},
	})
	return items
})

const switchLesson = (direction) => {
	trackVideoWatchDuration()
	let lessonIndex =
		direction === 'prev'
			? lesson.data.prev.split('.')
			: lesson.data.next.split('.')

	router.push({
		name: 'Lesson',
		params: {
			courseName: props.courseName,
			chapterNumber: lessonIndex[0],
			lessonNumber: lessonIndex[1],
		},
	})
}

watch(
	[() => route.params.chapterNumber, () => route.params.lessonNumber],
	async (
		[newChapterNumber, newLessonNumber],
		[oldChapterNumber, oldLessonNumber]
	) => {
		if (newChapterNumber || newLessonNumber) {
			plyrSources.value = []
			await nextTick()
			resetLessonState(newChapterNumber, newLessonNumber)
			startTimer()
			updateNotes()
			checkIfDiscussionsAllowed()
			checkQuiz()
		}
	}
)

const resetLessonState = (newChapterNumber, newLessonNumber) => {
	editor.value = null
	instructorEditor.value = null
	allowDiscussions.value = false
	lesson.submit({
		chapter: newChapterNumber,
		lesson: newLessonNumber,
	})
	clearInterval(timerInterval)
	timer.value = 0
	readingTimeElapsed.value = 0
	readingTimeMet.value = false
}

const trackVideoWatchDuration = () => {
	if (!lesson.data.membership) return
	let videoDetails = getVideoDetails()
	videoDetails = videoDetails.concat(getPlyrSourceDetails())
	call('lms.lms.api.track_video_watch_duration', {
		lesson: lesson.data.name,
		videos: videoDetails,
	})
}

const getVideoDetails = () => {
	let details = []
	const videos = document.querySelectorAll('video')
	if (videos.length > 0) {
		videos.forEach((video) => {
			if (video.duration > 0) {
				const pct = (video.currentTime / video.duration) * 100
				if (pct >= threshold.value) markProgress()
			} else if (video.currentTime == video.duration) {
				markProgress()
			}
			details.push({
				source: video.src,
				watch_time: video.currentTime,
				duration: video.duration || 0,
			})
		})
	}
	return details
}

const getPlyrSourceDetails = () => {
	let details = []
	plyrSources.value.forEach((source) => {
		if (source.duration > 0) {
			const pct = (source.currentTime / source.duration) * 100
			if (pct >= threshold.value) markProgress()
		} else if (source.currentTime == source.duration) {
			markProgress()
		}
		let src = cleanYouTubeUrl(source.source)
		details.push({
			source: src,
			watch_time: source.currentTime,
			duration: source.duration || 0,
		})
	})
	return details
}

const attachVideoProgressListeners = () => {
	plyrSources.value.forEach((plyrSource) => {
		plyrSource.on('timeupdate', () => {
			if (plyrSource.duration > 0) {
				const pct = (plyrSource.currentTime / plyrSource.duration) * 100
				if (pct >= threshold.value) {
					trackVideoWatchDuration()
					markProgress()
				}
			}
		})
		plyrSource.on('pause', () => {
			trackVideoWatchDuration()
		})
		plyrSource.on('ended', () => {
			trackVideoWatchDuration()
			markProgress()
		})
	})

	const videos = document.querySelectorAll('video')
	videos.forEach((vid) => {
		vid.addEventListener('timeupdate', () => {
			if (vid.duration > 0) {
				const pct = (vid.currentTime / vid.duration) * 100
				if (pct >= threshold.value) {
					trackVideoWatchDuration()
					markProgress()
				}
			}
		})
		vid.addEventListener('pause', () => {
			trackVideoWatchDuration()
		})
		vid.addEventListener('ended', () => {
			trackVideoWatchDuration()
			markProgress()
		})
	})
}

const cleanYouTubeUrl = (url) => {
	if (!url) return url
	const urlObj = new URL(url)
	urlObj.searchParams.delete('t')
	return urlObj.toString()
}

watch(
	() => lesson.data,
	async (data) => {
		setupLesson(data)
		getPlyrSource()
		updateNotes()
		if (data.icon == 'icon-youtube') clearInterval(timerInterval)
	}
)

const getPlyrSource = async () => {
	await nextTick()
	if (plyrSources.value.length == 0) {
		plyrSources.value = await enablePlyr()
	}
	updateVideoWatchDuration()
	attachVideoProgressListeners()
}

const updateVideoWatchDuration = () => {
	if (lesson.data.videos && lesson.data.videos.length > 0) {
		lesson.data.videos.forEach((video) => {
			if (video.source.includes('youtube') || video.source.includes('vimeo')) {
				updatePlyrVideoTime(video)
			} else {
				updateVideoTime(video)
			}
		})
	}
}

const updatePlyrVideoTime = (video) => {
	plyrSources.value.forEach((plyrSource) => {
		let lastWatchedTime = 0
		let isSeeking = false

		plyrSource.on('ready', () => {
			if (plyrSource.source === video.source) {
				plyrSource.embed.seekTo(video.watch_time, true)
				plyrSource.play()
				plyrSource.pause()
			}
		})
	})
}

const updateVideoTime = (video) => {
	const videos = document.querySelectorAll('video')
	if (videos.length > 0) {
		videos.forEach((vid) => {
			if (vid.src === video.source) {
				let watch_time = video.watch_time < vid.duration ? video.watch_time : 0
				if (vid.readyState >= 1) {
					vid.currentTime = watch_time
				} else {
					vid.addEventListener('loadedmetadata', () => {
						vid.currentTime = watch_time
					})
				}
			}
		})
	}
}

const startTimer = () => {
	readingTimeElapsed.value = 0
	clearInterval(timerInterval)

	const minTime = lesson.data?.min_reading_time || 0
	if (minTime <= 0) {
		readingTimeMet.value = true
		markProgress()
		return
	}

	readingTimeMet.value = false
	timerInterval = setInterval(() => {
		timer.value++
		readingTimeElapsed.value = Math.min(timer.value, minTime)
		if (timer.value >= minTime) {
			readingTimeMet.value = true
			clearInterval(timerInterval)
			markProgress()
		}
	}, 1000)
}

onBeforeUnmount(() => {
	clearInterval(timerInterval)
	stopStudyTimeTracking()
	visibilityLog.stop()
	examGuards.stop()
})

const checkIfDiscussionsAllowed = () => {
	hasQuiz.value = false
	JSON.parse(lesson.data?.content)?.blocks?.forEach((block) => {
		if (block.type === 'quiz') {
			hasQuiz.value = true
		}
	})

	if (
		!hasQuiz.value &&
		!zenModeEnabled.value &&
		(lesson.data?.membership ||
			user.data?.is_moderator ||
			user.data?.is_instructor)
	) {
		allowDiscussions.value = true
	} else {
		allowDiscussions.value = false
	}
}

const allowEdit = () => {
	if (window.read_only_mode) return false
	if (user.data?.is_moderator) return true
	if (lesson.data?.instructors?.includes(user.data?.name)) return true
	return false
}

const allowInstructorContent = () => {
	if (user.data?.is_moderator) return true
	if (lesson.data?.instructors?.includes(user.data?.name)) return true
	return false
}

const enrollment = createResource({
	url: 'frappe.client.insert',
	makeParams() {
		return {
			doc: {
				doctype: 'LMS Enrollment',
				course: props.courseName,
				member: user.data?.name,
			},
		}
	},
})

const enrollStudent = () => {
	enrollment.submit(
		{},
		{
			onSuccess() {
				window.location.reload()
			},
		}
	)
}

const toggleInlineMenu = async () => {
	showInlineMenu.value = false
	await nextTick()
	let selection = window.getSelection()
	if (selection.toString()) {
		showInlineMenu.value = true
	}
}

const canSeeStats = () => {
	if (user.data?.is_moderator || user.data?.is_instructor) return true
	return false
}

const showVideoStats = () => {
	showStatsDialog.value = true
}

const canGoZen = () => {
	if (
		user.data?.is_moderator ||
		user.data?.is_instructor
	)
		return true
	if (lesson.data?.membership) return true
	return false
}

const goFullScreen = () => {
	if (lessonContainer.value.requestFullscreen) {
		lessonContainer.value.requestFullscreen()
	} else if (lessonContainer.value.mozRequestFullScreen) {
		lessonContainer.value.mozRequestFullScreen()
	} else if (lessonContainer.value.webkitRequestFullscreen) {
		lessonContainer.value.webkitRequestFullscreen()
	} else if (lessonContainer.value.msRequestFullscreen) {
		lessonContainer.value.msRequestFullscreen()
	}
}

const showDiscussionsInZenMode = () => {
	if (allowDiscussions.value) {
		allowDiscussions.value = false
	} else {
		allowDiscussions.value = true
		currentTab.value = 'Community'
		scrollDiscussionsIntoView()
	}
}

const scrollDiscussionsIntoView = () => {
	nextTick(() => {
		discussionsContainer.value?.scrollIntoView({
			behavior: 'smooth',
			block: 'center',
			inline: 'nearest',
		})
	})
}

const updateNotes = () => {
	notes.update({
		filters: {
			lesson: lesson.data?.name,
			member: user.data?.name,
		},
	})
	notes.reload()
}

watch(allowDiscussions, () => {
	if (allowDiscussions.value) {
		tabs.value = [
			{
				label: __('Notes'),
				value: 'Notes',
			},
			{
				label: __('Community'),
				value: 'Community',
			},
		]
	} else {
		tabs.value = [
			{
				label: __('Notes'),
				value: 'Notes',
			},
		]
	}
})

const redirectToLogin = () => {
	window.location.href = `/login?redirect-to=/lms/courses/${props.courseName}`
}

usePageMeta(() => {
	return {
		title: lesson?.data?.title,
		icon: brand.favicon,
	}
})
</script>
<style>
.avatar-group {
	display: inline-flex;
	align-items: center;
}

.avatar-group .avatar {
	transition: margin 0.1s ease-in-out;
}

.lesson-content p {
	margin-bottom: 1rem;
	line-height: 1.7;
}

.lesson-content li {
	line-height: 1.7;
}

.lesson-content ol {
	list-style: auto;
	margin: revert;
	padding: 1rem;
}

.lesson-content ul {
	list-style: auto;
	padding: 1rem;
	margin: revert;
}

.lesson-content img {
	border: 1px solid theme('colors.gray.200');
	border-radius: 0.5rem;
}

.lesson-content code {
	display: block;
	overflow-x: auto;
	padding: 1rem 1.25rem;
	background: #011627;
	color: #d6deeb;
	border-radius: 0.5rem;
	margin: 1rem 0;
}

.lesson-content a {
	color: theme('colors.gray.900');
	text-decoration: underline;
	font-weight: 500;
}

.embed-tool__caption,
.cdx-simple-image__caption {
	display: none;
}

.ce-block__content {
	max-width: unset;
}

.codex-editor__redactor {
	padding-bottom: 0px !important;
}

.codeBoxHolder {
	display: flex;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
}

.codeBoxTextArea {
	width: 100%;
	min-height: 30px;
	padding: 10px;
	border-radius: 2px 2px 2px 0;
	border: none !important;
	outline: none !important;
	font: 14px monospace;
}

.codeBoxSelectDiv {
	display: flex;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
	position: relative;
}

.codeBoxSelectInput {
	border-radius: 0 0 20px 2px;
	padding: 2px 26px;
	padding-top: 0;
	padding-right: 0;
	text-align: left;
	cursor: pointer;
	border: none !important;
	outline: none !important;
}

.codeBoxSelectDropIcon {
	position: absolute !important;
	left: 10px !important;
	bottom: 0 !important;
	width: unset !important;
	height: unset !important;
	font-size: 16px !important;
}

.codeBoxSelectPreview {
	display: none;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
	border-radius: 2px;
	box-shadow: 0 3px 15px -3px rgba(13, 20, 33, 0.13);
	position: absolute;
	top: 100%;
	margin: 5px 0;
	max-height: 30vh;
	overflow-x: hidden;
	overflow-y: auto;
	z-index: 10000;
}

.codeBoxSelectItem {
	width: 100%;
	padding: 5px 20px;
	margin: 0;
	cursor: pointer;
}

.codeBoxSelectItem:hover {
	opacity: 0.7;
}

.codeBoxSelectedItem {
	background-color: lightblue !important;
}

.codeBoxShow {
	display: flex !important;
}

.dark {
	color: #abb2bf;
	background-color: #282c34;
}

.light {
	color: #383a42;
	background-color: #fafafa;
}

.codeBoxTextArea {
	line-height: 1.7;
}

.tc-table {
	border-left: 1px solid #e8e8eb;
}

.plyr__volume input[type='range'] {
	display: none;
}

.plyr__control--overlaid {
	background: radial-gradient(
		circle,
		rgba(0, 0, 0, 0.4) 0%,
		rgba(0, 0, 0, 0.5) 50%
	);
}

.plyr__control:hover {
	background: none;
}

.plyr--video {
	border: 1px solid theme('colors.gray.200');
	border-radius: 8px;
}

:root {
	--plyr-range-fill-background: white;
	--plyr-video-control-background-hover: transparent;
}
</style>
