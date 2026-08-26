<template>
	<div
		v-if="course.title"
		class="group flex h-full flex-col overflow-hidden rounded-md border border-outline-gray-2 bg-surface-white transition-shadow duration-300 hover:shadow-md motion-reduce:transition-none"
		style="min-height: 350px"
	>
		<!-- Register strip: the course's real category (LMS Category) as a ledger
		heading, plus a brass mark when this course carries a certificate — the
		one accent color reused for anything "officially recognised" on the card. -->
		<div
			v-if="course.category || isCertified"
			class="flex items-center justify-between border-b border-outline-gray-2 px-3 py-1.5"
		>
			<span class="lms-course-card__mono text-[10px] uppercase tracking-[0.12em] text-ink-gray-6">
				{{ course.category }}
			</span>
			<GraduationCap
				v-if="isCertified"
				class="lms-course-card__brass h-3 w-3 shrink-0 stroke-2"
			/>
		</div>

		<div class="relative h-[160px] w-full overflow-hidden">
			<div
				class="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-500 ease-out group-hover:scale-[1.05] motion-reduce:transition-none"
				:style="heroStyle"
			></div>

			<div
				v-if="!course.image"
				class="relative flex h-full items-center justify-center px-6 text-center text-white"
			>
				<span class="lms-course-card__serif leading-tight" :class="titleSizeOnHero">
					{{ course.title }}
				</span>
			</div>

			<div
				v-if="course.featured"
				:title="__('courses.card.featured')"
				class="lms-course-card__seal absolute right-2.5 top-2.5 flex h-7 w-7 items-center justify-center rounded-full shadow-sm"
			>
				<Award class="size-3.5 stroke-2" />
			</div>

			<button
				v-if="user"
				type="button"
				:title="
					isBookmarked
						? __('courses.card.removeBookmark')
						: __('courses.card.addBookmark')
				"
				class="absolute left-2.5 top-2.5 flex h-7 w-7 items-center justify-center rounded-full bg-surface-white text-ink-gray-8 shadow-sm transition-colors hover:bg-surface-gray-2"
				@click.stop.prevent="onToggleBookmark"
			>
				<BookmarkCheck v-if="isBookmarked" class="size-3.5 stroke-2" />
				<Bookmark v-else class="size-3.5 stroke-2" />
			</button>
		</div>

		<div class="flex flex-1 flex-col p-4">
			<div
				v-if="course.image"
				class="lms-course-card__serif leading-6"
				:class="titleSizeInBody"
			>
				{{ course.title }}
			</div>

			<div class="short-introduction text-sm text-ink-gray-6">
				{{ course.short_introduction }}
			</div>

			<div
				v-if="course.duration_display || course.lessons || course.enrollments || course.rating"
				class="lms-course-card__mono mb-1 mt-3 flex items-center gap-4 border-y border-outline-gray-1 py-2 text-[11px] text-ink-gray-6"
			>
				<Tooltip v-if="course.duration_display" :text="__('courses.card.duration')">
					<span class="flex items-center gap-1">
						<Clock class="h-3.5 w-3.5 stroke-1.5" />
						{{ course.duration_display }}
					</span>
				</Tooltip>

				<Tooltip v-if="course.lessons" :text="__('courses.card.lessons')">
					<span class="flex items-center gap-1">
						<BookOpen class="h-3.5 w-3.5 stroke-1.5" />
						{{ course.lessons }}
					</span>
				</Tooltip>

				<Tooltip
					v-if="course.enrollments"
					:text="__('courses.card.enrolledStudents')"
				>
					<span class="flex items-center gap-1">
						<Users class="h-3.5 w-3.5 stroke-1.5" />
						{{ formatAmount(course.enrollments) }}
					</span>
				</Tooltip>

				<Tooltip v-if="course.rating" :text="__('courses.card.averageRating')">
					<span class="flex items-center gap-1">
						<Star class="h-3.5 w-3.5 stroke-1.5" />
						{{ course.rating }}
					</span>
				</Tooltip>
			</div>

			<ProgressBar
				v-if="user && course.membership"
				:progress="course.membership.progress"
				size="md"
				completionColor
			/>

			<div
				v-if="user && course.membership"
				class="lms-course-card__mono mb-4 mt-2 text-[11px] text-ink-gray-6"
			>
				{{ Math.ceil(course.membership.progress) }}%
				{{ __('courses.card.completed') }}
			</div>

			<div class="mt-auto flex items-center justify-between pt-3">
				<div class="flex avatar-group overlap">
					<div
						class="h-6 mr-1"
						:class="{ 'avatar-group overlap': course.instructors.length > 1 }"
					>
						<UserAvatar
							v-for="instructor in course.instructors"
							:user="instructor"
						/>
					</div>
					<CourseInstructors :instructors="course.instructors" />
				</div>

				<div
					v-if="course.paid_course"
					class="lms-course-card__mono text-sm font-medium text-ink-gray-8"
				>
					{{ course.price }}
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import {
	Award,
	Bookmark,
	BookmarkCheck,
	BookOpen,
	Clock,
	GraduationCap,
	Star,
	Users,
} from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { sessionStore } from '@/stores/session'
import { call, Tooltip, toast } from 'frappe-ui'
import { theme } from '@/utils/theme'
import { formatAmount } from '@/utils'
import CourseInstructors from '@/components/CourseInstructors.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import ProgressBar from '@/components/ProgressBar.vue'

