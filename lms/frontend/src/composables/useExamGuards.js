import { call } from 'frappe-ui'

// Bundles the remaining "exam guard" signals for a timed quiz attempt:
// copy/cut/right-click are genuinely blocked (preventDefault); DevTools and
// Print Screen can only be detected, not blocked — there is no browser API
// that intercepts an OS-level screenshot, and blocking F12 via keydown is
// trivially bypassed through the browser menu, so neither is attempted.
// Every signal feeds the same onLog(count, eventType) callback as
// useVisibilityLog, so Quiz.vue shows one combined violation count with the
// specific action of the latest violation, rather than one banner per
// signal type (the full breakdown by event_type is still visible to staff
// in the log).
export function useExamGuards({ referenceDoctype, referenceName, onLog }) {
	let target = null
	let devtoolsInterval = null
	let sessionInterval = null
	let devtoolsOpen = false
	const DEVTOOLS_THRESHOLD = 160

	let currentCount = 0

	const log = (eventType, durationSeconds = 0) => {
		currentCount++
		if (onLog) onLog(currentCount, eventType)

		call('lms.lms.api.log_activity_event', {
			reference_doctype: referenceDoctype,
			reference_name: referenceName,
			duration_seconds: durationSeconds,
			event_type: eventType,
		}).then((data) => {
			if (data?.count !== undefined) {
				currentCount = data.count
				if (onLog) onLog(currentCount, eventType)
			}
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
			if (data?.count === undefined) return
			// Only attribute the "Concurrent Session" label when this poll is
			// what actually pushed the count up - otherwise a routine poll with
			// no new session would keep overwriting the banner's last-shown
			// action with "Concurrent Session" even though nothing just happened.
			const increased = data.count > currentCount
			currentCount = Math.max(currentCount, data.count)
			if (onLog) onLog(currentCount, increased ? 'Concurrent Session' : undefined)
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
