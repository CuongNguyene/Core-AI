<template>
	<!-- <header
		class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="[{ label: __('Home'), route: { name: 'Home' } }]" />
	</header> -->
	<div class="w-full px-5 pt-5 pb-10">
		<div class="space-y-2">
			<div class="flex items-center justify-between">
				<div class="text-xl font-bold text-ink-gray-9">
					{{ __('Hey') }}, {{ user.data?.full_name }} 👋
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

		<AdminHome
			v-if="isAdmin && currentTab === 'instructor'"
			:liveClasses="adminLiveClasses"
		/>
		<StudentHome v-else :myLiveClasses="myLiveClasses" />
	</div>
	<Streak v-model="showStreakModal" :streakInfo="streakInfo" />
</template>
<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { createResource, TabButtons, usePageMeta } from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import StudentHome from '@/pages/Home/StudentHome.vue'
import AdminHome from '@/pages/Home/AdminHome.vue'
import Streak from '@/pages/Home/Streak.vue'

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

const subtitle = computed(() => {
	if (isAdmin.value) {
		let liveClassSuffix =
			adminLiveClasses.data?.length > 1 ? __('live classes') : __('live class')
		if (adminLiveClasses.data?.length > 0) {
			return __('You have {0} upcoming {1}.').format(
				adminLiveClasses.data.length,
				liveClassSuffix
			)
		}
		return __('Manage your courses and batches at a glance')
	} else {
		let liveClassSuffix =
			myLiveClasses.data?.length > 1 ? __('live classes') : __('live class')
		if (myLiveClasses.data?.length > 0) {
			return __('You have {0} upcoming {1}.').format(
				myLiveClasses.data.length,
				liveClassSuffix
			)
		}
		return __('Resume where you left off')
	}
})

const tabs = [
	{ label: __('Student'), value: 'student' },
	{ label: __('Instructor'), value: 'instructor' },
]

usePageMeta(() => {
	return {
		title: __('Home'),
		icon: brand.favicon,
	}
})
</script>
