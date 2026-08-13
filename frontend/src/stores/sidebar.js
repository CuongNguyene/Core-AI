import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSidebar = defineStore('sidebar', () => {
	// Lesson.vue/SCORMChapter.vue force-collapse the sidebar on mount, but that
	// runs after the first paint. On a hard reload of a /learn/ page this would
	// otherwise flash the expanded sidebar for a frame before it snaps closed,
	// so seed the initial value from the URL instead of only localStorage.
	const isSidebarCollapsed = ref(window.location.pathname.includes('/learn/'))
	const isWebpagesCollapsed = ref(true)

	if (localStorage.getItem('isSidebarCollapsed')) {
		isSidebarCollapsed.value =
			isSidebarCollapsed.value ||
			JSON.parse(localStorage.getItem('isSidebarCollapsed'))
	}

	if (localStorage.getItem('isWebpagesCollapsed')) {
		isWebpagesCollapsed.value = JSON.parse(
			localStorage.getItem('isWebpagesCollapsed')
		)
	}

	return {
		isSidebarCollapsed,
		isWebpagesCollapsed,
	}
})
