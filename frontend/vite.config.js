import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
    plugins: [react()],
    server: {
        // Proxy API calls to the local backend during development.
        // In production VITE_BACKEND_URL is set to the deployed backend URL.
        proxy: {
            "/jobs": { target: "http://localhost:8001", changeOrigin: true },
            "/health": { target: "http://localhost:8001", changeOrigin: true },
        },
    },
});
