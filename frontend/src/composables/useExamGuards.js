import { call } from 'frappe-ui'

// Bundles the remaining "exam guard" signals for a timed quiz attempt:
// copy/cut/right-click are genuinely blocked (preventDefault); DevTools and
// Print Screen can only be detected, not blocked — there is no browser API
// that intercepts an OS-level screenshot, and blocking F12 via keydown is
// trivially bypassed through the browser menu, so neither is attempted.
// Every signal feeds the same onLog(count) callback as useVisibilityLog, so
// Quiz.vue shows one combined violation count rather than one banner per
// signal type (the exact event_type is still visible to staff in the log).
export function useExamGuards({ referenceDoctype, referenceName, onLog }) {
	let target = null
	let devtoolsInterval = null
	let sessionInterval = null
	let devtoolsOpen = false
	const DEVTOOLS_THRESHOLD = 160

	const log = (eventType, durationSeconds = 0) => {
		call('lms.lms.api.log_activity_event', {
			reference_doctype: referenceDoctype,
			reference_name: referenceName,
			duration_seconds: durationSeconds,
			event_type: eventType,
		}).then((data) => {
			if (onLog) onLog(data?.count)
		})
	}

	const blockAndLog = (eventType) => (e) => {
		e.preventDefault()
		log(eventType)
	}
	const onCopy = blockAndLog('Copy Attempt')
	const onContextMenu = blockAndLog('Right Click')

	const onKeyUp = (e) => {
		// Best-effort only: fires on Windows in most browsers, but the
		// macOS screenshot shortcut is an OS-level combo that never reaches
		// the page as a JS keyboard event at all.
		if (e.key === 'PrintScreen') log('Print Screen Attempt')
	}

	const checkDevtools = () => {
		// Heuristic: a docked devtools panel shrinks the viewport relative
		// to the outer window. Catches the common case, misses an
		// undocked/separate devtools window entirely — there's no reliable
		// cross-browser "devtools opened" event.
		const isOpen =
			window.outerWidth - window.innerWidth > DEVTOOLS_THRESHOLD ||
			window.outerHeight - window.innerHeight > DEVTOOLS_THRESHOLD
		if (isOpen && !devtoolsOpen) log('DevTools Opened')
		devtoolsOpen = isOpen
	}

	const checkConcurrentSessions = () => {
		call('lms.lms.api.check_concurrent_sessions', {
			reference_doctype: referenceDoctype,
			reference_name: referenceName,
		}).then((data) => {
			if (onLog) onLog(data?.count)
		})
	}

	const start = (el) => {
		target = el || document
		target.addEventListener('copy', onCopy)
		target.addEventListener('cut', onCopy)
		target.addEventListener('contextmenu', onContextMenu)
		document.addEventListener('keyup', onKeyUp)

		devtoolsOpen = false
		devtoolsInterval = setInterval(checkDevtools, 2000)

		sessionInterval = setInterval(checkConcurrentSessions, 60000)
		checkConcurrentSessions()
	}

	const stop = () => {
		if (target) {
			target.removeEventListener('copy', onCopy)
			target.removeEventListener('cut', onCopy)
			target.removeEventListener('contextmenu', onContextMenu)
		}
		document.removeEventListener('keyup', onKeyUp)
		clearInterval(devtoolsInterval)
		clearInterval(sessionInterval)
		target = null
	}

	return { start, stop }
}
