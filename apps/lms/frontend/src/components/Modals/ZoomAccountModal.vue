<template>
	<Dialog
		v-model="show"
		:options="{
			size: 'xl',
			actions: [
				{
					label: __('zoomAccount.save'),
					variant: 'solid',
					onClick: ({ close }) => {
						saveAccount(close)
					},
				},
			],
		}"
	>
		<template #body-title>
			<h3 class="lms-zoom-account-modal__serif text-2xl leading-6 text-ink-gray-9">
				{{ accountID === 'new' ? __('zoomAccount.newAccount') : __('zoomAccount.editAccount') }}
			</h3>
		</template>
		<template #body-content>
			<div class="mb-4">
				<FormControl
					v-model="account.enabled"
					:label="__('zoomAccount.enabled')"
					type="checkbox"
				/>
			</div>
			<div class="grid grid-cols-2 gap-5">
				<FormControl
					v-model="account.name"
					:label="__('zoomAccount.accountName')"
					type="text"
					:required="true"
				/>
				<FormControl
					v-model="account.client_id"
					:label="__('zoomAccount.clientId')"
					type="text"
					:required="true"
				/>
				<Link
					v-model="account.member"
					:label="__('zoomAccount.member')"
					doctype="Course Evaluator"
					:onCreate="(value: string, close: () => void) => openSettings('Members', close)"
					:required="true"
				/>
				<FormControl
					v-model="account.client_secret"
					:label="__('zoomAccount.clientSecret')"
					type="password"
					:required="true"
				/>
				<FormControl
					v-model="account.account_id"
					:label="__('zoomAccount.accountId')"
					type="text"
					:required="true"
				/>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { call, Dialog, FormControl, toast } from 'frappe-ui'
import { inject, reactive, watch } from 'vue'
import { User } from '@/components/Settings/types'
import { openSettings, cleanError } from '@/utils'
import Link from '@/components/Controls/Link.vue'

interface ZoomAccount {
	name: string
	account_name: string
	enabled: boolean
	member: string
	account_id: string
	client_id: string
	client_secret: string
}

interface ZoomAccounts {
	data: ZoomAccount[]
	reload: () => void
	insert: {
		submit: (
			data: ZoomAccount,
			options: { onSuccess: () => void; onError: (err: any) => void }
		) => void
	}
	setValue: {
		submit: (
			data: ZoomAccount,
			options: { onSuccess: () => void; onError: (err: any) => void }
		) => void
	}
}

const show = defineModel('show')
const user = inject<User | null>('$user')
const zoomAccounts = defineModel<ZoomAccounts>('zoomAccounts')

const account = reactive({
	name: '',
	enabled: false,
	member: user?.data?.name || '',
	account_id: '',
	client_id: '',
	client_secret: '',
})

const props = defineProps({
	accountID: {
		type: String,
		default: 'new',
	},
})

watch(
	() => props.accountID,
	(val) => {
		if (val != 'new') {
			zoomAccounts.value?.data.forEach((acc) => {
				if (acc.name === val) {
					account.name = acc.name
					account.enabled = acc.enabled || false
					account.member = acc.member
					account.account_id = acc.account_id
					account.client_id = acc.client_id
					account.client_secret = acc.client_secret
				}
			})
		}
	}
)

watch(show, (val) => {
	if (!val) {
		account.name = ''
		account.enabled = false
		account.member = user?.data?.name || ''
		account.account_id = ''
		account.client_id = ''
		account.client_secret = ''
	}
})

const saveAccount = (close: () => void) => {
	if (props.accountID == 'new') {
		createAccount(close)
	} else {
		updateAccount(close)
	}
}

const createAccount = (close: () => void) => {
	zoomAccounts.value?.insert.submit(
		{
			account_name: account.name,
			...account,
		},
		{
			onSuccess() {
				zoomAccounts.value?.reload()
				close()
				toast.success(__('zoomAccount.createdSuccess'))
			},
			onError(err) {
				close()
				toast.error(
					cleanError(err.messages[0]) || __('zoomAccount.errorCreating')
				)
			},
		}
	)
}

const updateAccount = async (close: () => void) => {
	if (props.accountID != account.name) {
		await renameDoc()
	}
	setValue(close)
}

const renameDoc = async () => {
	await call('frappe.client.rename_doc', {
		doctype: 'LMS Zoom Settings',
		old_name: props.accountID,
		new_name: account.name,
	})
}

const setValue = (close: () => void) => {
	zoomAccounts.value?.setValue.submit(
		{
			...account,
			name: account.name,
			account_name: props.accountID,
		},
		{
			onSuccess() {
				zoomAccounts.value?.reload()
				close()
				toast.success(__('zoomAccount.updatedSuccess'))
			},
			onError(err: any) {
				close()
				toast.error(
					cleanError(err.messages[0]) || __('zoomAccount.errorUpdating')
				)
			},
		}
	)
}
</script>
<style scoped>
.lms-zoom-account-modal__serif {
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
