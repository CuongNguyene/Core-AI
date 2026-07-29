import { watch } from 'vue'
import { usersStore } from './stores/user'
import translations from './translations'

export default function translationPlugin(app) {
	app.config.globalProperties.__ = translate
	window.__ = translate
	loadLanguage()
}

function getTranslation(messages, key) {
	if (typeof messages?.[key] !== 'undefined') {
		return messages[key]
	}

	let current = messages
	for (const part of key.split('.')) {
		if (!current || typeof current !== 'object') {
			return undefined
		}
		current = current[part]
	}

	return typeof current === 'string' ? current : undefined
}

function translate(message) {
	if (typeof message !== 'string' || !message) {
		return message
	}

	let translatedMessages = window.translatedMessages || {}
	let translatedMessage = getTranslation(translatedMessages, message) || message

	const hasPlaceholders = /{\d+}/.test(translatedMessage)
	if (!hasPlaceholders) {
		return translatedMessage
	}
	return {
		format: function (...args) {
			return translatedMessage.replace(
				/{(\d+)}/g,
				function (match, number) {
					return typeof args[number] != 'undefined'
						? args[number]
						: match
				}
			)
		},
	}
}

function loadLanguage() {
	// The user's language preference lives on the Frappe User doctype (see
	// the "Language" field in EditProfile.vue), read here from the same
	// `userResource` the rest of the app already fetches via `usersStore`
	// (Pinia stores are singletons, so this doesn't trigger a second
	// request). Picking a new language triggers a full page reload
	// (EditProfile.vue), so a one-time lookup at boot is enough — no need
	// to react to later changes within the same session.
	const { userResource } = usersStore()

	const applyLanguage = (user) => {
		window.translatedMessages = (user?.language && translations[user.language]) || {}
	}

	if (userResource.data) {
		applyLanguage(userResource.data)
		return
	}

	const stopWatch = watch(
		() => userResource.data,
		(data) => {
			if (data) {
				applyLanguage(data)
				stopWatch()
			}
		}
	)
}
