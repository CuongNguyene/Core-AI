<template>
	<div>
		<Button
			v-if="!singleThread && !readOnlyMode"
			class="float-right"
			@click="openTopicModal()"
		>
			<template #prefix>
				<Plus class="size-4" />
			</template>
			{{ __('batches.discussions.newItem').format(singularize(title)) }}
		</Button>
		<div class="lms-discussions__serif text-xl text-ink-gray-9">
			{{ title }}
		</div>
	</div>
	<div v-if="topics.data?.length && !singleThread">
		<div v-if="showTopics" v-for="(topic, index) in topics.data">
			<div
				@click="showReplies(topic)"
				class="flex items-center cursor-pointer py-5 w-full"
				:class="{ 'border-b': index + 1 != topics.data.length }"
			>
				<UserAvatar :user="topic.user" size="2xl" class="mr-4" />
				<div>
					<div class="lms-discussions__serif text-lg mb-1 text-ink-gray-7">
						{{ topic.title }}
					</div>
					<div class="flex items-center text-ink-gray-5">
						<span>
							{{ topic.user.full_name }}
						</span>
						<span class="text-sm ml-3">
							{{ timeAgo(topic.creation) }}
						</span>
					</div>
				</div>
			</div>
		</div>
		<div v-else>
			<DiscussionReplies
				:topic="currentTopic"
				v-model:showTopics="showTopics"
			/>
		</div>
	</div>
	<div v-else-if="singleThread && topics.data">
		<DiscussionReplies :topic="topics.data" :singleThread="singleThread" />
	</div>
	<div
		v-else
		class="flex flex-col items-center justify-center py-24 text-center"
	>
		<div
			class="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-surface-gray-2"
		>
			<MessageSquareText class="size-6 stroke-1.5 text-ink-gray-6" />
		</div>
		<div v-if="emptyStateTitle" class="text-lg font-semibold text-ink-gray-7 mb-2.5">
			{{ emptyStateTitle }}
		</div>
		<div class="leading-5 text-base w-full md:w-2/5 text-ink-gray-6">
			{{ emptyStateText || __('batches.discussions.startDiscussion') }}
		</div>
	</div>
	<DiscussionModal
		v-model="showTopicModal"
		:title="__('batches.discussions.newItem').format(title)"
		:doctype="props.doctype"
		:docname="props.docname"
		v-model:reloadTopics="topics"
	/>
</template>
<script setup>
import { createResource, Button } from 'frappe-ui'
import UserAvatar from '@/components/UserAvatar.vue'
import { singularize, timeAgo } from '@/utils'
import { ref, onMounted, inject, onUnmounted } from 'vue'
import DiscussionReplies from '@/components/DiscussionReplies.vue'
import DiscussionModal from '@/components/Modals/DiscussionModal.vue'
import { MessageSquareText, Plus } from 'lucide-vue-next'
import { getScrollContainer } from '@/utils/scrollContainer'

const showTopics = ref(true)
const currentTopic = ref(null)
const socket = inject('$socket')
const user = inject('$user')
const showTopicModal = ref(false)
const readOnlyMode = window.read_only_mode

const props = defineProps({
	title: {
		type: String,
		required: true,
	},
	doctype: {
		type: String,
		required: true,
	},
	docname: {
		type: String,
		required: true,
	},
	emptyStateTitle: {
		type: String,
		default: '',
	},
	emptyStateText: {
		type: String,
		default: '',
	},
	singleThread: {
		type: Boolean,
		default: false,
	},
	scrollToBottom: {
		type: Boolean,
		default: false,
	},
})

onMounted(() => {
	if (user.data) topics.reload()

	socket.on('new_discussion_topic', (data) => {
		topics.refresh()
	})

	if (props.scrollToBottom) {
		setTimeout(() => {
			scrollToEnd()
		}, 100)
	}
})

const scrollToEnd = () => {
	let scrollContainer = getScrollContainer()
	scrollContainer.scrollTop = scrollContainer.scrollHeight
}

const topics = createResource({
	url: 'lms.lms.utils.get_discussion_topics',
	cache: ['topics', props.doctype, props.docname],
	makeParams() {
		return {
			doctype: props.doctype,
			docname: props.docname,
			single_thread: props.singleThread,
		}
	},
})

const showReplies = (topic) => {
	showTopics.value = false
	currentTopic.value = topic
}

const openTopicModal = () => {
	showTopicModal.value = true
}

onUnmounted(() => {
	socket.off('new_discussion_topic')
})
</script>
<style scoped>
.lms-discussions__serif {
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
