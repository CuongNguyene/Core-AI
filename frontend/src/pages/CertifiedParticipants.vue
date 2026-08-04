<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<router-link :to="{ name: 'Batches', query: { certification: true } }">
			<Button>
				<template #prefix>
					<GraduationCap class="h-4 w-4 stroke-1.5" />
				</template>
				{{ __('certification.getCertified') }}
			</Button>
		</router-link>
	</header>
	<div class="py-5 mx-5">
		<div class="flex flex-col md:flex-row justify-between mb-4">
			<div class="text-xl font-semibold text-ink-gray-7 mb-4 md:mb-0">
				{{ memberCount }} {{ __('certification.certifiedMembers') }}
			</div>
			<div class="grid grid-cols-2 gap-2">
				<FormControl
					v-model="nameFilter"
					:placeholder="__('certification.searchByName')"
					type="text"
					class="min-w-40 lg:min-w-0 lg:w-32 xl:w-40"
					@input="updateParticipants()"
				/>
				<div
					v-if="categories.data?.length"
					class="min-w-40 lg:min-w-0 lg:w-32 xl:w-40"
				>
					<Autocomplete
						:value="currentCategory"
						:options="categories.data"
						:placeholder="__('certification.category')"
						@change="(val) => { currentCategory = val?.value || ''; updateParticipants() }"
					/>
				</div>
			</div>
		</div>
		<div v-if="participants.data?.length" class="divide-y">
			<template v-for="participant in participants.data">
				<router-link
					:to="{
						name: 'ProfileCertificates',
						params: {
							username: participant.username,
						},
					}"
					class="flex sm:rounded px-3 py-2 sm:h-15 hover:bg-surface-gray-2"
				>
					<div class="flex items-center w-full space-x-3">
						<Avatar
							:image="participant.user_image"
							class="size-8 rounded-full object-contain"
							:label="participant.full_name"
							size="2xl"
						/>
						<div class="flex flex-col md:flex-row w-full">
							<div class="flex-1">
								<div class="text-base font-medium text-ink-gray-8">
									{{ participant.full_name }}
								</div>
								<div
									v-if="participant.headline"
									class="mt-1.5 text-base text-ink-gray-5"
								>
									{{ participant.headline }}
								</div>
							</div>
							<div
								class="flex items-center space-x-3 md:space-x-24 text-sm md:text-base mt-1.5"
							>
								<div class="text-ink-gray-5">
									{{ participant.certificate_count }}
									{{
										participant.certificate_count > 1
											? __('certification.certificates')
											: __('certification.certificate')
									}}
								</div>
								<span class="text-ink-gray-4 md:hidden">·</span>
								<div class="text-ink-gray-5">
									{{ dayjs(participant.issue_date).format('L') }}
								</div>
							</div>
						</div>
					</div>
				</router-link>
			</template>
		</div>
		<EmptyState v-else type="Certified Members" />
		<div
			v-if="!participants.list.loading && participants.hasNextPage"
			class="flex justify-center mt-5"
		>
			<Button @click="participants.next()">
				{{ __('certification.loadMore') }}
			</Button>
		</div>
	</div>
</template>
<script setup>
import {
	Avatar,
	Breadcrumbs,
	Button,
	call,
	createListResource,
	FormControl,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, onMounted, ref } from 'vue'
import { GraduationCap } from 'lucide-vue-next'
import { sessionStore } from '../stores/session'
import EmptyState from '@/components/EmptyState.vue'
import Autocomplete from '@/components/Controls/Autocomplete.vue'

const currentCategory = ref('')
const filters = ref({})
const nameFilter = ref('')
const { brand } = sessionStore()
const memberCount = ref(0)
const dayjs = inject('$dayjs')

onMounted(() => {
	getMemberCount()
	updateParticipants()
})

const participants = createListResource({
	doctype: 'LMS Certificate',
	url: 'lms.lms.api.get_certified_participants',
	start: 0,
	cache: ['certified_participants'],
	pageLength: 100,
})

const getMemberCount = () => {
	call('lms.lms.api.get_count_of_certified_members', {
		filters: filters.value,
	}).then((data) => {
		memberCount.value = data
	})
}

const categories = createListResource({
	doctype: 'LMS Certificate',
	url: 'lms.lms.api.get_certification_categories',
	cache: ['certification_categories'],
	auto: true,
	transform(data) {
		let options = data.map((category) => ({ label: category, value: category }))
		options.unshift({ label: __('certification.allCategories'), value: '' })
		return options
	},
})

const updateParticipants = () => {
	updateFilters()
	getMemberCount()
	participants.update({
		filters: filters.value,
	})
	participants.reload()
}

const updateFilters = () => {
	if (currentCategory.value) {
		filters.value.category = currentCategory.value
	} else {
		delete filters.value.category
	}

	if (nameFilter.value) {
		filters.value.member_name = ['like', `%${nameFilter.value}%`]
	} else {
		delete filters.value.member_name
	}
}

const breadcrumbs = computed(() => [
	{
		label: __('certification.certifiedMembersTitle'),
		route: { name: 'CertifiedParticipants' },
	},
])

usePageMeta(() => {
	return {
		title: __('certification.certifiedMembersTitle'),
		icon: brand.favicon,
	}
})
</script>
<style>
.headline {
	display: -webkit-box;
	-webkit-line-clamp: 1;
	-webkit-box-orient: vertical;
	text-overflow: ellipsis;
	width: 100%;
	overflow: hidden;
}
</style>
