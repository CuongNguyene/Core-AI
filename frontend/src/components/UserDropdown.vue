<template>
	<div class="p-2">
		<Dropdown :options="userDropdownOptions">
			<template v-slot="{ open }">
				<button
					class="flex h-12 py-2 items-center rounded-md duration-300 ease-in-out"
					:class="
						isCollapsed
							? 'px-0 w-auto'
							: open
							? 'bg-surface-white shadow-sm px-2 w-52'
							: 'hover:bg-surface-gray-3 px-2 w-52'
					"
				>
					<img
						v-if="branding.data?.banner_image"
						:src="branding.data?.banner_image.file_url"
						class="w-8 h-8 rounded flex-shrink-0"
					/>
					<LMSLogo v-else class="w-8 h-8 rounded flex-shrink-0" />
					<div
						class="flex flex-1 flex-col text-left duration-300 ease-in-out"
						:class="
							isCollapsed
								? 'opacity-0 ml-0 w-0 overflow-hidden'
								: 'opacity-100 ml-2 w-auto'
						"
					>
						<div class="text-base font-medium text-ink-gray-9 leading-none">
							<span
								v-if="
									branding.data?.app_name && branding.data?.app_name != 'Frappe'
								"
							>
								{{ branding.data?.app_name }}
							</span>
							<span v-else> Learning </span>
						</div>
						<div
							v-if="userResource.data"
							class="mt-1 text-sm text-ink-gray-7 leading-none"
						>
							{{ convertToTitleCase(userResource.data?.full_name) }}
						</div>
					</div>
					<div
						class="duration-300 ease-in-out"
						:class="
							isCollapsed
								? 'opacity-0 ml-0 w-0 overflow-hidden'
								: 'opacity-100 ml-2 w-auto'
						"
					>
						<ChevronDown class="h-4 w-4 text-ink-gray-7" />
					</div>
				</button>
			</template>
		</Dropdown>
	</div>
	<SettingsModal
		v-if="userResource.data?.is_moderator"
		v-model="showSettingsModal"
	/>
</template>

<script setup>
import LMSLogo from '@/components/Icons/LMSLogo.vue'
import { sessionStore } from '@/stores/session'
import { Dropdown } from 'frappe-ui'
import Apps from '@/components/Apps.vue'
import { useRouter } from 'vue-router'
import { convertToTitleCase } from '@/utils'
import { usersStore } from '@/stores/user'
import { useSettings } from '@/stores/settings'
import { markRaw, watch, ref, onMounted, computed } from 'vue'
import { createDialog } from '@/utils/dialogs'
import { createResource } from 'frappe-ui'
import SettingsModal from '@/components/Settings/Settings.vue'
import FrappeCloudIcon from '@/components/Icons/FrappeCloudIcon.vue'
import translations from '@/translations'
import {
	ChevronDown,
	Check,
	Languages,
	LogIn,
	LogOut,
	Moon,
	User,
	Settings,
	Sun,
	Zap,
} from 'lucide-vue-next'

const router = useRouter()
const { logout, branding } = sessionStore()
let { userResource } = usersStore()
const settingsStore = useSettings()
let { isLoggedIn } = sessionStore()
const showSettingsModal = ref(false)
const theme = ref('light')
const frappeCloudBaseEndpoint = 'https://frappecloud.com'
const $dialog = createDialog

const languageNames = {
	en: 'English',
	vi: 'Tiếng Việt',
}

const updateLanguage = createResource({
	url: 'frappe.client.set_value',
	onSuccess() {
		window.location.reload()
	},
})

const setLanguage = (code) => {
	if (code === userResource.data?.language) return
	updateLanguage.submit({
		doctype: 'User',
		name: userResource.data?.name,
		fieldname: 'language',
		value: code,
	})
}

const props = defineProps({
	isCollapsed: {
		type: Boolean,
		default: false,
	},
})

onMounted(() => {
	theme.value = localStorage.getItem('theme') || 'light'
	if (['light', 'dark'].includes(theme.value)) {
		document.documentElement.setAttribute('data-theme', theme.value)
	}
})

watch(
	() => settingsStore.isSettingsOpen,
	(value) => {
		showSettingsModal.value = value
	}
)

// const toggleTheme = () => {
// 	const currentTheme = document.documentElement.getAttribute('data-theme')
// 	theme.value = currentTheme === 'dark' ? 'light' : 'dark'
// 	document.documentElement.setAttribute('data-theme', theme.value)
// 	localStorage.setItem('theme', theme.value)
// }

const userDropdownOptions = computed(() => {
	return [
		{
			group: '',
			items: [
				{
					icon: User,
					label: __('sidebar.myProfile'),
					onClick: () => {
						router.push(`/user/${userResource.data?.username}`)
					},
					condition: () => {
						return isLoggedIn
					},
				},
				// {
				// 	icon: theme.value === 'light' ? Moon : Sun,
				// 	label: 'Toggle Theme',
				// 	onClick: () => {
				// 		toggleTheme()
				// 	},
				// },
				{
					icon: Settings,
					label: __('sidebar.settings'),
					onClick: () => {
						settingsStore.isSettingsOpen = true
					},
					condition: () => {
						return userResource.data?.is_moderator
					},
				},
				{
					icon: Languages,
					label: __('sidebar.language'),
					submenu: Object.keys(translations).map((code) => ({
						icon: userResource.data?.language === code ? Check : undefined,
						label: languageNames[code] || code,
						onClick: () => setLanguage(code),
					})),
					condition: () => {
						return isLoggedIn && Object.keys(translations).length > 1
					},
				},
				{
					icon: FrappeCloudIcon,
					label: __('sidebar.loginToFrappeCloud'),
					onClick: () => {
						$dialog({
							title: __('sidebar.loginToFrappeCloudTitle'),
							message: __(
								'sidebar.loginToFrappeCloudMessage'
							),
							actions: [
								{
									label: __('sidebar.confirm'),
									variant: 'solid',
									onClick(close) {
										loginToFrappeCloud()
										close()
									},
								},
							],
						})
					},
					condition: () => {
						return (
							userResource.data?.is_system_manager &&
							userResource.data?.is_fc_site
						)
					},
				},
				{
					icon: LogOut,
					label: __('sidebar.logOut'),
					onClick: () => {
						logout.submit().then(() => {
							isLoggedIn = false
						})
					},
					condition: () => {
						return isLoggedIn
					},
				},
				{
					icon: LogIn,
					label: __('sidebar.logIn'),
					onClick: () => {
						window.location.href = `/login?redirect-to=${encodeURIComponent(
							window.location.pathname + window.location.search,
						)}`
					},
					condition: () => {
						return !isLoggedIn
					},
				},
			],
		},
	]
})

const loginToFrappeCloud = () => {
	let redirect_to = '/dashboard/sites/' + userResource.data.sitename
	window.open(`${frappeCloudBaseEndpoint}${redirect_to}`, '_blank')
}
</script>
