<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<Button v-if="canCreateProgram()" @click="openForm('new')" variant="solid">
			<template #prefix>
				<Plus class="h-4 w-4 stroke-1.5" />
			</template>
			{{ __('programs.list.new') }}
		</Button>
	</header>
	<StudentPrograms v-if="isStudent" />
	<div v-else class="p-5 pb-10">
		<div
			class="flex flex-col lg:flex-row space-y-4 lg:space-y-0 lg:items-center justify-between mb-5"
		>
			<div class="text-lg text-ink-gray-9 font-semibold">
				{{ __('All Programs') }}
			</div>
			<FormControl
				v-model="title"
				:placeholder="__('Search by Title')"
				type="text"
				class="w-full lg:w-40"
				@input="updatePrograms()"
			/>
		</div>
		<div
			v-if="programs.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-8"
		>
			<div
				v-for="program in programs.data"
				@click="openForm(program.name)"
				class="cursor-pointer"
			>
<<<<<<< HEAD
				<ProgramCard :program="program" />
=======
				<div class="text-lg font-semibold">
					{{ program.name }}
				</div>
				<div class="flex items-center space-x-1">
					<BookOpen class="h-4 w-4 stroke-1.5 mr-1" />
					<span>
						{{ program.course_count }}
						{{ program.course_count == 1 ? __('programs.list.course') : __('programs.list.courses') }}
					</span>
				</div>
				<div class="flex items-center space-x-1">
					<User class="h-4 w-4 stroke-1.5 mr-1" />
					<span>
						{{ program.member_count || 0 }}
						{{ program.member_count == 1 ? __('programs.list.member') : __('programs.list.members') }}
					</span>
				</div>
>>>>>>> 04ef8e1a4c4b88c63f0f47866309c780be6523f5
			</div>
		</div>
		<EmptyState v-else-if="!programs.list?.loading" type="Programs" />
		<div
			v-if="!programs.list?.loading && programs.hasNextPage"
			class="flex justify-center mt-5"
		>
			<Button @click="programs.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
	<ProgramForm
		v-model="showForm"
		:programName="currentProgram"
		v-model:programs="programs"
	/>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	FormControl,
	usePageMeta,
	createListResource,
} from 'frappe-ui'
import { computed, inject, onMounted, ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { Plus } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import ProgramForm from '@/pages/Programs/ProgramForm.vue'
import ProgramCard from '@/components/ProgramCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import StudentPrograms from '@/pages/Programs/StudentPrograms.vue'

const { brand } = sessionStore()
const user = inject('$user')
const showForm = ref(false)
const currentProgram = ref(null)
const readOnlyMode = window.read_only_mode
const title = ref('')
const filters = ref({})

onMounted(() => {
	if (!user.data) {
		window.location.href = '/login'
	}
	if (user.data?.is_moderator || user.data?.is_instructor) {
		programs.reload()
	}
})

const programs = createListResource({
	doctype: 'LMS Program',
	cache: ['program'],
	fields: [
		'name',
		'title',
		'member_count',
		'course_count',
		'published',
		'enforce_course_order',
	],
	auto: false,
	pageLength: 20,
	orderBy: 'creation desc',
})

const updatePrograms = useDebounceFn(() => {
	if (title.value) {
		filters.value.title = ['like', `%${title.value}%`]
	} else {
		delete filters.value.title
	}
	programs.update({ filters: filters.value })
	programs.reload()
}, 300)

const canCreateProgram = () => {
	if (readOnlyMode) return false
	if (user.data?.is_moderator || user.data?.is_instructor) return true
	return false
}

const openForm = (programName) => {
	if (!canCreateProgram()) return
	currentProgram.value = programName
	showForm.value = true
}

const isStudent = computed(() => {
	return user.data?.is_student || false
})

const breadcrumbs = computed(() => [
	{
<<<<<<< HEAD
		label: __('Programs'),
		route: { name: 'Programs' },
=======
		label: __('programs.list.title'),
>>>>>>> 04ef8e1a4c4b88c63f0f47866309c780be6523f5
	},
])

usePageMeta(() => {
	return {
		title: __('programs.list.title'),
		icon: brand.favicon,
	}
})
</script>
