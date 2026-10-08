import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: { emptyOutDir: false },
  test: { environment: 'jsdom', setupFiles: './src/test-setup.js' },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL || 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
});
