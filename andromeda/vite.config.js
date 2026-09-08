import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        landing: resolve(__dirname, 'landing.html'),
        app: resolve(__dirname, 'app.html'),
      },
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
  },
});
