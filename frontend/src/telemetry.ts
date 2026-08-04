import posthog from 'posthog-js'
import { createResource } from 'frappe-ui'

type PosthogSettings = {
  posthog_project_id: string
  posthog_host: string
  enable_telemetry: boolean
  telemetry_site_age: number
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

// Posthog Settings
let posthogSettings = createResource({
  url: 'lms.lms.telemetry.get_posthog_settings',
  cache: 'posthog_settings',
  onSuccess: (ps: PosthogSettings) => initPosthog(ps),
})

const captureEvent = (event_name: string, data: Record<string, any> = {}) => {
	if (!isEnabled.value || !pulseProvider || !appName.value) return
	pulseProvider.capture(event_name, appName.value, data)
}

// Posthog Initialization
function initPosthog(ps: PosthogSettings) {
  if (!isTelemetryEnabled()) return

  posthog.init(ps.posthog_project_id, {
    api_host: ps.posthog_host,
    person_profiles: 'identified_only',
    autocapture: false,
    capture_pageview: true,
    capture_pageleave: true,
    enable_heatmaps: false,
    disable_session_recording: false,
    loaded: (ph) => {
      ph.identify(window.location.hostname)
    },
  })
}

// Posthog Functions
function capture(
  event: string,
  options: CaptureOptions = { data: { user: '' } },
) {
  if (!isTelemetryEnabled()) return
  posthog.capture(`lms_${event}`, options)
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

// Posthog Plugin
function posthogPlugin(app: any) {
    app.config.globalProperties.posthog = posthog
    if (!posthog.__loaded) posthogSettings.fetch()
}

export {
  posthog,
  posthogSettings,
  posthogPlugin,
  capture,
  startRecording,
  stopRecording,
}
