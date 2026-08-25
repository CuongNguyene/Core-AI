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
		<div class="mb-6 border-b border-outline-gray-2 pb-4">
			<div
				class="flex flex-col lg:flex-row space-y-4 lg:space-y-0 lg:items-end justify-between"
			>
				<div>
					<div
						class="lms-programs__mono mb-1 text-[11px] uppercase tracking-[0.14em] text-ink-gray-5"
					>
						{{ __('programs.list.title') }}
					</div>
					<div class="lms-programs__serif text-[1.75rem] leading-none text-ink-gray-9">
						{{ __('All Programs') }}
					</div>
				</div>
				<FormControl
					v-model="title"
					:placeholder="__('Search by Title')"
					type="text"
					class="w-full lg:w-40"
					@input="updatePrograms()"
				/>
			</div>
		</div>
		<div
			v-if="programs.list?.loading && !programs.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-8"
		>
			<CardSkeleton v-for="i in 8" :key="i" />
		</div>
		<div
			v-else-if="programs.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-8"
		>
			<div
				v-for="program in programs.data"
				@click="openForm(program.name)"
				class="cursor-pointer"
			>
				<ProgramCard :program="program" />
			</div>
		</div>
		<EmptyState v-else type="Programs" />
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
import CardSkeleton from '@/components/CardSkeleton.vue'
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
		label: __('Programs'),
		route: { name: 'Programs' },
	},
])

usePageMeta(() => {
	return {
		title: __('programs.list.title'),
		icon: brand.favicon,
	}
})
</script>
<style scoped>
.lms-programs__serif {
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

.lms-programs__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}
</style>
