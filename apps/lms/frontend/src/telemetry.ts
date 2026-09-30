import { call } from 'frappe-ui'
import { reactive, readonly, ref, type App } from 'vue'

declare global {
	interface Window {
		frappe: any
	}
}

type PulseProvider = {
	enabled: boolean
	init: () => Promise<void> | void
	capture: (
		event_name: string,
		app_name: string,
		data: Record<string, any>,
	) => void
}

type PulseBootConfig = {
	enabled?: boolean
	host?: string
	client_url?: string
	key?: string
	site?: string
	user?: string
	team?: string
	site_age?: number
}

let pulseProvider: PulseProvider | null = null

const appName = ref<string>()
const isEnabled = ref(false)

const captureEvent = (event_name: string, data: Record<string, any> = {}) => {
	if (!isEnabled.value || !pulseProvider || !appName.value) return
	pulseProvider.capture(event_name, appName.value, data)
}

export function useTelemetry() {
	return reactive({
		isEnabled: readonly(isEnabled),
		disable: () => {
			isEnabled.value = false
		},
		capture: captureEvent,
	})
}

async function loadPulseProvider(): Promise<PulseProvider | null> {
	try {
		const path = '../../../frappe/frappe/public/js/telemetry/pulse.js'
		const module = await import(/* @vite-ignore */ path)
		return module.pulse_provider as PulseProvider
	} catch (e) {
		console.warn(
			'Telemetry pulse provider could not be loaded. Telemetry will be disabled.',
			e,
		)
		return null
	}
}

function applyBootConfig(cfg: PulseBootConfig) {
	window.frappe ??= {}
	window.frappe.boot = {
		...(window.frappe.boot || {}),
		enable_telemetry: Boolean(cfg.enabled),
		telemetry_provider: cfg.enabled ? ['pulse'] : [],
		telemetry: cfg,
		telemetry_site_age: cfg.site_age,
	}
}

export const telemetryPlugin = {
	async install(app: App, options: { app_name: string }) {
		appName.value = options.app_name

		if (!appName.value) {
			console.warn(
				`Telemetry plugin installed without app_name.\n` +
					`To enable telemetry, please provide the app_name while installing the plugin:\n` +
					`app.use(telemetryPlugin, { app_name: 'your_app_name' })`,
			)
			return
		}

		let cfg: PulseBootConfig = { enabled: false }
		try {
			// Backends newer than this app's baseline expose boot_config. Gate on
			// is_enabled (present across versions) first so older Frappe backends
			// don't 417 on a missing endpoint just to discover telemetry is off.
			const enabled = await call(
				'frappe.utils.telemetry.pulse.client.is_enabled',
			)
			if (!enabled) return

			cfg = await call('frappe.utils.telemetry.pulse.client.boot_config')
		} catch (e) {
			// Older/misconfigured backends: keep telemetry off.
			return
		}

		if (!cfg?.enabled) return

		applyBootConfig(cfg)
		pulseProvider = await loadPulseProvider()
		if (!pulseProvider) return

		await pulseProvider.init()
		isEnabled.value = Boolean(pulseProvider.enabled)
	},
}

export default telemetryPlugin
