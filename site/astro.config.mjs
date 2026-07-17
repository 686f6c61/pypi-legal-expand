// @ts-check
import { defineConfig } from 'astro/config';

// El dominio final se ajustará cuando se decida el hosting.
export default defineConfig({
  site: 'https://legal-expand.example.dev',
  build: {
    inlineStylesheets: 'auto',
  },
});