const { user } = sessionStore()

const props = defineProps({
	course: {
		type: Object,
		default: null,
	},
})

const isCertified = computed(
	() => !!(props.course.paid_certificate || props.course.enable_certification),
)

const isBookmarked = ref(!!props.course?.is_bookmarked)

// The v-for in Courses.vue has no :key, so Vue may reuse this component
// instance for a different course when the list reloads (e.g. switching
// tabs) — re-sync local state whenever the underlying course actually
// changes, rather than only ever reading the prop once at setup.
watch(
	() => props.course?.name,
	() => {
		isBookmarked.value = !!props.course?.is_bookmarked
	},
)

const onToggleBookmark = () => {
	isBookmarked.value = !isBookmarked.value
	call('lms.lms.doctype.lms_course_bookmark.lms_course_bookmark.toggle_bookmark', {
		course: props.course.name,
	}).catch(() => {
		isBookmarked.value = !isBookmarked.value
		toast.error(__('courses.card.bookmarkFailed'))
	})
}

const titleSizeOnHero = computed(() => {
	if (props.course.title.length > 32) return 'text-lg'
	if (props.course.title.length > 20) return 'text-xl'
	return 'text-2xl'
})

const titleSizeInBody = computed(() =>
	props.course.title.length > 32 ? 'text-lg' : 'text-xl',
)

const getGradientColor = () => {
	let color = props.course.card_gradient?.toLowerCase() || 'blue'
	let colorMap = theme.backgroundColor[color]
	return `radial-gradient(ellipse 140% 100% at 100% 0%, ${colorMap[300]} 0%, ${colorMap[600]} 45%, #16222e 100%)`
}

const heroStyle = computed(() => {
	if (props.course.image) {
		return { backgroundImage: `url('${encodeURI(props.course.image)}')` }
	}
	return { backgroundImage: getGradientColor() }
})
</script>
<style scoped>
.lms-course-card__serif {
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

.lms-course-card__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
	font-variant-numeric: tabular-nums;
}

.lms-course-card__seal {
	background: #efe8d8;
	color: #8a6a22;
}

.lms-course-card__brass {
	color: #9c7a3c;
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

.avatar-group.overlap .avatar + .avatar {
	margin-left: calc(-8px);
}

.short-introduction {
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	text-overflow: ellipsis;
	width: 100%;
	overflow: hidden;
	margin: 0.25rem 0 1.25rem;
	line-height: 1.5;
}
</style>
