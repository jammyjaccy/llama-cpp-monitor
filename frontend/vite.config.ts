import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发时代理 API 到后端；生产构建产物由 FastAPI 静态托管
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5100,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
