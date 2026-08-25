<template>
	<div v-if="course.data">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
		</header>
		<div class="m-5">
			<div class="flex justify-between w-full space-x-5">
				<div class="md:w-2/3">
					<div class="flex items-start justify-between gap-3">
						<div class="lms-course-detail__serif text-3xl leading-tight text-ink-gray-9">
							{{ course.data.title }}
						</div>
						<button
							v-if="user.data"
							type="button"
							:title="
								isBookmarked
									? __('courses.card.removeBookmark')
									: __('courses.card.addBookmark')
							"
							class="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-outline-gray-2 text-ink-gray-8 transition-colors hover:bg-surface-gray-2"
							@click="onToggleBookmark"
						>
							<BookmarkCheck v-if="isBookmarked" class="size-4 stroke-2" />
							<Bookmark v-else class="size-4 stroke-2" />
						</button>
					</div>
					<div class="my-3 leading-6 text-ink-gray-7">
						{{ course.data.short_introduction }}
					</div>
					<div
						class="lms-course-detail__mono flex flex-wrap items-center gap-4 border-y border-outline-gray-2 py-2 text-[11px] text-ink-gray-6"
					>
						<Tooltip
							v-if="course.data.duration_display"
							:text="__('courses.card.duration')"
						>
							<span class="flex items-center gap-1">
								<Clock class="h-3.5 w-3.5 stroke-1.5" />
								{{ course.data.duration_display }}
							</span>
						</Tooltip>
						<Tooltip
							v-if="parseInt(course.data.rating) > 0"
							:text="__('courses.detail.averageRating')"
						>
							<span class="flex items-center gap-1">
								<Star class="h-3.5 w-3.5 fill-yellow-500 text-transparent" />
								{{ course.data.rating }}
							</span>
						</Tooltip>
						<Tooltip
							v-if="course.data.enrollment_count"
							:text="__('courses.detail.enrolledStudents')"
						>
							<span class="flex items-center gap-1">
								<Users class="h-3.5 w-3.5 stroke-1.5" />
								{{ course.data.enrollment_count_formatted }}
							</span>
						</Tooltip>
						<div class="flex items-center">
							<span
								class="h-6 mr-1"
								:class="{
									'avatar-group overlap': course.data.instructors.length > 1,
								}"
							>
								<UserAvatar
									v-for="instructor in course.data.instructors"
									:user="instructor"
								/>
							</span>
							<CourseInstructors :instructors="course.data.instructors" />
						</div>
					</div>
					<div v-if="course.data.tags" class="flex my-4 w-fit">
						<Badge
							theme="gray"
							size="lg"
							class="mr-2 text-ink-gray-9"
							v-for="tag in course.data.tags.split(', ')"
						>
							{{ tag }}
						</Badge>
					</div>
					<div class="md:hidden my-4">
						<CourseCardOverlay :course="course" />
					</div>
					<div
						v-html="course.data.description"
						class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal mt-10"
					></div>
					<div class="mt-10">
						<CourseOutline
						:title="__('courses.detail.courseOutline')"
							:courseName="course.data.name"
							:showOutline="true"
							:getProgress="course.data.membership ? true : false"
						/>
					</div>
					<div class="mt-10">
						<CourseResources
							:courseName="course.data.name"
							:canManage="isInstructor() || user.data?.is_moderator"
						/>
					</div>
					<CourseReviews
						:courseName="course.data.name"
						:avg_rating="course.data.rating"
						:membership="course.data.membership"
					/>
				</div>
				<div class="hidden md:block">
					<CourseCardOverlay :course="course" />
				</div>
			</div>
			<RelatedCourses :courseName="course.data.name" />
		</div>
	</div>
	<DetailSkeleton v-else />
</template>
<script setup>
import {
	call,
	createResource,
	Breadcrumbs,
	Badge,
	toast,
	Tooltip,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, ref, watch } from 'vue'
import { Bookmark, BookmarkCheck, Clock, Users, Star } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import { useRouter } from 'vue-router'
import CourseCardOverlay from '@/components/CourseCardOverlay.vue'
import CourseOutline from '@/components/CourseOutline.vue'
import CourseResources from '@/components/CourseResources.vue'
import CourseReviews from '@/components/CourseReviews.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import RelatedCourses from '@/components/RelatedCourses.vue'
import DetailSkeleton from '@/components/DetailSkeleton.vue'

const { brand } = sessionStore()
const router = useRouter()
const user = inject('$user')

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
})

const course = createResource({
	url: 'lms.lms.utils.get_course_details',
	cache: ['course', props.courseName],
	makeParams() {
		return {
			course: props.courseName,
		}
	},
	auto: true,
})

watch(
	() => props.courseName,
	() => {
		course.reload()
	}
)

watch(course, () => {
	if (
		!isInstructor() &&
		!user.data?.is_moderator &&
		!course.data?.published &&
		!course.data?.upcoming
	) {
		router.push({
			name: 'Courses',
		})
	}
	isBookmarked.value = !!course.data?.is_bookmarked
})

const isBookmarked = ref(false)

const onToggleBookmark = () => {
	isBookmarked.value = !isBookmarked.value
	call('lms.lms.doctype.lms_course_bookmark.lms_course_bookmark.toggle_bookmark', {
		course: course.data.name,
	}).catch(() => {
		isBookmarked.value = !isBookmarked.value
		toast.error(__('courses.card.bookmarkFailed'))
	})
}

const isInstructor = () => {
	let user_is_instructor = false
	course.data?.instructors.forEach((instructor) => {
		if (!user_is_instructor && instructor.name == user.data?.name) {
			user_is_instructor = true
		}
	})
	return user_is_instructor
}

const breadcrumbs = computed(() => {
	let items = [{ label: __('courses.list.courses'), route: { name: 'Courses' } }]
	items.push({
		label: course?.data?.title,
		route: { name: 'CourseDetail', params: { courseName: course?.data?.name } },
	})
	return items
})

usePageMeta(() => {
	return {
		title: course?.data?.title,
		icon: brand.favicon,
	}
})
</script>
<style scoped>
.lms-course-detail__serif {
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

.lms-course-detail__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
	font-variant-numeric: tabular-nums;
}
</style>
<style>
.avatar-group {
	display: inline-flex;
	align-items: center;
}

.avatar-group .avatar {
	transition: margin 0.1s ease-in-out;
}
</style>
