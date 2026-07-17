# Proxy BOE para la demo

La demo web ejecuta `legal-expand` en el navegador con Pyodide. La **detección**
de referencias BOE es 100% offline y no necesita nada. Pero **traer el texto real
de los artículos** (modo online) hace peticiones a `https://www.boe.es`, y el
navegador las bloquea por CORS. Este proxy resuelve ese caso.

## Qué hace

Reenvía únicamente rutas de la API pública de legislación consolidada del BOE
(`/datosabiertos/api/legislacion-consolidada...`) y añade cabeceras CORS. No
permite proxyar ninguna otra ruta ni host.

## Desplegar en Cloudflare Workers (free tier)

```bash
npm install -g wrangler
cd site/boe-proxy
wrangler deploy
```

Al terminar, Cloudflare da una URL tipo `https://legal-expand-boe-proxy.<cuenta>.workers.dev`.

## Activar en la web

Basta con exponer la URL del proxy antes de que cargue la demo. Por ejemplo,
añadiendo en `src/layouts/Base.astro` (o mediante variable de entorno en el build):

```html
<script is:inline>window.__BOE_PROXY__ = 'https://legal-expand-boe-proxy.tu-cuenta.workers.dev';</script>
```

Con eso, el selector «Online (traer artículos)» de la demo pasa a traer el texto
real de los artículos. Sin proxy configurado, la demo cae a la detección offline
y lo explica en pantalla (no rompe).

## Alternativas

El mismo contrato (GET del path del BOE, respuesta con CORS) se puede implementar
como función serverless de Vercel, Netlify o Deno Deploy si el hosting elegido ya
las ofrece; en ese caso apunta `window.__BOE_PROXY__` a esa ruta.
