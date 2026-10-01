describe('AI Course Planning', () => {
	it('clarifies a new revision before confirming and resumes it after reload', () => {
		cy.login()

		let phase = 'initial'
		let clarifyCalls = 0

		cy.intercept('POST', '**/api/method/pai_frappe.api.create_course_authoring_request', {
			body: {
				message: {
					name: 'PAI-REQUEST-TEST-001',
					pai_request_id: 'course-authoring-request-test-001',
					status: 'DRAFT',
				},
			},
		}).as('createAuthoringRequest')
		cy.intercept('POST', '**/api/method/pai_frappe.api.get_course_authoring_request', {
			body: {
				message: {
					request: { name: 'PAI-REQUEST-TEST-001', title: 'Coaching fundamentals', status: 'DRAFT' },
					pai: { id: 'course-authoring-request-test-001', title: 'Coaching fundamentals', mode: 'GOAL_DRIVEN' },
				},
			},
		}).as('getAuthoringRequest')
		cy.intercept('POST', '**/api/method/pai_frappe.api.list_authoring_brief_revisions', (request) => {
			const revisions = phase === 'initial' || phase === 'needs-clarification'
				? [{
					id: 'authoring-brief-revision:test-001',
					request_id: 'course-authoring-request-test-001',
					version: 1,
					status: phase === 'needs-clarification' ? 'NEEDS_CLARIFICATION' : 'DRAFT',
					payload: {
						training_goal: 'Improve coaching conversations',
						desired_outcomes: ['Give actionable feedback'],
						prerequisites: [],
					},
					clarification: { readiness: 'DRAFT', questions: [] },
					created_at: '2026-09-30T00:00:00Z',
				}]
				: [{
					id: 'authoring-brief-revision:test-002',
					request_id: 'course-authoring-request-test-001',
					version: 2,
					status: phase === 'confirmed' ? 'CONFIRMED' : 'READY_FOR_CONFIRMATION',
					payload: {
						training_goal: 'Improve coaching conversations',
						desired_outcomes: ['Give actionable feedback'],
						prerequisites: [],
						learning_horizon: '30 days',
						expected_learning_effort: '2 hours per week',
						excluded_scope: [],
						emphasis: [],
					},
					clarification: { readiness: 'READY_FOR_CONFIRMATION', questions: [] },
					created_at: '2026-09-30T00:02:00Z',
					confirmed_at: phase === 'confirmed' ? '2026-09-30T00:03:00Z' : null,
				}]
			request.reply({ body: { message: revisions } })
		}).as('listBriefRevisions')
		cy.intercept('POST', '**/api/method/pai_frappe.api.clarify_authoring_brief', (request) => {
			clarifyCalls += 1
			phase = clarifyCalls > 1 ? 'ready' : 'needs-clarification'
			request.reply({
				delay: clarifyCalls > 1 ? 300 : 0,
				body: { message: { status: phase === 'ready' ? 'READY_FOR_CONFIRMATION' : 'NEEDS_CLARIFICATION' } },
			})
		}).as('clarifyBrief')
		cy.intercept('POST', '**/api/method/pai_frappe.api.revise_authoring_brief', (request) => {
			phase = 'revision-created'
			request.reply({ body: { message: { id: 'authoring-brief-revision:test-002', version: 2 } } })
		}).as('reviseBrief')
		cy.intercept('POST', '**/api/method/pai_frappe.api.confirm_authoring_brief', (request) => {
			phase = 'confirmed'
			request.reply({ body: { message: { status: 'CONFIRMED' } } })
		}).as('confirmBrief')
		cy.visit('/lms/ai-course-planning')
		cy.contains('AI Course Planning').should('be.visible')
		cy.get('label').contains('Title').parent().find('input').type('Coaching fundamentals')
		cy.get('label').contains('Training goal').parent().find('textarea').type('Improve coaching conversations')
		cy.contains('Create brief').click()
		cy.wait('@createAuthoringRequest')
		cy.url().should('include', '/lms/ai-course-planning/PAI-REQUEST-TEST-001')
		cy.wait('@getAuthoringRequest')
		cy.wait('@listBriefRevisions')
		cy.wait('@clarifyBrief')
		cy.get('[data-cy="revision-history-status"]').should('contain.text', 'Needs clarification')
		cy.contains('Save new revision').click()
		cy.wait('@reviseBrief')
		cy.wait('@listBriefRevisions')
		cy.contains('Confirm brief').should('be.disabled')
		cy.wait('@clarifyBrief')
		cy.get('[data-cy="revision-history-status"]').should('contain.text', 'Ready to confirm')
		cy.contains('Confirm brief').click()
		cy.wait('@confirmBrief')
		cy.wait('@listBriefRevisions')
		cy.contains('Confirmed revision 2').scrollIntoView().should('be.visible')
		cy.reload()
		cy.wait('@getAuthoringRequest')
		cy.wait('@listBriefRevisions')
		cy.contains('Confirmed revision 2').scrollIntoView().should('be.visible')
	})
})
