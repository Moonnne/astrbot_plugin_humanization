import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  define: { 'process.env.NODE_ENV': '"production"' },
  build: {
    outDir: fileURLToPath(new URL('./humanization', import.meta.url)),
    emptyOutDir: false,
    minify: false,
    cssMinify: false,
    cssCodeSplit: false,
    rollupOptions: {
      input: fileURLToPath(new URL('./humanization/main.js', import.meta.url)),
      output: {
        format: 'es',
        entryFileNames: 'app.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'style.css',
        manualChunks(id) { if (id.includes('node_modules')) return 'vendor'; },
      },
    },
  },
});
