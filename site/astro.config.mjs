// @ts-check
import { defineConfig } from 'astro/config';

// Dominio de producción (Contabo/Coolify, con y sin www; canonical sin www).
export default defineConfig({
  site: 'https://legal-expand.686f6c61.dev',
  build: {
    inlineStylesheets: 'auto',
    // 'file' genera docs.html (sin redirección de barra final), como el resto del sitio.
    format: 'file',
  },
});
