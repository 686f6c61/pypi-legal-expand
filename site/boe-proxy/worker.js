// Proxy mínimo para traer artículos del BOE desde el navegador (sortea CORS).
// Reenvía únicamente rutas de la API de legislación consolidada del BOE y
// añade cabeceras CORS. Pensado para Cloudflare Workers (free tier).
//
// La demo lo consume vía: window.__BOE_PROXY__ = 'https://<tu-worker>.workers.dev'
// El cliente Pyodide pide `${proxy}${path}` donde path empieza por el prefijo permitido.

const BOE_ORIGIN = 'https://www.boe.es';
const ALLOWED_PREFIX = '/datosabiertos/api/legislacion-consolidada';

function withCors(response) {
  const headers = new Headers(response.headers);
  headers.set('Access-Control-Allow-Origin', '*');
  headers.set('Access-Control-Allow-Methods', 'GET, OPTIONS');
  headers.set('Access-Control-Allow-Headers', 'Accept');
  return new Response(response.body, { status: response.status, headers });
}

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return withCors(new Response(null, { status: 204 }));
    }
    if (request.method !== 'GET') {
      return withCors(new Response('Method not allowed', { status: 405 }));
    }
    // Solo se permite proxyar la API pública de legislación consolidada.
    if (!url.pathname.startsWith(ALLOWED_PREFIX)) {
      return withCors(new Response('Path not allowed', { status: 403 }));
    }

    const target = BOE_ORIGIN + url.pathname + url.search;
    // El endpoint de bloque del BOE solo acepta XML; el resto sirve JSON.
    const accept = url.pathname.includes('/texto/bloque/')
      ? 'application/xml'
      : 'application/json, application/xml;q=0.9, */*;q=0.1';
    const upstream = await fetch(target, {
      headers: { Accept: accept, 'User-Agent': 'legal-expand-boe-proxy' },
    });

    const body = await upstream.arrayBuffer();
    const passthrough = new Response(body, {
      status: upstream.status,
      headers: {
        'Content-Type': upstream.headers.get('Content-Type') || 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=86400',
      },
    });
    return withCors(passthrough);
  },
};
