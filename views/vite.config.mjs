import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  define: { 'process.env.NODE_ENV': '"production"' },
  build: {
    outDir: fileURLToPath(new URL('./humanization', import.meta.url)),
    emptyOutDir: false,
    lib: {
      entry: fileURLToPath(new URL('./humanization/main.js', import.meta.url)),
      formats: ['iife'],
      name: 'HumanizationView',
      fileName: () => 'app.js',
    },
    rollupOptions: { output: { assetFileNames: 'style.css' } },
  },
});
