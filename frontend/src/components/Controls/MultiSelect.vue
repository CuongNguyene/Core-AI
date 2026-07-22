<template>
	<div>
		<label class="block mb-1" :class="labelClasses" v-if="label">
			{{ label }}
			<span class="text-ink-red-3" v-if="required">*</span>
		</label>
		<div class="w-full">
			<Combobox v-model="selectedValue" nullable>
				<Popover class="w-full" v-model:show="showOptions" match-target-width>
					<template #target="{ togglePopover }">
						<ComboboxInput
							ref="search"
							class="search-input form-input w-full focus-visible:!ring-0"
							type="text"
							:value="query"
							@change="
								(e) => {
									query = e.target.value
									showOptions = true
								}
							"
							autocomplete="off"
							@focus="() => togglePopover()"
							@keydown.delete.capture.stop="removeLastValue"
						/>
					</template>
					<template #body="{ isOpen, close }">
						<div v-show="isOpen" class="w-full">
							<div
								class="mt-1 rounded-lg bg-surface-white py-1 text-base border-2 w-full"
							>
								<ComboboxOptions
									class="my-1 min-h-[4rem] max-h-[12rem] overflow-y-auto px-1.5"
									static
								>
									<ComboboxOption
										v-for="option in options"
										:key="option.value"
										:value="option"
										v-slot="{ active }"
									>
										<li
											:class="[
												'flex cursor-pointer items-center rounded px-2 py-1 text-base',
												{ 'bg-surface-gray-2': active },
											]"
										>
											<div class="flex flex-col gap-1 p-1">
												<div class="text-base font-medium text-ink-gray-8">
													{{ option.description }}
												</div>
												<div class="text-sm text-ink-gray-5">
													{{ option.value }}
												</div>
											</div>
										</li>
									</ComboboxOption>
									<div
										v-if="options.length === 0"
										class="px-2.5 py-2 text-base text-ink-gray-5"
									>
										No results found
									</div>
								</ComboboxOptions>
								<div
									v-if="attrs.onCreate"
									class="border-t p-1"
								>
									<Button
										variant="ghost"
										class="w-full !justify-start"
										:label="__('Create New')"
										@click="attrs.onCreate(close)"
									>
										<template #prefix>
											<Plus class="h-4 w-4 stroke-1.5" />
										</template>
									</Button>
								</div>
							</div>
						</div>
					</template>
				</Popover>
			</Combobox>
		</div>
		<div v-if="values?.length" class="flex flex-wrap gap-2 mt-2">
			<div
				v-for="value in values"
				:key="value"
				class="inline-flex items-center gap-1.5 bg-surface-gray-2 text-ink-gray-7 px-2.5 py-1.5 rounded-md text-sm max-w-full"
			>
				<span class="break-all">
					{{ getLabel(value) }}
				</span>
				<X
					class="size-3.5 stroke-1.5 cursor-pointer text-ink-gray-6 hover:text-ink-gray-9 flex-shrink-0 ml-1"
					@click="removeValue(value)"
				/>
			</div>
		</div>
		<!-- <ErrorMessage class="mt-2 pl-2" v-if="error" :message="error" /> -->
	</div>
</template>

