// Bundles every ./translations/*.json file at build time into
// { [langCode]: { sourceText: translatedText } }, e.g. translations.vi.
// Drop a new <lang-code>.json file in this folder to add a language — no
// other code changes needed.
const modules = import.meta.glob('./*.json', { eager: true })

const translations = {}
for (const path in modules) {
	const match = path.match(/\.\/([a-zA-Z-]+)\.json$/)
	if (match) {
		translations[match[1]] = modules[path].default || modules[path]
	}
}

export default translations
