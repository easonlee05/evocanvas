import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: 'react-vendor', test: /node_modules[\\/](react|react-dom|react-router|react-router-dom)[\\/]/ },
            { name: 'editor-vendor', test: /node_modules[\\/](@tiptap|prosemirror|tiptap-markdown|markdown-it)[\\/]/ },
            { name: 'markdown-vendor', test: /node_modules[\\/](react-markdown|remark|rehype|unified|mdast|hast|micromark)[\\/]/ },
            { name: 'canvas-vendor', test: /node_modules[\\/](roughjs|dagre|lucide-react|@phosphor-icons)[\\/]/ },
          ],
        },
      },
    },
  },
  server: {
    port: 4000,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  },
})
