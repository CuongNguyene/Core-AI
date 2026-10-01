<template>
	<Dialog
		v-model="show"
		:options="{
			size: 'xl',
		}"
	>
		<template #body>
			<div class="p-5 space-y-10 text-base">
				<div class="flex items-center space-x-2">
					<Avatar :image="student.user_image" size="3xl" />
					<div class="space-y-1">
						<div class="flex items-center space-x-2">
							<div class="lms-student-progress__serif text-xl">
								{{ student.full_name }}
							</div>
							<Badge
								v-if="
									Object.keys(student.assessments).length ||
									Object.keys(student.courses).length
								"
								:theme="student.progress === 100 ? 'green' : 'red'"
							>
								<span class="lms-student-progress__mono">
									{{ student.progress }}% {{ __('batches.studentProgress.complete') }}
								</span>
							</Badge>
							<Badge v-if="timeSpent.data" theme="gray">
								<span class="lms-student-progress__mono">
									{{ formatDuration(timeSpent.data.seconds) }}
								</span>
							</Badge>
						</div>
						<div class="text-sm text-ink-gray-7">
							{{ student.email }}
						</div>
					</div>
				</div>

				<div class="space-y-8">
					<!-- Assessments -->
					<div
						v-if="Object.keys(student.assessments).length"
						class="space-y-2 text-sm"
					>
						<div class="flex items-center border-b pb-1 font-medium">
							<span class="flex-1">
								{{ __('batches.studentProgress.assessment') }}
							</span>
							<span>
								{{ __('batches.studentProgress.percentageStatus') }}
							</span>
						</div>
						<router-link
							v-for="assessment in Object.keys(student.assessments)"
							class="flex items-center text-ink-gray-7 font-medium"
							:to="{
								name:
									student.assessments[assessment].type == 'LMS Assignment'
										? 'AssignmentSubmission'
										: '',
								params:
									student.assessments[assessment].type == 'LMS Assignment'
										? {
												assignmentID:
													student.assessments[assessment].assessment,
												submissionName:
													student.assessments[assessment].submission,
										  }
										: {},
							}"
						>
							<span class="flex-1">
								{{ assessment }}
							</span>
							<span v-if="isAssignment(student.assessments[assessment].status)">
								<Badge
									:theme="
										getStatusTheme(student.assessments[assessment].status)
									"
								>
									{{ student.assessments[assessment].status }}
								</Badge>
							</span>
							<span v-else>
								{{ student.assessments[assessment].status }}
							</span>
						</router-link>
					</div>

					<!-- Courses -->
					<div
						v-if="Object.keys(student.courses).length"
						class="space-y-2 text-sm"
					>
						<div class="flex items-center border-b pb-1 font-medium">
							<span class="flex-1">
								{{ __('batches.studentProgress.courses') }}
							</span>
							<span>
								{{ __('batches.studentProgress.progress') }}
							</span>
						</div>
						<div
							v-for="course in Object.keys(student.courses)"
							class="flex items-center text-ink-gray-7 font-medium"
						>
							<span class="flex-1">
								{{ course }}
							</span>
							<span>
								{{ Math.floor(student.courses[course]) }}
							</span>
						</div>
					</div>
				</div>

				<!-- Heatmap -->
				<StudentHeatmap :member="student.email" :days="120" />
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Avatar, Badge, createResource, Dialog } from 'frappe-ui'
import { watch } from 'vue'
import StudentHeatmap from '@/components/StudentHeatmap.vue'

const show = defineModel()
const props = defineProps({
	student: {
		type: Object,
		default: null,
	},
	batch: {
		type: String,
		default: null,
	},
})

const timeSpent = createResource({
	url: 'lms.lms.api.get_member_time_spent',
	auto: false,
})

watch(
	() => [show.value, props.student],
	([isOpen, student]) => {
		if (isOpen && student?.email && props.batch) {
			timeSpent.submit({
				member: student.email,
				batch: props.batch,
			})
		}
	},
	{ immediate: true }
)

const formatDuration = (seconds) => {
	let hours = Math.floor(seconds / 3600)
	let minutes = Math.floor((seconds % 3600) / 60)
	if (hours) return __('batches.studentProgress.hoursMinutesSpent').format(hours, minutes)
	return __('batches.studentProgress.minutesSpent').format(minutes)
}

const isAssignment = (value) => {
	return isNaN(value)
}

const getStatusTheme = (status) => {
	if (status === 'Pass') {
		return 'green'
	} else if (status == 'Not Graded') {
		return 'orange'
	} else {
		return 'red'
	}
}
</script>
<style scoped>
.lms-student-progress__serif {
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

.lms-student-progress__mono {
	font-family:
		'IBM Plex Mono',
		ui-monospace,
		SFMono-Regular,
		Menlo,
		Consolas,
		monospace;
}
</style>
