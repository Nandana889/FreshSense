import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // The FastAPI CORS policy allows exactly http://localhost:5173, so the dev
    // server must fail loudly rather than silently move to another port.
    host: 'localhost',
    port: 5173,
    strictPort: true,
  },
});
