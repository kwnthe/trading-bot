import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Allow connections from any IP
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://192.168.2.4:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_API_TARGET || 'http://192.168.2.4:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
