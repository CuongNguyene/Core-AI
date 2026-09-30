<template>
	<div class="flex flex-col min-h-0 text-base">
		<div class="flex items-center justify-between mb-5">
			<div class="flex flex-col space-y-2">
				<div class="lms-teams-settings__serif text-2xl leading-6 text-ink-gray-9">
					{{ label }}
				</div>
				<div class="text-ink-gray-6 leading-5">
					{{ __(description) }}
				</div>
			</div>
			<div class="flex items-center space-x-5">
				<Button @click="openForm('new')">
					<template #prefix>
						<Plus class="h-3 w-3 stroke-1.5" />
					</template>
					{{ __('New') }}
				</Button>
			</div>
		</div>
		<div v-if="teamsAccounts.data?.length" class="overflow-y-scroll">
			<ListView
				:columns="columns"
				:rows="teamsAccounts.data"
				row-key="name"
				:options="{
					showTooltip: false,
					onRowClick: (row) => {
						openForm(row.name)
					},
				}"
			>
				<ListHeader
					class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
				>
					<ListHeaderItem :item="item" v-for="item in columns">
						<template #prefix="{ item }">
							<FeatherIcon
								v-if="item.icon"
								:name="item.icon"
								class="h-4 w-4 stroke-1.5"
							/>
						</template>
					</ListHeaderItem>
				</ListHeader>

				<ListRows>
					<ListRow :row="row" v-for="row in teamsAccounts.data">
						<template #default="{ column, item }">
							<ListRowItem :item="row[column.key]" :align="column.align">
								<template #prefix>
									<div v-if="column.key == 'member_name'">
										<Avatar
											class="flex items-center"
											:image="row['member_image']"
											:label="item"
											size="sm"
										/>
									</div>
								</template>
								<div v-if="column.key == 'enabled'">
									<Badge v-if="row[column.key]" theme="green">
										{{ __('Enabled') }}
									</Badge>
									<Badge v-else theme="gray">
										{{ __('Disabled') }}
									</Badge>
								</div>
								<div v-else class="leading-5 text-sm">
									{{ row[column.key] }}
								</div>
							</ListRowItem>
						</template>
					</ListRow>
				</ListRows>

				<ListSelectBanner>
					<template #actions="{ unselectAll, selections }">
						<div class="flex gap-2">
							<Button
								variant="ghost"
								@click="removeAccount(selections, unselectAll)"
							>
								<Trash2 class="h-4 w-4 stroke-1.5" />
							</Button>
						</div>
					</template>
				</ListSelectBanner>
			</ListView>
		</div>
	</div>
	<TeamsAccountModal
		v-model="showForm"
		v-model:teamsAccounts="teamsAccounts"
		:accountID="currentAccount"
	/>
</template>
<script setup lang="ts">
import {
	Avatar,
	Button,
	Badge,
	call,
	createListResource,
	FeatherIcon,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	ListRowItem,
	ListSelectBanner,
	toast,
} from 'frappe-ui'
import { computed, inject, onMounted, ref } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import { cleanError } from '@/utils'
import { User } from '@/components/Settings/types'
import TeamsAccountModal from '@/components/Modals/TeamsAccountModal.vue'

const user = inject<User | null>('$user')
const showForm = ref(false)
const currentAccount = ref<string | null>(null)

const props = defineProps({
	label: String,
	description: String,
})

const teamsAccounts = createListResource({
	doctype: 'LMS Teams Settings',
	fields: [
		'name',
		'enabled',
		'member',
		'member_name',
		'member_image',
		'tenant_id',
		'client_id',
		'client_secret',
	],
	cache: ['teamsAccounts'],
})

onMounted(() => {
	fetchTeamsAccounts()
})

const fetchTeamsAccounts = () => {
	if (!user?.data?.is_moderator && !user?.data?.is_instructor) return

	if (!user?.data?.is_moderator) {
		teamsAccounts.update({
			filters: {
				member: user.data.name,
			},
		})
	}
	teamsAccounts.reload()
}

const openForm = (accountID: string) => {
	currentAccount.value = accountID
	showForm.value = true
}

const removeAccount = (selections, unselectAll) => {
	call('lms.lms.api.delete_documents', {
		doctype: 'LMS Teams Settings',
		documents: Array.from(selections),
	})
		.then(() => {
			teamsAccounts.reload()
			toast.success(__('Email Templates deleted successfully'))
			unselectAll()
		})
		.catch((err) => {
			toast.error(
				cleanError(err.messages[0]) || __('Error deleting email templates')
			)
		})
}

const columns = computed(() => {
	return [
		{
			label: __('Member'),
			key: 'member_name',
			icon: 'user',
		},
		{
			label: __('Account Name'),
			key: 'name',
			icon: 'video',
		},
		{
			label: __('Status'),
			key: 'enabled',
			align: 'center',
			icon: 'check-square',
		},
	]
})
</script>
<style scoped>
.lms-teams-settings__serif {
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
