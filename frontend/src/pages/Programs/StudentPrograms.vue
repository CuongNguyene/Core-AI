<template>
	<div class="p-5 pb-10">
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
						{{ __('programs.studentPrograms.allPrograms') }}
					</div>
				</div>
				<div
					class="flex flex-col space-y-3 lg:space-y-0 lg:flex-row lg:items-center lg:space-x-4"
				>
					<TabButtons v-model="currentTab" :buttons="tabs" class="w-fit" />
					<FormControl
						v-model="searchQuery"
						:placeholder="__('Search by Title')"
						type="text"
						class="w-full lg:w-40"
					/>
				</div>
			</div>
		</div>
		<div v-for="(data, category) in programs.data">
			<div v-if="category == currentTab">
				<div
					v-if="filterPrograms(data).length > 0"
					class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-8"
				>
					<div
						v-for="program in filterPrograms(data)"
						@click="openDetails(program.name, category)"
						class="cursor-pointer"
					>
						<ProgramCard :program="program" />
					</div>
				</div>
				<EmptyState v-else :type="convertToTitleCase(category) + ' Programs'" />
				<!-- <div v-else class="col-span-3 text-center text-ink-gray-5">
                    {{ __('No programs found in this category.') }}
                </div> -->
			</div>
		</div>
	</div>
	<ProgramEnrollment
		v-model="showEnrollmentConfirmation"
		:programName="enrollmentProgram"
	/>
</template>
<script setup lang="ts">
import { createResource, FormControl, TabButtons } from 'frappe-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { convertToTitleCase } from '@/utils'
import ProgramCard from '@/components/ProgramCard.vue'
import ProgramEnrollment from '@/pages/Programs/ProgramEnrollment.vue'
import EmptyState from '@/components/EmptyState.vue'

const currentTab = ref('enrolled')
const router = useRouter()
const showEnrollmentConfirmation = ref(false)
const enrollmentProgram = ref(null)
const searchQuery = ref('')

const programs = createResource({
	url: 'lms.lms.utils.get_programs',
	auto: true,
})

// Client-side title filter (get_programs returns all programs; no API change).
const filterPrograms = (data: any[]) => {
	if (!searchQuery.value) return data
	const query = searchQuery.value.toLowerCase()
	return data.filter((program) =>
		(program.name || '').toLowerCase().includes(query)
	)
}

const openDetails = (programName: any, category: string) => {
	if (category === 'enrolled') {
		router.push({
			name: 'ProgramDetail',
			params: { programName: programName },
		})
	} else {
		showEnrollmentConfirmation.value = true
		enrollmentProgram.value = programName
	}
}

const tabs = computed(() => {
	return [
		{
			label: __('programs.studentPrograms.enrolledTab'),
			value: 'enrolled',
		},
		{
			label: __('programs.studentPrograms.publishedTab'),
			value: 'published',
		},
	]
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
