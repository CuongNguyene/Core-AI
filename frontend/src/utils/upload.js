import AudioBlock from '@/components/AudioBlock.vue'
import VideoBlock from '@/components/VideoBlock.vue'
import UploadPlugin from '@/components/UploadPlugin.vue'
import { h, createApp, nextTick } from 'vue'
import { Upload as UploadIcon } from 'lucide-vue-next'
import { createDialog } from '@/utils/dialogs'
import translationPlugin from '../translation'

export class Upload {
	constructor({ data, api, readOnly, config }) {
		this.data = data
		this.readOnly = readOnly
		this.courseName = config?.courseName
	}

	static get toolbox() {
		const app = createApp({
			render: () =>
				h(UploadIcon, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})

		const div = document.createElement('div')
		app.mount(div)

		return {
			title: 'Upload',
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')

		if (this.data && this.data.file_url) {
			this.renderFile(this.data)
		} else {
			this.renderFileUploader()
		}

		return this.wrapper
	}

	mountApp(app) {
		this.currentApp?.unmount()
		this.wrapper.innerHTML = ''
		app.mount(this.wrapper)
		this.currentApp = app
	}

	renderFile(file) {
		if (this.isVideo(file.file_type)) {
			const app = createApp(VideoBlock, {
				file: file.file_url,
				readOnly: this.readOnly,
				quizzes: file.quizzes || [],
				saveQuizzes: (quizzes) => {
					if (this.readOnly) return
					this.data.quizzes = quizzes
				},
			})
			app.use(translationPlugin)
			app.config.globalProperties.$dialog = createDialog
			this.mountApp(app)
			return
		} else if (this.isAudio(file.file_type)) {
			const app = createApp(AudioBlock, {
				file: file.file_url,
			})
			this.mountApp(app)
			return
		} else if (file.file_type == 'PDF') {
			this.currentApp?.unmount()
			this.currentApp = null
			this.wrapper.innerHTML = `<iframe src="${
				window.location.origin
			}${encodeURI(
				file.file_url
			)}" width='100%' height='700px' class="mb-4" type="application/pdf"></iframe>`
			return
		} else {
			this.currentApp?.unmount()
			this.currentApp = null
			this.wrapper.innerHTML = `<img class="mb-4" src=${encodeURI(
				file.file_url
			)} width='100%'>`
			return
		}
	}

	renderFileUploader() {
		const app = createApp(UploadPlugin, {
			courseName: this.courseName,
			onFileUploaded: (file) => {
				this.data.file_url = file.file_url
				this.data.file_type = file.file_type
				nextTick(() => this.renderFile(file))
			},
		})
		app.use(translationPlugin)
		this.mountApp(app)
	}

	validate(savedData) {
		if (!savedData.file_url || !savedData.file_type) {
			return false
		}
		return true
	}

	save(blockContent) {
		return {
			file_url: this.data.file_url,
			file_type: this.data.file_type,
			quizzes: this.data.quizzes || [],
		}
	}

	isVideo(type) {
		return ['mov', 'mp4', 'avi', 'mkv', 'webm'].includes(type.toLowerCase())
	}

	isAudio(type) {
		return ['mp3', 'wav', 'ogg'].includes(type.toLowerCase())
	}
}
