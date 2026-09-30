<template>
	<Dialog
		v-model="show"
		class="text-base"
		:options="{
			size: 'lg',
			actions: [
				{
					label: __('sidebar.add'),
					variant: 'solid',
					onClick: (close) => {
						addWebPage(close)
					},
				},
			],
		}"
	>
		<template #body-title>
			<h3 class="lms-page-modal__serif text-2xl leading-6 text-ink-gray-9">
				{{ __('sidebar.addWebPage') }}
			</h3>
		</template>
		<template #body-content>
			<Link
				v-model="page.webpage"
				doctype="Web Page"
				:label="__('sidebar.webPage')"
				:filters="{
					published: 1,
				}"
			/>
			<IconPicker v-model="page.icon" :label="__('sidebar.icon')" class="mt-4" />
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, createResource, toast } from 'frappe-ui'
import Link from '@/components/Controls/Link.vue'
import { reactive, watch } from 'vue'
import IconPicker from '@/components/Controls/IconPicker.vue'

const sidebar = defineModel('reloadSidebar')
const show = defineModel()
const page = reactive({
	icon: '',
	webpage: '',
})

const props = defineProps({
	page: {
		type: Object,
		default: null,
	},
})

const webPage = createResource({
	url: 'lms.lms.api.update_sidebar_item',
	makeParams(values) {
		return {
			webpage: page.webpage,
			icon: page.icon,
		}
	},
})

watch(
	() => props.page,
	(newPage) => {
		if (newPage) {
			page.icon = newPage.icon
			page.webpage = newPage.web_page
		}
	},
	{ immediate: true }
)

const addWebPage = (close) => {
	webPage.submit(
		{},
		{
			onSuccess() {
				sidebar.value.reload()
				close()
				toast.success(__('sidebar.webPageAdded'))
			},
			onError(err) {
				toast.error(err.message[0] || err)
				close()
			},
		}
	)
}
</script>
<style scoped>
.lms-page-modal__serif {
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
