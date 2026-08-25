<template>
	<!-- <header
		class="sticky flex items-center justify-between top-0 z-10 border-b border-outline-gray-2 bg-surface-white/90 backdrop-blur-md px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="[{ label: __('Home'), route: { name: 'Home' } }]" />
	</header> -->
	<div class="w-full px-5 pt-5 pb-10">
		<div class="space-y-2">
			<div class="flex items-center justify-between">
				<div class="lms-home__serif text-2xl text-ink-gray-9">
					{{ __('home.common.greeting') }}, {{ user.data?.full_name }} 👋
				</div>
				<div>
					<TabButtons v-if="isAdmin" v-model="currentTab" :buttons="tabs" />
					<div
						v-else
						@click="showStreakModal = true"
						class="bg-surface-amber-2 px-2 py-1 rounded-md cursor-pointer"
					>
						<span> 🔥 </span>
						<span class="text-ink-gray-9">
							{{ streakInfo.data?.current_streak }}
						</span>
					</div>
				</div>
			</div>

			<div class="text-lg text-ink-gray-6 leading-6">
				{{ subtitle }}
			</div>
		</div>

		<div
			v-if="homeSettings.data?.announcement_content"
			class="lms-home__announcement mt-6 rounded-md border-l-4 bg-surface-gray-2 px-4 py-3"
		>
			<div
				class="lms-home__mono mb-1 text-[10px] uppercase tracking-[0.14em] text-ink-gray-6"
			>
				{{ __('home.announcement.label') }}
			</div>
			<div class="whitespace-pre-wrap text-sm leading-6 text-ink-gray-8">
				{{ homeSettings.data.announcement_content }}
			</div>
		</div>

		<AdminHome
			v-if="isAdmin && currentTab === 'instructor'"
			:liveClasses="adminLiveClasses"
		/>
		<StudentHome v-else :myLiveClasses="myLiveClasses" />

		<Leaderboard />

		<div
			v-if="homeSettings.data?.guidelines_url"
			class="mt-10 flex items-center justify-between gap-4 rounded-md border border-outline-gray-2 p-4"
		>
			<div class="flex items-center gap-3">
				<div
					class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-gray-2 text-ink-gray-7"
				>
					<BookMarked class="h-4 w-4 stroke-1.5" />
				</div>
				<div>
					<div class="lms-home__serif text-base text-ink-gray-9">
						{{ __('home.guidelines.title') }}
					</div>
					<div class="text-sm text-ink-gray-6">
						{{ __('home.guidelines.description') }}
					</div>
				</div>
			</div>
			<a :href="homeSettings.data.guidelines_url" target="_blank" rel="noopener">
				<Button variant="subtle">
					{{ homeSettings.data.guidelines_label || __('home.guidelines.linkLabel') }}
				</Button>
			</a>
		</div>

		<div
			v-if="
				homeSettings.data?.it_department_contact ||
				homeSettings.data?.training_department_contact
			"
			class="mt-10 grid grid-cols-1 gap-5 border-t border-outline-gray-2 pt-6 sm:grid-cols-2"
		>
			<div v-if="homeSettings.data?.it_department_contact">
				<div
					class="lms-home__mono mb-1 text-[10px] uppercase tracking-[0.14em] text-ink-gray-5"
				>
					{{ __('home.footer.itDepartment') }}
				</div>
				<div class="whitespace-pre-wrap text-sm leading-6 text-ink-gray-7">
					{{ homeSettings.data.it_department_contact }}
				</div>
			</div>
			<div v-if="homeSettings.data?.training_department_contact">
				<div
					class="lms-home__mono mb-1 text-[10px] uppercase tracking-[0.14em] text-ink-gray-5"
				>
					{{ __('home.footer.trainingDepartment') }}
				</div>
				<div class="whitespace-pre-wrap text-sm leading-6 text-ink-gray-7">
					{{ homeSettings.data.training_department_contact }}
				</div>
			</div>
		</div>
	</div>
	<Streak v-model="showStreakModal" :streakInfo="streakInfo" />
</template>
<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { Button, createResource, TabButtons, usePageMeta } from 'frappe-ui'
import { BookMarked } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import StudentHome from '@/pages/Home/StudentHome.vue'
import AdminHome from '@/pages/Home/AdminHome.vue'
import Streak from '@/pages/Home/Streak.vue'
import Leaderboard from '@/components/Leaderboard.vue'

const user = inject<any>('$user')
const { brand } = sessionStore()
const currentTab = ref<'student' | 'instructor'>('instructor')
const showStreakModal = ref(false)

const isAdmin = computed(() => {
	return user.data?.is_moderator || user.data?.is_instructor
})

const myLiveClasses = createResource({
	url: 'lms.lms.utils.get_my_live_classes',
	auto: !isAdmin.value ? true : false,
})

const adminLiveClasses = createResource({
	url: 'lms.lms.utils.get_admin_live_classes',
	auto: isAdmin.value ? true : false,
})

const streakInfo = createResource({
	url: 'lms.lms.utils.get_streak_info',
	auto: true,
})

const homeSettings = createResource({
	url: 'lms.lms.api.get_home_page_settings',
	auto: true,
})

const subtitle = computed(() => {
	if (isAdmin.value) {
		let liveClassSuffix =
				adminLiveClasses.data?.length > 1
					? __('home.common.liveClassesPlural')
					: __('home.common.liveClassesSingular')
		if (adminLiveClasses.data?.length > 0) {
				return __('home.common.upcomingClassesMessage').format(
				adminLiveClasses.data.length,
				liveClassSuffix
			)
		}
			return __('home.common.manageCoursesAndBatches')
	} else {
		let liveClassSuffix =
				myLiveClasses.data?.length > 1
					? __('home.common.liveClassesPlural')
					: __('home.common.liveClassesSingular')
		if (myLiveClasses.data?.length > 0) {
				return __('home.common.upcomingClassesMessage').format(
				myLiveClasses.data.length,
				liveClassSuffix
			)
		}
			return __('home.common.resumeWhereYouLeftOff')
	}
})

const tabs = [
		{ label: __('home.common.student'), value: 'student' },
		{ label: __('home.common.instructor'), value: 'instructor' },
]

usePageMeta(() => {
	return {
			title: __('home.common.title'),
		icon: brand.favicon,
	}
})
</script>
<style scoped>
.lms-home__serif {
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

.lms-home__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}

.lms-home__announcement {
	border-left-color: #16222e;
}
</style>
