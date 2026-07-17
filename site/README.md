# legal-expand · landing y demo

Sitio estático (Astro) con una demo interactiva que ejecuta el paquete real
`legal-expand` en el navegador mediante **Pyodide**. Vive en la rama `landing`.

## Desarrollo

```bash
cd site
npm install
npm run dev      # servidor de desarrollo en http://localhost:4321
npm run build    # genera dist/ estático
npm run preview  # sirve dist/ para comprobar el build
```

## Cómo funciona la demo

- `public/scripts/demo.js` carga Pyodide desde el CDN, instala el wheel de
  `public/wheels/legal_expand-*.whl` con micropip y llama a las funciones reales
  del paquete (`expandir_siglas`, `auditar_texto`, `enriquecer_boe`…).
- El wheel se construye desde el propio repositorio, así que la demo refleja el
  código actual, no solo el publicado en PyPI. Para regenerarlo:

  ```bash
  python -m build --wheel        # desde la raíz del paquete
  cp dist/legal_expand-*.whl site/public/wheels/
  ```

- Los edge cases de la sección «Casos límite» están en `src/data/edgecases.json`
  y se generan ejecutando el paquete real (no son textos inventados).

## Traer artículos del BOE (modo online)

La detección de referencias es offline. Traer el texto de los artículos necesita
un proxy que sortee CORS: ver `boe-proxy/`. Una vez desplegado, se activa con
`window.__BOE_PROXY__`.

## Despliegue

El build es estático (`dist/`), válido para cualquier hosting de estáticos
(Cloudflare Pages, Vercel, Netlify, GitHub Pages…). El dominio final se fija en
`astro.config.mjs` (`site`).
