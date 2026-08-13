import { Pencil } from 'lucide-vue-next'
import { createApp, h } from 'vue'
import AssessmentPlugin from '@/components/AssessmentPlugin.vue'
import AssignmentSubmission from '@/components/Assignment.vue'
import translationPlugin from '../translation'
import { usersStore } from '@/stores/user'
import { call } from 'frappe-ui'
import router from '@/router'

export class Assignment {
	constructor({ data, api, readOnly }) {
		this.data = data
		this.readOnly = readOnly
	}

	static get toolbox() {
		const app = createApp({
			render: () =>
				h(Pencil, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})

		const div = document.createElement('div')
		app.mount(div)

		return {
			title: __('assignments.assignment'),
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')
		if (Object.keys(this.data).length) {
			this.renderAssignment(this.data.assignment)
		} else {
			this.renderAssignmentModal()
		}
		return this.wrapper
	}

	renderAssignment(assignment) {
		if (this.readOnly) {
			const { userResource } = usersStore()
			call('frappe.client.get_value', {
				doctype: 'LMS Assignment Submission',
				filters: {
					assignment: assignment,
					member: userResource.data?.name,
				},
				fieldname: ['name'],
			}).then((data) => {
				let submission = data.name || 'new'
				// Mounted directly instead of via an <iframe> pointing at the
				// AssignmentSubmission page - that iframe was its own separate
				// document/JS realm, so frappe-ui's toast (a page-fixed
				// singleton) rendered clipped to the small iframe box instead
				// of the real page's bottom-right corner.
				this.wrapper.classList.add('w-full', 'h-[500px]', 'mb-4')
				const app = createApp(AssignmentSubmission, {
					assignmentID: assignment,
					submissionName: submission,
					showTitle: false,
				})
				app.provide('$user', userResource)
				app.use(translationPlugin)
				app.use(router)
				app.mount(this.wrapper)
			})
			return
		}
		call('frappe.client.get_value', {
			doctype: 'LMS Assignment',
			filters: {
				name: assignment,
			},
			fieldname: ['title'],
		}).then((data) => {
			this.wrapper.innerHTML = `<div class='border rounded-md p-4 text-center bg-surface-menu-bar mb-4'>
				<span class="font-medium">
					${__('assignments.assignmentLabel').format(data.title)}
				</span>
			</div>`
			return
		})
	}

	renderAssignmentModal() {
		if (this.readOnly) {
			return
		}
		const app = createApp(AssessmentPlugin, {
			type: 'assignment',
			onAddition: (assignment) => {
				this.data.assignment = assignment
				this.renderAssignment(assignment)
			},
		})
		app.use(translationPlugin)
		app.mount(this.wrapper)
	}

	save() {
		if (Object.keys(this.data).length === 0) return {}
		return {
			assignment: this.data.assignment,
		}
	}
}
