import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // Sources ES de dc.js : le bundle UMD lit d3.version, absent de D3 v7 (voir src/lib/dcCompat.js)
      dc: fileURLToPath(new URL("./node_modules/dc/src/index.js", import.meta.url))
    }
  },
  server: { port: 5173 }
});
