// TEMPORARY Frappe v15 compatibility shim for frappe-ui onboarding.
//
// The installed backend is Frappe v15, which does NOT ship the
// `frappe.onboarding` module (get_onboarding_status / update_user_onboarding_status).
// frappe-ui's useOnboarding() calls those endpoints; on this backend they fail
// with `ModuleNotFoundError`, surfacing a blocking red error toast for System
// Manager users (e.g. when the sidebar sets up onboarding on page load).
//
// This shim makes onboarding fail silently WITHOUT removing the feature:
//   - When ONBOARDING_SUPPORTED is true it delegates 1:1 to the real frappe-ui
//     implementation, so supported environments are unaffected.
//   - When false it returns a safe no-op object that never calls the backend,
//     while still invoking any caller-supplied callbacks so business flow is
//     unchanged.
//
// TO REMOVE after upgrading to a Frappe version that provides `frappe.onboarding`:
//   1. Delete this file.
//   2. Restore `import { useOnboarding } from 'frappe-ui/frappe'` in every file
//      that currently imports from '@/utils/onboardingCompat'.
//   3. Remove the `isOnboardingSupported()` early-return in
//      AppSidebar.setUpOnboarding().
import { ref } from 'vue'
import { useOnboarding as useFrappeOnboarding } from 'frappe-ui/frappe'

// Flip to true (or delete this shim) once the backend provides frappe.onboarding.
const ONBOARDING_SUPPORTED = false

export function isOnboardingSupported() {
	return ONBOARDING_SUPPORTED
}

const noop = () => {}

// Mirrors the shape returned by frappe-ui's useOnboarding(), but performs no
// network calls. Caller callbacks are still invoked (as the real impl does) so
// no business logic is skipped — only the backend sync is dropped.
function createNoopOnboarding() {
	return {
		steps: [],
		stepsCompleted: 0,
		totalSteps: 0,
		completedPercentage: 0,
		isOnboardingStepsCompleted: ref(true),
		updateOnboardingStep: (step, value = true, skipped = false, callback = null) =>
			callback?.(step, skipped),
		skip: (step, callback = null) => callback?.(step, true),
		skipAll: (callback = null) => callback?.(true),
		reset: (step, callback = null) => callback?.(step, false),
		resetAll: (callback = null) => callback?.(false),
		setUp: noop,
		syncStatus: noop,
	}
}

export function useOnboarding(appName) {
	if (isOnboardingSupported()) {
		return useFrappeOnboarding(appName)
	}
	return createNoopOnboarding()
}
