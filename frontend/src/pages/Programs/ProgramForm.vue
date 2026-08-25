<template>
	<Dialog
		v-model="show"
		:options="{
			size: '2xl',
		}"
	>
		<template #body-title>
			<div class="flex items-center justify-between space-x-2 text-base w-full">
				<div class="lms-program-form__serif text-xl text-ink-gray-9">
					{{
						programName === 'new' ? __('programs.form.createProgram') : __('programs.form.editProgram')
					}}
				</div>
				<Badge theme="orange" v-if="dirty">
					{{ __('programs.form.notSaved') }}
				</Badge>
			</div>
		</template>
		<template #body-content>
			<div class="text-base">
				<div class="grid grid-cols-1 md:grid-cols-2 gap-5 pb-5">
					<FormControl
						v-model="program.name"
						:label="__('programs.form.title')"
						type="text"
						:required="true"
						@change="dirty = true"
					/>
					<div class="flex flex-col space-y-3">
						<FormControl
							v-if="isModerator"
							v-model="program.published"
							:label="__('programs.form.published')"
							type="checkbox"
							@change="dirty = true"
						/>
						<div v-else class="text-sm text-ink-gray-6 flex items-center gap-1.5">
							<Info class="size-4 shrink-0" />
							{{ __('programs.form.publishedByModerator') }}
						</div>
						<FormControl
							v-model="program.enforce_course_order"
							:label="__('programs.form.enforceCourseOrder')"
							type="checkbox"
							@change="dirty = true"
						/>
					</div>
				</div>

				<div class="pb-5">
					<div class="flex items-center justify-between mt-5 mb-4">
						<div class="lms-program-form__serif text-lg text-ink-gray-9">
							{{ __('programs.form.courses') }}
						</div>
						<Button @click="openForm('course')">
							<template #prefix>
								<Plus class="h-4 w-4 stroke-1.5" />
							</template>
							<span>
								{{ __('programs.form.add') }}
							</span>
						</Button>
					</div>
					<ListView
						v-if="programCourses.data.length > 0"
						:columns="courseColumns"
						:rows="programCourses.data"
						:options="{
							selectable: true,
							resizeColumn: true,
							showTooltip: false,
						}"
						rowKey="name"
					>
						<ListHeader
							class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
						>
							<ListHeaderItem :item="item" v-for="item in courseColumns" />
						</ListHeader>
						<ListRows>
							<Draggable
								:list="programCourses.data"
								item-key="name"
								group="items"
								@end="updateOrder"
								class="cursor-move"
							>
								<template #item="{ element: row }">
									<ListRow :row="row" />
								</template>
							</Draggable>
						</ListRows>
						<ListSelectBanner>
							<template #actions="{ unselectAll, selections }">
								<div class="flex gap-2">
									<Button
										variant="ghost"
										@click="remove(selections, unselectAll, 'courses')"
									>
										<Trash2 class="h-4 w-4 stroke-1.5" />
									</Button>
								</div>
							</template>
						</ListSelectBanner>
					</ListView>
					<div v-else class="text-ink-gray-7">
						{{ __('programs.form.noCoursesAdded') }}
					</div>
				</div>

				<div>
					<div class="flex items-center justify-between mt-5 mb-4">
						<div class="lms-program-form__serif text-lg text-ink-gray-9">
							{{ __('programs.form.members') }}
						</div>

						<div class="space-x-2">
							<Button
								v-if="programMembers.data.length > 0"
								@click="
									() => {
										showProgressDialog = true
									}
								"
							>
								<template #prefix>
									<TrendingUp class="size-4 stroke-1.5" />
								</template>
								{{ __('programs.form.progressSummary') }}
							</Button>
							<Button @click="openForm('member')">
								<template #prefix>
									<Plus class="h-4 w-4 stroke-1.5" />
								</template>
								{{ __('programs.form.add') }}
							</Button>
						</div>
					</div>
					<ListView
						v-if="programMembers.data.length > 0"
						:columns="memberColumns"
						:rows="programMembers.data"
						:options="{
							selectable: true,
							resizeColumn: true,
						}"
						rowKey="name"
					>
						<ListHeader
							class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
						>
							<ListHeaderItem :item="item" v-for="item in memberColumns" />
						</ListHeader>
						<ListRows>
							<ListRow :row="row" v-for="row in programMembers.data" />
						</ListRows>
						<ListSelectBanner>
							<template #actions="{ unselectAll, selections }">
								<div class="flex gap-2">
									<Button
										variant="ghost"
										@click="remove(selections, unselectAll, 'members')"
									>
										<Trash2 class="h-4 w-4 stroke-1.5" />
									</Button>
								</div>
							</template>
						</ListSelectBanner>
					</ListView>
					<div v-else class="text-ink-gray-7">
						{{ __('programs.form.noMembersAdded') }}
					</div>
				</div>
			</div>
			<Dialog
				v-model="showFormDialog"
				:options="{
					title:
						currentForm == 'course'
							? __('programs.form.addCourseTitle')
							: __('programs.form.enrollMemberTitle'),
					actions: [
						{
							label: __('programs.form.add'),
							variant: 'solid',
							onClick: ({ close }: { close: () => void }) =>
								currentForm == 'course'
									? addCourse(close)
									: addMember(close),
						},
					],
				}"
			>
				<template #body-content>
					<div @click.stop>
						<Link
							v-if="currentForm == 'course'"
							v-model="course"
							doctype="LMS Course"
							:label="__('programs.form.course')"
						/>

						<Link
							v-if="currentForm == 'member'"
							v-model="member"
							doctype="User"
							:filters="{
								ignore_user_type: 1,
							}"
							:label="__('Program Member')"
							:onCreate="(value: string, close: () => void) => createMember(close)"
						/>
					</div>
				</template>
			</Dialog>

			<ProgramProgressSummary
				v-model="showProgressDialog"
				:programName="programName"
				:programMembers="programMembers.data"
			/>
		</template>
		<template #actions="{ close }">
			<div class="flex items-center justify-between">
				<Button
					v-if="programName != 'new'"
					@click="deleteProgram(close)"
					variant="outline"
					theme="red"
				>
					<template #prefix>
						<Trash2 class="size-4 stroke-1.5" />
					</template>
					{{ __('programs.form.delete') }}
				</Button>
				<span v-else></span>
				<Button variant="solid" @click="saveProgram(close)">
					{{ __('programs.form.save') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import {
	Badge,
	Button,
	createListResource,
	Dialog,
	FormControl,
	ListSelectBanner,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	toast,
} from 'frappe-ui'
import { computed, inject, ref, watch } from 'vue'
import { Info, Plus, Trash2, TrendingUp } from 'lucide-vue-next'
import { Programs, Program } from '@/types/programs'
import { openSettings } from '@/utils'
import Link from '@/components/Controls/Link.vue'
import Draggable from 'vuedraggable'
import ProgramProgressSummary from '@/pages/Programs/ProgramProgressSummary.vue'

const show = defineModel<boolean>()
const programs = defineModel<Programs>('programs')
const showFormDialog = ref(false)
const currentForm = ref<'course' | 'member'>('course')
const course = ref<string>('')
const member = ref<string>('')
const showProgressDialog = ref(false)
const dirty = ref(false)
const user = inject<any>('$user')
const isModerator = computed(() => user?.data?.is_moderator || false)

const props = withDefaults(
	defineProps<{
		programName: string | null
	}>(),
	{
		programName: 'new',
	}
)

const program = ref<Program>({
	name: '',
	title: '',
	published: false,
	enforce_course_order: false,
	program_courses: [],
	program_members: [],
})

watch(
	() => props.programName,
	() => {
		setProgramData()
		fetchCourses()
		fetchMembers()
	}
)

const setProgramData = () => {
	let isNew = true
	programs.value?.data.forEach((p: Program) => {
		if (p.name === props.programName) {
			isNew = false
			program.value = { ...p }
		}
	})

	if (isNew) {
		program.value = {
			name: '',
			title: '',
			published: false,
			enforce_course_order: false,
			program_courses: [],
			program_members: [],
		}
	}
	dirty.value = false
}

const programCourses = createListResource({
	doctype: 'LMS Program Course',
	fields: ['course', 'course_title', 'name', 'idx'],
	cache: ['programCourses', props.programName],
	parent: 'LMS Program',
	orderBy: 'idx',
	onSuccess(data: ProgramCourse[]) {
		program.value.program_courses = data
	},
})

const programMembers = createListResource({
	doctype: 'LMS Program Member',
	fields: ['member', 'full_name', 'progress', 'name'],
	cache: ['programMembers', props.programName],
	parent: 'LMS Program',
	orderBy: 'creation desc',
	onSuccess(data: ProgramMember[]) {
		program.value.program_members = data
	},
})

const fetchCourses = () => {
	programCourses.update({
		filters: {
			parent: props.programName,
			parenttype: 'LMS Program',
			parentfield: 'program_courses',
		},
	})
	programCourses.reload()
}

const fetchMembers = () => {
	programMembers.update({
		filters: {
			parent: props.programName,
			parenttype: 'LMS Program',
			parentfield: 'program_members',
		},
	})
	programMembers.reload()
}

const saveProgram = (close: () => void) => {
	if (props.programName === 'new') createNewProgram(close)
	else updateProgram(close)
	dirty.value = false
}

const createNewProgram = (close: () => void) => {
	programs.value.insert.submit(
		{
			...program.value,
			title: program.value.name,
		},
		{
			onSuccess() {
				close()
				programs.value.reload()
				if (isModerator.value) {
					toast.success(__('programs.form.createdSuccess'))
				} else {
					toast.success(__('programs.form.createdPendingReview'))
				}
			},
			onError(err: any) {
				toast.warning(__(err.messages?.[0] || err))
			},
		}
	)
}

const updateProgram = (close: () => void) => {
	programs.value.setValue.submit(
		{
			name: props.programName,
			...program.value,
		},
		{
			onSuccess() {
				close()
				programs.value.reload()
				toast.success(__('programs.form.updatedSuccess'))
			},
			onError(err: any) {
				toast.warning(__(err.messages?.[0] || err))
			},
		}
	)
}

const openForm = (formType: 'course' | 'member') => {
	currentForm.value = formType
	showFormDialog.value = true
	if (formType === 'course') {
		course.value = ''
	} else {
		member.value = ''
	}
}

const createMember = (close: () => void) => {
	close()
	showFormDialog.value = false
	show.value = false
	openSettings('Members')
}

const addCourse = (close: () => void) => {
	if (!course.value) {
		toast.warning(__('programs.form.selectCourseRequired'))
		return
	}

	programCourses.insert.submit(
		{
			parent: props.programName,
			parenttype: 'LMS Program',
			parentfield: 'program_courses',
			course: course.value,
			idx: programCourses.data.length + 1,
		},
		{
			onSuccess() {
				updateCounts('course', 'add')
				close()
				toast.success(__('programs.form.courseAddedSuccess'))
			},
			onError(err: any) {
				toast.warning(__(err.messages?.[0] || err))
			},
		}
	)
}

const addMember = (close: () => void) => {
	if (!member.value) {
		toast.warning(__('programs.form.selectMemberRequired'))
		return
	}

	programMembers.insert.submit(
		{
			parent: props.programName,
			parenttype: 'LMS Program',
			parentfield: 'program_members',
			member: member.value,
		},
		{
			onSuccess() {
				updateCounts('member', 'add')
				close()
				toast.success(__('programs.form.memberAddedSuccess'))
			},
			onError(err: any) {
				toast.warning(__(err.messages?.[0] || err))
			},
		}
	)
}

const updateCounts = async (
	type: 'member' | 'course',
	action: 'add' | 'remove'
) => {
	if (!props.programName) return

	let memberCount = programMembers.data?.length || 0
	let courseCount = programCourses.data?.length || 0

	if (type === 'member') {
		memberCount += action === 'add' ? 1 : -1
	} else {
		courseCount += action === 'add' ? 1 : -1
	}

	await programs.value.setValue.submit(
		{
			name: props.programName,
			member_count: memberCount,
			course_count: courseCount,
		},
		{
			onSuccess() {
				setProgramData()
			},
			onError(err: any) {
				toast.warning(__(err.messages?.[0] || err))
			},
		}
	)
}

const updateOrder = async (e: DragEvent) => {
	let sourceIdx = e.from.dataset.idx
	let targetIdx = e.to.dataset.idx
	let courses = programCourses.data
	courses.splice(targetIdx, 0, courses.splice(sourceIdx, 1)[0])

	for (const [index, course] of courses.entries()) {
		programCourses.setValue.submit(
			{
				name: course.name,
				idx: index + 1,
			},
			{
				onError(err: any) {
					toast.warning(__(err.messages?.[0] || err))
				},
			}
		)
		await wait(100)
	}
}

const wait = (ms: number) => new Promise((res) => setTimeout(res, ms))

const remove = async (
	selections: string[],
	unselectAll: () => void,
	type: string
) => {
	selections = Array.from(selections)
	for (const selection of selections) {
		if (type == 'courses') {
			await programCourses.delete.submit(selection)
			await updateCounts('course', 'remove')
		} else {
			await programMembers.delete.submit(selection)
			await updateCounts('member', 'remove')
		}
		await programs.value.reload()
		await wait(100)
	}
	unselectAll()
}

const deleteProgram = (close: () => void) => {
	if (props.programName == 'new') return
	programs.value?.delete.submit(props.programName, {
		onSuccess() {
			toast.success(__('programs.form.deletedSuccess'))
			close()
		},
		onError(err: any) {
			toast.warning(__(err.messages?.[0] || err))
		},
	})
}

const courseColumns = computed(() => {
	return [
		{
			label: __('programs.form.title'),
			key: 'course_title',
			width: 1,
		},
	]
})

const memberColumns = computed(() => {
	return [
		{
			label: __('programs.progressSummary.member'),
			key: 'member',
			width: 3,
			align: 'left',
		},
		{
			label: __('programs.form.fullName'),
			key: 'full_name',
			width: 3,
			align: 'left',
		},
	]
})
</script>
<style scoped>
.lms-program-form__serif {
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
</style>
