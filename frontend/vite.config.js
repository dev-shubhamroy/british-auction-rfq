import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Forward API calls to FastAPI so the browser sees a single origin.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
