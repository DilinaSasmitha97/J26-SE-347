import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      // NL-to-SQL engine (FastAPI): /nl-api/api/v1/translate -> :8000/api/v1/translate
      '/nl-api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/nl-api/, '')
      },
      // SQLGlot inspection service: /sqlglot-api/inspect -> :8001/inspect
      '/sqlglot-api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/sqlglot-api/, '')
      }
    }
  }
});
