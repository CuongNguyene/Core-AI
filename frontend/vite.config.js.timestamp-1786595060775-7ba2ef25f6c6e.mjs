// vite.config.js
import { defineConfig } from "file:///workspace/development/frappe-bench/apps/lms/frontend/node_modules/vite/dist/node/index.js";
import vue from "file:///workspace/development/frappe-bench/apps/lms/frontend/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import path from "path";
import frappeui from "file:///workspace/development/frappe-bench/apps/lms/frontend/node_modules/frappe-ui/vite/index.js";
import { VitePWA } from "file:///workspace/development/frappe-bench/apps/lms/frontend/node_modules/vite-plugin-pwa/dist/index.js";
var __vite_injected_original_dirname = "/workspace/development/frappe-bench/apps/lms/frontend";
var vite_config_default = defineConfig({
  plugins: [
    frappeui({
      frappeProxy: true,
      lucideIcons: true,
      jinjaBootData: true,
      frappeTypes: {
        input: {}
      },
      buildConfig: {
        indexHtmlPath: "../lms/www/lms.html"
      }
    }),
    vue({
      script: {
        defineModel: true,
        propsDestructure: true
      }
    }),
    VitePWA({
      registerType: "autoUpdate",
      devOptions: {
        enabled: true
      },
      workbox: {
        cleanupOutdatedCaches: true,
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024
      },
      manifest: false
    })
  ],
  server: {
    host: "0.0.0.0",
    // Accept connections from any network interface
    allowedHosts: ["ps", "fs", "home"]
    // Explicitly allow this host
  },
  resolve: {
    alias: {
      "@": path.resolve(__vite_injected_original_dirname, "src"),
      "tailwind.config.js": path.resolve(__vite_injected_original_dirname, "tailwind.config.js")
    }
  },
  optimizeDeps: {
    include: [
      "feather-icons",
      "showdown",
      "engine.io-client",
      "tailwind.config.js",
      "interactjs",
      "highlight.js",
      "plyr"
    ]
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcuanMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvd29ya3NwYWNlL2RldmVsb3BtZW50L2ZyYXBwZS1iZW5jaC9hcHBzL2xtcy9mcm9udGVuZFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiL3dvcmtzcGFjZS9kZXZlbG9wbWVudC9mcmFwcGUtYmVuY2gvYXBwcy9sbXMvZnJvbnRlbmQvdml0ZS5jb25maWcuanNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL3dvcmtzcGFjZS9kZXZlbG9wbWVudC9mcmFwcGUtYmVuY2gvYXBwcy9sbXMvZnJvbnRlbmQvdml0ZS5jb25maWcuanNcIjtpbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tICd2aXRlJ1xuaW1wb3J0IHZ1ZSBmcm9tICdAdml0ZWpzL3BsdWdpbi12dWUnXG5pbXBvcnQgcGF0aCBmcm9tICdwYXRoJ1xuaW1wb3J0IGZyYXBwZXVpIGZyb20gJ2ZyYXBwZS11aS92aXRlJ1xuaW1wb3J0IHsgVml0ZVBXQSB9IGZyb20gJ3ZpdGUtcGx1Z2luLXB3YSdcblxuLy8gaHR0cHM6Ly92aXRlanMuZGV2L2NvbmZpZy9cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG5cdHBsdWdpbnM6IFtcblx0XHRmcmFwcGV1aSh7XG5cdFx0XHRmcmFwcGVQcm94eTogdHJ1ZSxcblx0XHRcdGx1Y2lkZUljb25zOiB0cnVlLFxuXHRcdFx0amluamFCb290RGF0YTogdHJ1ZSxcblx0XHRcdGZyYXBwZVR5cGVzOiB7XG5cdFx0XHRcdGlucHV0OiB7fSxcblx0XHRcdH0sXG5cdFx0XHRidWlsZENvbmZpZzoge1xuXHRcdFx0XHRpbmRleEh0bWxQYXRoOiAnLi4vbG1zL3d3dy9sbXMuaHRtbCcsXG5cdFx0XHR9LFxuXHRcdH0pLFxuXHRcdHZ1ZSh7XG5cdFx0XHRzY3JpcHQ6IHtcblx0XHRcdFx0ZGVmaW5lTW9kZWw6IHRydWUsXG5cdFx0XHRcdHByb3BzRGVzdHJ1Y3R1cmU6IHRydWUsXG5cdFx0XHR9LFxuXHRcdH0pLFxuXHRcdFZpdGVQV0Eoe1xuXHRcdFx0cmVnaXN0ZXJUeXBlOiAnYXV0b1VwZGF0ZScsXG5cdFx0XHRkZXZPcHRpb25zOiB7XG5cdFx0XHRcdGVuYWJsZWQ6IHRydWUsXG5cdFx0XHR9LFxuXHRcdFx0d29ya2JveDoge1xuXHRcdFx0XHRjbGVhbnVwT3V0ZGF0ZWRDYWNoZXM6IHRydWUsXG5cdFx0XHRcdG1heGltdW1GaWxlU2l6ZVRvQ2FjaGVJbkJ5dGVzOiA1ICogMTAyNCAqIDEwMjQsXG5cdFx0XHR9LFxuXHRcdFx0bWFuaWZlc3Q6IGZhbHNlLFxuXHRcdH0pLFxuXHRdLFxuXHRzZXJ2ZXI6IHtcblx0XHRob3N0OiAnMC4wLjAuMCcsIC8vIEFjY2VwdCBjb25uZWN0aW9ucyBmcm9tIGFueSBuZXR3b3JrIGludGVyZmFjZVxuXHRcdGFsbG93ZWRIb3N0czogWydwcycsICdmcycsICdob21lJ10sIC8vIEV4cGxpY2l0bHkgYWxsb3cgdGhpcyBob3N0XG5cdH0sXG5cdHJlc29sdmU6IHtcblx0XHRhbGlhczoge1xuXHRcdFx0J0AnOiBwYXRoLnJlc29sdmUoX19kaXJuYW1lLCAnc3JjJyksXG5cdFx0XHQndGFpbHdpbmQuY29uZmlnLmpzJzogcGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgJ3RhaWx3aW5kLmNvbmZpZy5qcycpLFxuXHRcdH0sXG5cdH0sXG5cdG9wdGltaXplRGVwczoge1xuXHRcdGluY2x1ZGU6IFtcblx0XHRcdCdmZWF0aGVyLWljb25zJyxcblx0XHRcdCdzaG93ZG93bicsXG5cdFx0XHQnZW5naW5lLmlvLWNsaWVudCcsXG5cdFx0XHQndGFpbHdpbmQuY29uZmlnLmpzJyxcblx0XHRcdCdpbnRlcmFjdGpzJyxcblx0XHRcdCdoaWdobGlnaHQuanMnLFxuXHRcdFx0J3BseXInLFxuXHRcdF0sXG5cdH0sXG59KVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUFpVixTQUFTLG9CQUFvQjtBQUM5VyxPQUFPLFNBQVM7QUFDaEIsT0FBTyxVQUFVO0FBQ2pCLE9BQU8sY0FBYztBQUNyQixTQUFTLGVBQWU7QUFKeEIsSUFBTSxtQ0FBbUM7QUFPekMsSUFBTyxzQkFBUSxhQUFhO0FBQUEsRUFDM0IsU0FBUztBQUFBLElBQ1IsU0FBUztBQUFBLE1BQ1IsYUFBYTtBQUFBLE1BQ2IsYUFBYTtBQUFBLE1BQ2IsZUFBZTtBQUFBLE1BQ2YsYUFBYTtBQUFBLFFBQ1osT0FBTyxDQUFDO0FBQUEsTUFDVDtBQUFBLE1BQ0EsYUFBYTtBQUFBLFFBQ1osZUFBZTtBQUFBLE1BQ2hCO0FBQUEsSUFDRCxDQUFDO0FBQUEsSUFDRCxJQUFJO0FBQUEsTUFDSCxRQUFRO0FBQUEsUUFDUCxhQUFhO0FBQUEsUUFDYixrQkFBa0I7QUFBQSxNQUNuQjtBQUFBLElBQ0QsQ0FBQztBQUFBLElBQ0QsUUFBUTtBQUFBLE1BQ1AsY0FBYztBQUFBLE1BQ2QsWUFBWTtBQUFBLFFBQ1gsU0FBUztBQUFBLE1BQ1Y7QUFBQSxNQUNBLFNBQVM7QUFBQSxRQUNSLHVCQUF1QjtBQUFBLFFBQ3ZCLCtCQUErQixJQUFJLE9BQU87QUFBQSxNQUMzQztBQUFBLE1BQ0EsVUFBVTtBQUFBLElBQ1gsQ0FBQztBQUFBLEVBQ0Y7QUFBQSxFQUNBLFFBQVE7QUFBQSxJQUNQLE1BQU07QUFBQTtBQUFBLElBQ04sY0FBYyxDQUFDLE1BQU0sTUFBTSxNQUFNO0FBQUE7QUFBQSxFQUNsQztBQUFBLEVBQ0EsU0FBUztBQUFBLElBQ1IsT0FBTztBQUFBLE1BQ04sS0FBSyxLQUFLLFFBQVEsa0NBQVcsS0FBSztBQUFBLE1BQ2xDLHNCQUFzQixLQUFLLFFBQVEsa0NBQVcsb0JBQW9CO0FBQUEsSUFDbkU7QUFBQSxFQUNEO0FBQUEsRUFDQSxjQUFjO0FBQUEsSUFDYixTQUFTO0FBQUEsTUFDUjtBQUFBLE1BQ0E7QUFBQSxNQUNBO0FBQUEsTUFDQTtBQUFBLE1BQ0E7QUFBQSxNQUNBO0FBQUEsTUFDQTtBQUFBLElBQ0Q7QUFBQSxFQUNEO0FBQ0QsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
