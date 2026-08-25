<template>
	<Dialog
		:options="{
			title: __('profile.editProfile.title'),
			size: 'xl',
			actions: [
				{
					label: __('profile.editProfile.save'),
					variant: 'solid',
					onClick: (close) => saveProfile(close),
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-5">
				<div>
					<div class="text-xs text-ink-gray-5 mb-1">
						{{ __('profile.editProfile.profileImage') }}
					</div>
					<FileUploader
						v-if="!profile.image"
						:fileTypes="['image/*']"
						:validateFile="validateFile"
						@success="(file) => saveImage(file)"
					>
						<template
							v-slot="{ file, progress, uploading, openFileSelector }"
						>
							<div class="mb-4">
								<Button @click="openFileSelector" :loading="uploading">
									{{
										uploading
											? __('profile.coverImage.uploading').format(progress)
											: __('profile.editProfile.uploadProfileImage')
									}}
								</Button>
							</div>
						</template>
					</FileUploader>
					<div v-else class="mb-4">
						<div class="flex items-center">
							<img
								:src="profile.image.file_url"
								class="object-cover h-[50px] w-[50px] rounded-full border-4 border-white object-cover"
							/>

							<div class="text-base flex flex-col ml-2">
								<span>
									{{ profile.image.file_name }}
								</span>
								<span class="text-sm text-ink-gray-4 mt-1">
									{{ getFileSize(profile.image.file_size) }}
								</span>
							</div>
							<X
								@click="removeImage()"
								class="bg-surface-gray-3 rounded-md cursor-pointer stroke-1.5 w-5 h-5 p-1 ml-4"
							/>
						</div>
					</div>
				</div>
				<div>
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('profile.editProfile.bio') }}
					</div>
					<TextEditor
						:fixedMenu="true"
						@change="(val) => (profile.bio = val)"
						:content="profile.bio"
						editorClass="prose-sm py-2 px-2 min-h-[200px] border-outline-gray-2 hover:border-outline-gray-3 rounded-b-md bg-surface-gray-3"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	Dialog,
	FileUploader,
	Button,
	createResource,
	TextEditor,
	toast,
} from 'frappe-ui'
import { reactive, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { getFileSize, decodeEntities } from '@/utils'
import DOMPurify from 'dompurify'

const reloadProfile = defineModel('reloadProfile')

const props = defineProps({
	profile: {
		type: Object,
		required: true,
	},
})

const profile = reactive({
	bio: '',
	image: '',
})

const imageResource = createResource({
	url: 'lms.lms.api.get_file_info',
	makeParams(values) {
		return {
			file_url: values.image,
		}
	},
	auto: false,
	onSuccess(data) {
		profile.image = data
	},
})

const updateProfile = createResource({
	url: 'frappe.client.set_value',
	makeParams(values) {
		return {
			doctype: 'User',
			name: props.profile.data.name,
			fieldname: {
				user_image: profile.image.file_url,
				...profile,
			},
		}
	},
	onSuccess(data) {
		props.profile.data = data
	},
})

const saveProfile = (close) => {
	profile.bio = DOMPurify.sanitize(decodeEntities(profile.bio), {
		ALLOWED_TAGS: [
			'b',
			'i',
			'em',
			'strong',
			'a',
			'p',
			'br',
			'ul',
			'ol',
			'li',
			'img',
		],
		ALLOWED_ATTR: ['href', 'target', 'src'],
	})
	updateProfile.submit(
		{},
		{
			onSuccess() {
				close()
				reloadProfile.value.reload()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

const validateFile = (file) => {
	let extension = file.name.split('.').pop().toLowerCase()
	if (!['jpg', 'jpeg', 'png'].includes(extension)) {
		return __('profile.coverImage.onlyImageAllowed')
	}
}

const saveImage = (file) => {
	profile.image = file
}

const removeImage = () => {
	profile.image = null
}

watch(
	() => props.profile.data,
	(newVal) => {
		if (newVal) {
			profile.bio = newVal.bio
			if (newVal.user_image) imageResource.submit({ image: newVal.user_image })
		}
	}
)
</script>
