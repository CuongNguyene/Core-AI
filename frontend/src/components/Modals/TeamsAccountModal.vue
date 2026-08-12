<template>
	<Dialog
		v-model="show"
		:options="{
			title:
				accountID === 'new' ? __('teamsAccount.newAccount') : __('teamsAccount.editAccount'),
			size: 'xl',
			actions: [
				{
					label: __('teamsAccount.save'),
					variant: 'solid',
					onClick: ({ close }) => {
						saveAccount(close)
					},
				},
			],
		}"
	>
		<template #body-content>
			<div class="mb-4">
				<FormControl
					v-model="account.enabled"
					:label="__('teamsAccount.enabled')"
					type="checkbox"
				/>
			</div>
			<div class="grid grid-cols-2 gap-5">
				<FormControl
					v-model="account.name"
					:label="__('teamsAccount.accountName')"
					type="text"
					:required="true"
				/>
				<FormControl
					v-model="account.client_id"
					:label="__('teamsAccount.clientId')"
					type="text"
					:required="true"
				/>
				<Link
					v-model="account.member"
					:label="__('teamsAccount.member')"
					doctype="Course Evaluator"
					:onCreate="(value: string, close: () => void) => openSettings('Members', close)"
					:required="true"
				/>
				<FormControl
					v-model="account.client_secret"
					:label="__('teamsAccount.clientSecret')"
					type="password"
					:required="true"
				/>
				<FormControl
					v-model="account.tenant_id"
					:label="__('teamsAccount.tenantId')"
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

interface TeamsAccount {
	name: string
	account_name: string
	enabled: boolean
	member: string
	tenant_id: string
	client_id: string
	client_secret: string
}

interface TeamsAccounts {
	data: TeamsAccount[]
	reload: () => void
	insert: {
		submit: (
			data: TeamsAccount,
			options: { onSuccess: () => void; onError: (err: any) => void }
		) => void
	}
	setValue: {
		submit: (
			data: TeamsAccount,
			options: { onSuccess: () => void; onError: (err: any) => void }
		) => void
	}
}

const show = defineModel('show')
const user = inject<User | null>('$user')
const teamsAccounts = defineModel<TeamsAccounts>('teamsAccounts')

const account = reactive({
	name: '',
	enabled: false,
	member: user?.data?.name || '',
	tenant_id: '',
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
			teamsAccounts.value?.data.forEach((acc) => {
				if (acc.name === val) {
					account.name = acc.name
					account.enabled = acc.enabled || false
					account.member = acc.member
					account.tenant_id = acc.tenant_id
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
		account.tenant_id = ''
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
	teamsAccounts.value?.insert.submit(
		{
			account_name: account.name,
			...account,
		},
		{
			onSuccess() {
				teamsAccounts.value?.reload()
				close()
				toast.success(__('teamsAccount.createdSuccess'))
			},
			onError(err) {
				close()
				toast.error(
					cleanError(err.messages[0]) || __('teamsAccount.errorCreating')
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
		doctype: 'LMS Teams Settings',
		old_name: props.accountID,
		new_name: account.name,
	})
}

const setValue = (close: () => void) => {
	teamsAccounts.value?.setValue.submit(
		{
			...account,
			name: account.name,
			account_name: props.accountID,
		},
		{
			onSuccess() {
				teamsAccounts.value?.reload()
				close()
				toast.success(__('teamsAccount.updatedSuccess'))
			},
			onError(err: any) {
				close()
				toast.error(
					cleanError(err.messages[0]) || __('teamsAccount.errorUpdating')
				)
			},
		}
	)
}
</script>
