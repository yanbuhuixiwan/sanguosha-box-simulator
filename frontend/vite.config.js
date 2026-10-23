import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 900,
    // 默认的 'modules' 目标会保留 ?. / ?? 等 ES2020 语法，
    // 在旧内核（360/QQ 浏览器的老版本、Chrome < 80）里会直接语法报错、
    // 整页白屏或黑屏。降到 es2018 换取更宽的浏览器兼容。
    target: 'es2018',
    cssTarget: 'chrome61',
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
