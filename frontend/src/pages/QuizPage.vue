<template>
	<IntegrityWarningBanner v-if="!fromLesson" :count="violationCount" />
	<header
		v-if="!fromLesson"
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<div class="flex items-center space-x-2">
			<Button @click="goBack()">
				<template #prefix>
					<ArrowLeft class="size-4 stroke-1.5" />
				</template>
				{{ __('quiz.take.back') }}
			</Button>
			<Breadcrumbs :items="breadcrumbs" />
		</div>
	</header>
	<div
		class="md:w-7/12 md:mx-auto mx-4 py-10"
		:class="{ 'pt-4 md:w-full': fromLesson }"
	>
		<Quiz
			:quizName="quizID"
			:hide-integrity-banner="!fromLesson"
			@violation-count="violationCount = $event"
		/>
	</div>
</template>
<script setup>
import Quiz from '@/components/Quiz.vue'
import IntegrityWarningBanner from '@/components/IntegrityWarningBanner.vue'
import { createResource, Breadcrumbs, Button, usePageMeta } from 'frappe-ui'
import { computed, inject, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import { sessionStore } from '../stores/session'

const violationCount = ref(0)

const { brand } = sessionStore()
const user = inject('$user')
const router = useRouter()
const fromLesson = ref(false)

onMounted(() => {
	if (!user.data) {
		router.push({ name: 'Courses' })
	}

	if (new URLSearchParams(window.location.search).get('fromLesson')) {
		fromLesson.value = true
	}
})

const props = defineProps({
	quizID: {
		type: String,
		required: true,
	},
})

const goBack = () => {
	if (window.history.state?.back) {
		router.back()
	} else {
		router.push({ name: 'Courses' })
	}
}

const title = createResource({
	url: 'frappe.client.get_value',
	params: {
		doctype: 'LMS Quiz',
		fieldname: 'title',
		filters: {
			name: props.quizID,
		},
	},
	auto: true,
})

const breadcrumbs = computed(() => {
	return [{ label: __('quiz.builder.quiz') }, { label: title.data?.title }]
})

usePageMeta(() => {
	return {
		title: `${title.data?.title}`,
		icon: brand.favicon,
	}
})
</script>
