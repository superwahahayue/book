import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Frontend dev server proxies /api to the FastAPI backend on :8000,
// so the browser talks to a single origin during development.
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true, // 暴露到局域网，自动打印可访问的 Network 地址
    port: 5288,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Build artifacts land here so FastAPI (or Nginx) can serve them.
    outDir: 'dist',
    emptyOutDir: true,
  },
})
