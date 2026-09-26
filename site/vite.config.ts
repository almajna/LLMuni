import { defineConfig } from "vite";

// Static site at the domain root. Data comes from public/data, written by `npm run data` (committed, so hosts
// can build without Python). The map libraries ship as their own chunks so a data-only update stays small.
export default defineConfig({
  base: "/",
  build: {
    target: "es2022",
    chunkSizeWarningLimit: 1400,
    rollupOptions: {
      output: {
        manualChunks: { maplibre: ["maplibre-gl"], deck: ["@deck.gl/core", "@deck.gl/layers", "@deck.gl/geo-layers", "@deck.gl/mapbox"] },
      },
    },
  },
});
