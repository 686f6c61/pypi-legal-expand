// Demo interactiva: ejecuta el paquete real legal-expand en el navegador con
// Pyodide. Flujo simple: el usuario elige un escrito jurídico y ve tres cosas —
// siglas traducidas, contenido de los artículos (BOE) y referencias con enlaces
// (BOE y EUR-Lex).
import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.mjs';

const WHEEL_URL = '/wheels/legal_expand-1.6.0-py3-none-any.whl';
// Proxy opcional para traer los artículos del BOE (sortea CORS). Sin proxy, la
// demo detecta y enlaza, pero no puede traer el texto de los artículos.
const BOE_PROXY = (typeof window !== 'undefined' && window.__BOE_PROXY__) || '';

const els = {
  dot: document.getElementById('runtime-dot'),
  status: document.getElementById('runtime-status'),
  run: document.getElementById('demo-run'),
  text: document.getElementById('demo-text'),
  outExpand: document.getElementById('out-expand'),
  outArticles: document.getElementById('out-articles'),
  outRefs: document.getElementById('out-refs'),
};

let pyodide = null;

const PY_HELPERS = `
import json
import html as _html
import re as _re
from legal_expand import expandir_siglas, enriquecer_boe
from legal_expand.types import BOEOptions


def _apartados(texto):
    # Separa el articulado en apartados numerados para que se lea bien.
    partes = _re.split(r'\\s+(?=\\d{1,2}\\.\\s+[A-ZÁÉÍÓÚÑ])', texto.strip())
    if len(partes) <= 1:
        return f'<p>{_html.escape(texto)}</p>'
    return ''.join(f'<p>{_html.escape(p.strip())}</p>' for p in partes)


def _boe_report(text, proxy):
    if proxy:
        from legal_expand.boe import BOEClient
        from pyodide.http import open_url

        def _transport(url, accept):
            return open_url(url).read()

        opts = BOEOptions(mode='online', include_unit_text=True, max_retries=0)
        try:
            return enriquecer_boe(text, opts, client=BOEClient(opts, base_url=proxy, transport=_transport))
        except Exception:
            pass
    return enriquecer_boe(text, BOEOptions(mode='offline'))


def le_case(text, proxy):
    expanded = expandir_siglas(text)
    report = _boe_report(text, proxy)

    articulos = []
    filas = []
    for ref in report.references:
        for bloque in ref.unit_blocks:
            if bloque.text:
                norma = ref.norm.title if ref.norm else ''
                articulos.append(
                    '<details><summary>' + _html.escape(bloque.title)
                    + '<span class="art-norm">' + _html.escape(norma) + '</span></summary>'
                    + '<div class="art-body">' + _apartados(bloque.text) + '</div></details>'
                )
        if ref.norm is not None:
            fuente = 'EUR-Lex' if ref.norm.source == 'eur-lex' else 'BOE'
            clase = 'eurlex' if fuente == 'EUR-Lex' else 'boe'
            filas.append(
                '<tr><td>' + _html.escape(ref.original_text) + '</td>'
                + '<td>' + _html.escape(ref.norm.title) + '</td>'
                + '<td><span class="src src-' + clase + '">' + fuente + '</span></td>'
                + '<td><a href="' + _html.escape(ref.norm.url, quote=True)
                + '" target="_blank" rel="noopener">abrir</a></td></tr>'
            )

    articulos_html = ''.join(articulos) or (
        '<p class="muted">Este escrito no cita artículos con texto recuperable en el BOE.</p>'
    )
    refs_html = (
        '<table><thead><tr><th>Referencia</th><th>Norma</th><th>Fuente</th><th>Enlace</th></tr></thead>'
        '<tbody>' + ''.join(filas) + '</tbody></table>'
    ) if filas else '<p class="muted">Sin referencias legales detectadas.</p>'

    return json.dumps({'expanded': expanded, 'articulos': articulos_html, 'refs': refs_html}, ensure_ascii=False)
`;

function setStatus(state, text) {
  if (els.dot) els.dot.className = 'runtime-dot is-' + state;
  if (els.status) els.status.textContent = text;
}

async function runDemo() {
  if (!pyodide) return;
  els.run.disabled = true;
  els.outExpand.textContent = 'Analizando…';
  els.outArticles.innerHTML = '<span class="placeholder">…</span>';
  els.outRefs.innerHTML = '<span class="placeholder">…</span>';
  try {
    pyodide.globals.set('demo_text', els.text.value);
    pyodide.globals.set('demo_proxy', BOE_PROXY);
    const raw = await pyodide.runPythonAsync('le_case(demo_text, demo_proxy)');
    const payload = JSON.parse(raw);
    els.outExpand.textContent = payload.expanded; // texto plano, seguro
    els.outArticles.innerHTML = payload.articulos; // HTML del paquete/escapado
    els.outRefs.innerHTML = payload.refs;
  } catch (err) {
    els.outExpand.textContent = 'Error: ' + (err && err.message ? err.message : String(err));
  } finally {
    els.run.disabled = false;
  }
}

function selectDoc(button) {
  const list = window.__LEGAL_EXPAND_EXAMPLES__ || [];
  const example = list.find((e) => e.id === button.dataset.doc);
  document.querySelectorAll('#demo-docs button').forEach((b) =>
    b.setAttribute('aria-selected', String(b === button)));
  if (example) els.text.value = example.text;
  if (pyodide) runDemo();
}

function wireUI() {
  document.querySelectorAll('#demo-docs button').forEach((b) => {
    b.addEventListener('click', () => selectDoc(b));
  });
  els.run.addEventListener('click', runDemo);
}

async function boot() {
  wireUI();
  try {
    setStatus('loading', 'Cargando Python…');
    pyodide = await loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/' });
    setStatus('loading', 'Instalando legal-expand…');
    await pyodide.loadPackage('micropip');
    const micropip = pyodide.pyimport('micropip');
    await micropip.install(new URL(WHEEL_URL, window.location.origin).href);
    pyodide.runPython(PY_HELPERS);
    setStatus('ready', 'Python listo · paquete real');
    els.run.disabled = false;
    runDemo();
  } catch (err) {
    setStatus('error', 'No se pudo cargar Python');
    els.outExpand.textContent = 'Error al iniciar Pyodide: ' + (err && err.message ? err.message : String(err));
  }
}

boot();
