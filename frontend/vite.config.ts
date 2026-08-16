import { defineConfig } from "vite";

// Output is committed to the add-on so the Supervisor never needs Node on the device.
// Filenames are deterministic to keep the committed diff readable.
export default defineConfig({
  base: "./",
  build: {
    outDir: "../private_source_manager/app/psm/static",
    emptyOutDir: true,
    target: "es2022",
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name].js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
});