<script setup>
import {
	Combobox,
	ComboboxInput,
	ComboboxOptions,
	ComboboxOption,
} from '@headlessui/vue'
import { createResource, Popover, Button, call } from 'frappe-ui'
import { ref, computed, nextTick, useAttrs, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { X, Plus } from 'lucide-vue-next'

const props = defineProps({
	label: {
		type: String,
	},
	size: {
		type: String,
		default: 'sm',
	},
	doctype: {
		type: String,
		required: true,
	},
	filters: {
		type: Object,
		default: () => ({}),
	},
	validate: {
		type: Function,
		default: null,
	},
	errorMessage: {
		type: Function,
		default: (value) => `${value} is an Invalid value`,
	},
	required: {
		type: Boolean,
	},
})

const values = defineModel()
const attrs = useAttrs()
const emails = ref([])
const search = ref(null)
const error = ref(null)
const query = ref('')
const text = ref('')
const showOptions = ref(false)
const labelMap = ref({})

const getLabel = (val) => {
	return labelMap.value[val] || val
}

const selectedValue = computed({
	get: () => query.value || '',
	set: (val) => {
		query.value = ''
		if (val) {
			showOptions.value = false
		}
		if (val?.value) {
			if (val.description || val.label) {
				labelMap.value[val.value] = val.description || val.label
			}
			addValue(val.value)
		}
	},
})

watchDebounced(
	query,
	(val) => {
		val = val || ''
		if (text.value === val) return
		text.value = val
		reload(val)
	},
	{ debounce: 300, immediate: true }
)

const filterOptions = createResource({
	url: 'frappe.desk.search.search_link',
	method: 'POST',
	cache: [text.value, props.doctype],
	auto: true,
	params: {
		txt: text.value,
		doctype: props.doctype,
	},
})

const options = computed(() => {
	return filterOptions.data || []
})

watch(
	options,
	(newOptions) => {
		if (newOptions && Array.isArray(newOptions)) {
			newOptions.forEach((opt) => {
				if (opt.value) {
					labelMap.value[opt.value] = opt.description || opt.label || opt.value
				}
			})
		}
	},
	{ immediate: true, deep: true }
)

const fetchMissingLabels = (missingValues) => {
	if (!missingValues || !missingValues.length) return
	call('frappe.client.get_list', {
		doctype: props.doctype,
		filters: { name: ['in', missingValues] },
		fields: ['name', 'full_name', 'title'],
		limit_page_length: missingValues.length,
	})
		.then((res) => {
			if (res && Array.isArray(res)) {
				res.forEach((doc) => {
					const label = doc.full_name || doc.title || doc.name
					if (label) {
						labelMap.value[doc.name] = label
					}
				})
			}
		})
		.catch(() => {})
}

watch(
	() => values.value,
	(newValues) => {
		if (Array.isArray(newValues) && newValues.length) {
			const missing = newValues.filter((v) => v && !labelMap.value[v])
			if (missing.length) {
				fetchMissingLabels(missing)
			}
		}
	},
	{ immediate: true, deep: true }
)

function reload(val) {
	filterOptions.update({
		params: {
			txt: val,
			doctype: props.doctype,
		},
	})
	filterOptions.reload()
}

const addValue = (value) => {
	error.value = null
	if (value) {
		const splitValues = value.split(',')
		splitValues.forEach((value) => {
			value = value.trim()
			if (value) {
				// check if value is not already in the values array
				if (!values.value?.includes(value)) {
					// check if value is valid
					if (value && props.validate && !props.validate(value)) {
						error.value = props.errorMessage(value)
						return
					}
					// add value to values array
					if (!values.value) {
						values.value = [value]
					} else {
						values.value.push(value)
					}
					value = value.replace(value, '')
				}
			}
		})
		!error.value && (value = '')
	}
}

const removeValue = (value) => {
	values.value = values.value.filter((v) => v !== value)
}

const removeLastValue = () => {
	if (query.value) return

	let emailRef = emails.value[emails.value.length - 1]?.$el
	if (document.activeElement === emailRef) {
		values.value.pop()
		nextTick(() => {
			if (values.value.length) {
				emailRef = emails.value[emails.value.length - 1].$el
				emailRef?.focus()
			} else {
				setFocus()
			}
		})
	} else {
		emailRef?.focus()
	}
}

function setFocus() {
	search.value.$el.focus()
}

defineExpose({ setFocus })

const labelClasses = computed(() => {
	return [
		{
			sm: 'text-xs',
			md: 'text-base',
		}[props.size || 'sm'],
		'text-ink-gray-5',
	]
})
</script>
