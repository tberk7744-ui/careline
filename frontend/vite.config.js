import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Rasa server runs locally (rasa run --enable-api --cors "*");
// in Docker, nginx serves the build and proxies /webhooks/ to the rasa service.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/webhooks": "http://localhost:5005" } },
});
