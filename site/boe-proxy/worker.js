// Proxy mínimo para traer el articulado desde el navegador (sortea CORS).
// Reenvía solo rutas concretas de fuentes oficiales (BOE y EUR-Lex) y añade
// cabeceras CORS. Pensado para Cloudflare Workers (free tier).
//
// La demo lo consume vía: window.__BOE_PROXY__ = 'https://<tu-worker>.workers.dev'
// El cliente Pyodide pide `${proxy}${path}` donde path empieza por un prefijo permitido.

// Enrutado por prefijo de ruta -> host oficial permitido.
const ROUTES = [
  { prefix: '/datosabiertos/api/legislacion-consolidada', origin: 'https://www.boe.es' },
  { prefix: '/legal-content/', origin: 'https://eur-lex.europa.eu' },
];

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
    const route = ROUTES.find((r) => url.pathname.startsWith(r.prefix));
    if (!route) {
      return withCors(new Response('Path not allowed', { status: 403 }));
    }

    const target = route.origin + url.pathname + url.search;
    // El endpoint de bloque del BOE solo acepta XML; EUR-Lex sirve HTML.
    let accept = 'application/json, application/xml;q=0.9, */*;q=0.1';
    if (url.pathname.includes('/texto/bloque/')) accept = 'application/xml';
    else if (route.origin.includes('eur-lex')) accept = 'text/html';

    const upstream = await fetch(target, {
      headers: { Accept: accept, 'User-Agent': 'legal-expand-proxy' },
    });

    const body = await upstream.arrayBuffer();
    const passthrough = new Response(body, {
      status: upstream.status,
      headers: {
        'Content-Type': upstream.headers.get('Content-Type') || 'application/octet-stream',
        'Cache-Control': 'public, max-age=86400',
      },
    });
    return withCors(passthrough);
  },
};
