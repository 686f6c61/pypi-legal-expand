// @ts-check
import { defineConfig } from 'astro/config';

// Dominio de producción (Contabo/Coolify, con y sin www; canonical sin www).
export default defineConfig({
  site: 'https://legal-expand.686f6c61.dev',
  build: {
    inlineStylesheets: 'auto',
  },
});
