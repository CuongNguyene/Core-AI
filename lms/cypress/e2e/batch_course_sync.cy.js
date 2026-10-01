const batch = {
	name: 'BATCH-SYNC-UAT',
	title: 'Batch sync UAT',
	description: '',
	instructors: [],
	students: ['learner@example.com'],
	courses: [],
	start_date: '2030-01-01',
	end_date: '2030-01-31',
	start_time: '09:00:00',
	end_time: '17:00:00',
	certification: 0,
}

const courseOption = [{ label: 'Course sync UAT', value: 'COURSE-SYNC-UAT' }]

const mockBatchCourseRequests = () => {
	cy.intercept('POST', '**/api/method/lms.lms.api.get_user_info', {
		body: {
			message: {
				name: 'moderator@example.com',
				is_moderator: true,
				is_instructor: false,
				is_student: false,
				is_system_manager: false,
			},
		},
	}).as('getUser')
	cy.intercept('POST', '**/api/method/lms.lms.utils.get_batch_details', {
		body: { message: batch },
	}).as('getBatch')
	cy.intercept('POST', '**/api/method/lms.lms.utils.get_batch_courses', {
		body: { message: [] },
	}).as('getBatchCourses')
	cy.intercept('POST', '**/api/method/frappe.desk.search.search_link', {
		body: { message: courseOption },
	}).as('searchCourses')
	cy.intercept(
		'POST',
		'**/api/method/lms.lms.learning_assignment_api.add_course_to_batch',
		(request) => {
			expect(request.body).to.include({
				batch: batch.name,
				course: courseOption[0].value,
			})
			request.reply({ body: { message: { name: 'BATCH-COURSE-SYNC-UAT' } } })
		},
	).as('addBatchCourse')
	cy.intercept(
		'POST',
		'**/api/method/lms.lms.learning_assignment_api.preview_batch_course_sync',
		{
			body: {
				message: {
					existing_members: 1,
					learners_requiring_enrollment: 1,
					learners: ['learner@example.com'],
				},
			},
		},
	).as('previewBatchSync')
}

const addCourseToBatch = () => {
	cy.contains('button', 'Add').click()
	cy.get('[role="dialog"]').last().within(() => {
		cy.get('input').type(courseOption[0].label)
	})
	cy.wait('@searchCourses')
	cy.get('[id^="headlessui-combobox-option-"]')
		.contains(courseOption[0].label)
		.click()
	cy.get('[role="dialog"]').last().contains('button', 'Add').click()
	cy.wait('@addBatchCourse')
	cy.wait('@previewBatchSync')
}

describe('Batch course sync', () => {
	beforeEach(() => {
		cy.login()
		mockBatchCourseRequests()
		cy.visit(`/lms/batches/${batch.name}#courses`)
		cy.wait('@getUser')
		cy.wait('@getBatch')
		cy.wait('@getBatchCourses')
	})

	it('syncs existing learners after adding a course', () => {
		cy.intercept(
			'POST',
			'**/api/method/lms.lms.learning_assignment_api.sync_batch_course_existing_learners',
			(request) => {
				expect(request.body).to.include({
					batch: batch.name,
					course: courseOption[0].value,
					confirm: 1,
				})
				request.reply({
					body: {
						message: { created_enrollments: 1, created_items: 0, synced: true },
					},
				})
			},
		).as('syncLearners')

		addCourseToBatch()
		cy.contains('[role="dialog"]', 'Sync existing learners?').should('be.visible')
		cy.contains('[role="dialog"]', '1 learner(s) do not have an enrollment').should('be.visible')
		cy.contains('[role="dialog"] button', 'Sync learners').click()
		cy.wait('@syncLearners')
		cy.contains('Synced 1 learner enrollment(s) to the new course.').should('be.visible')
	})

	it('keeps existing learners unenrolled when sync is declined', () => {
		cy.intercept(
			'POST',
			'**/api/method/lms.lms.learning_assignment_api.sync_batch_course_existing_learners',
		).as('syncLearners')

		addCourseToBatch()
		cy.contains('[role="dialog"] button', 'Do not sync').click()
		cy.contains('Course added to batch without enrolling existing learners.').should('be.visible')
		cy.get('@syncLearners.all').should('have.length', 0)
	})
})
