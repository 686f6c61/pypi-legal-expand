// Proxy para DESARROLLO LOCAL. Reenvía a las fuentes oficiales (BOE y EUR-Lex)
// añadiendo CORS, para probar el modo online de la demo sin desplegar el Worker.
// No usar en producción.
//
//   node boe-proxy/local-server.cjs   ->  http://localhost:8787
//
const http = require('http');
const https = require('https');

const PORT = process.env.BOE_PROXY_PORT || 8787;

// Enrutado por prefijo de ruta -> host oficial permitido.
const ROUTES = [
  { prefix: '/datosabiertos/api/legislacion-consolidada', host: 'www.boe.es' },
  { prefix: '/legal-content/', host: 'eur-lex.europa.eu' },
];

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Accept',
};

http
  .createServer((req, res) => {
    if (req.method === 'OPTIONS') {
      res.writeHead(204, CORS);
      return res.end();
    }
    const url = new URL(req.url, 'http://localhost');
    const route = ROUTES.find((r) => url.pathname.startsWith(r.prefix));
    if (!route) {
      res.writeHead(403, CORS);
      return res.end('Path not allowed');
    }
    // El endpoint de bloque del BOE solo acepta XML; EUR-Lex sirve HTML.
    let accept = 'application/json, application/xml;q=0.9, */*;q=0.1';
    if (url.pathname.includes('/texto/bloque/')) accept = 'application/xml';
    else if (route.host === 'eur-lex.europa.eu') accept = 'text/html';

    https
      .get(
        {
          host: route.host,
          path: url.pathname + url.search,
          headers: { Accept: accept, 'User-Agent': 'legal-expand-local-proxy' },
        },
        (upstream) => {
          const chunks = [];
          upstream.on('data', (c) => chunks.push(c));
          upstream.on('end', () => {
            res.writeHead(upstream.statusCode || 200, {
              ...CORS,
              'Content-Type': upstream.headers['content-type'] || 'application/octet-stream',
            });
            res.end(Buffer.concat(chunks));
          });
        }
      )
      .on('error', (err) => {
        res.writeHead(502, CORS);
        res.end('Upstream error: ' + String(err));
      });
  })
  .listen(PORT, () => {
    console.log('Proxy local (BOE + EUR-Lex) en http://localhost:' + PORT);
  });
