import { defineConfig } from "vite";

// Vercel serves the site at the domain root. Data comes from public/data, written by `npm run data`.
export default defineConfig({ base: "/", build: { target: "es2022" } });
