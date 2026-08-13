import { call } from 'frappe-ui'

// Logs completed tab-hidden intervals (via the Page Visibility API) against a
// quiz attempt or a lesson. This is a soft deterrence/audit signal, not an
// enforcement mechanism — start()/stop() are exposed rather than tied to the
// component lifecycle, since callers only want the listener active during a
// specific window (an active quiz attempt, or a lesson being viewed), and
// referenceName (e.g. a quiz attempt name) is often only known partway
// through that window.
export function useVisibilityLog({ referenceDoctype, referenceName, minDurationSec = 2, onLog }) {
	let hiddenAt = null
	let localCount = 0

	const onVisibilityChange = () => {
		if (document.hidden) {
			hiddenAt = Date.now()
			return
		}

		if (!hiddenAt) return
		const duration = (Date.now() - hiddenAt) / 1000
		hiddenAt = null
		if (duration < minDurationSec) return

		localCount++
		if (onLog) onLog(localCount, duration)

		call('lms.lms.api.log_activity_event', {
			reference_doctype: referenceDoctype,
			reference_name: referenceName,
			duration_seconds: duration,
		}).then((data) => {
			if (data?.count !== undefined) {
				localCount = Math.max(localCount, data.count)
				if (onLog) onLog(localCount, duration)
			}
		})
	}

	const start = () => {
		hiddenAt = null
		document.addEventListener('visibilitychange', onVisibilityChange)
	}

	const stop = () => {
		document.removeEventListener('visibilitychange', onVisibilityChange)
		hiddenAt = null
	}

	return { start, stop }
}
