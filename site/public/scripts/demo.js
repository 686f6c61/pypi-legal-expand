// Demo interactiva: ejecuta el paquete real legal-expand en el navegador con Pyodide.
import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.mjs';

const WHEEL_URL = '/wheels/legal_expand-1.6.0-py3-none-any.whl';
// Proxy opcional para sortear CORS al traer artículos del BOE (modo online).
// Configúralo en el hosting con: window.__BOE_PROXY__ = 'https://tu-proxy/boe';
// Acepta el patrón con '{path}' o simple concatenación proxy + path.
const BOE_PROXY = (typeof window !== 'undefined' && window.__BOE_PROXY__) || '';

const els = {
  dot: document.getElementById('runtime-dot'),
  status: document.getElementById('runtime-status'),
  run: document.getElementById('demo-run'),
  text: document.getElementById('demo-text'),
  output: document.getElementById('demo-output'),
  meta: document.getElementById('demo-meta'),
  format: document.getElementById('demo-format'),
  boeMode: document.getElementById('demo-boe-mode'),
  first: document.getElementById('demo-first'),
  renderToggle: document.getElementById('render-toggle'),
  copyOut: document.getElementById('demo-copy-out'),
  formatGroup: document.querySelector('[data-control="format"]'),
  boeGroup: document.querySelector('[data-control="boe-mode"]'),
};

let pyodide = null;
let mode = 'expand';
let lastHtml = null; // salida HTML pendiente de togglear entre código/vista

const PY_HELPERS = `
import json
import html as _html
from legal_expand import (
    expandir_siglas, auditar_texto,
    enriquecer_boe, boe_report_to_html, ExpansionOptions,
)
from legal_expand.core.engine import generar_glosario
from legal_expand.types import BOEOptions

def _opts(fmt, only_first):
    return ExpansionOptions(format=fmt, expand_only_first=only_first)

def le_expand(text, fmt, only_first):
    result = expandir_siglas(text, _opts(fmt, only_first))
    stats = expandir_siglas(text, _opts('structured', only_first))
    if fmt == 'structured':
        output = result.to_json(indent=2)
    else:
        output = result if isinstance(result, str) else result.expanded_text
    return json.dumps({
        'output': output,
        'is_html': fmt == 'html',
        'meta': {
            'siglas': stats.stats.total_acronyms_found,
            'expandidas': stats.stats.total_expanded,
            'ambiguas': stats.stats.ambiguous_not_expanded,
        },
    }, ensure_ascii=False)

def _table(headers, rows_html):
    head = "".join(f"<th>{_html.escape(h)}</th>" for h in headers)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{rows_html}</tbody></table>"

def le_audit(text, only_first):
    report = auditar_texto(text, _opts('plain', only_first))
    rows = "".join(
        f"<tr><td>{_html.escape(e.acronym)}</td><td>{_html.escape(e.expansion)}</td><td>{e.count}</td></tr>"
        for e in report.glossary
    ) or '<tr><td colspan="3">Sin siglas conocidas</td></tr>'
    unknown = ""
    if report.unknown_acronyms:
        chips = " ".join(f"<span class='chip'>{_html.escape(u.acronym)}</span>" for u in report.unknown_acronyms)
        unknown = f"<h4>Desconocidas</h4><div class='chips'>{chips}</div>"
    out = "<div class='report'><h4>Glosario</h4>" + _table(['Sigla', 'Significado', 'Apariciones'], rows) + unknown + "</div>"
    return json.dumps({'output': out, 'render_html': True, 'meta': {
        'detectadas': report.stats.total_detected,
        'conocidas': report.stats.total_known,
        'desconocidas': report.stats.total_unknown,
    }}, ensure_ascii=False)

def le_glossary(text):
    glossary = generar_glosario(text)
    if not glossary:
        return json.dumps({'output': "<p class='muted'>Sin siglas conocidas.</p>", 'render_html': True, 'meta': {}}, ensure_ascii=False)
    rows = "".join(
        f"<tr><td>{_html.escape(e.acronym)}</td><td>{_html.escape(e.expansion)}</td><td>{e.count}</td></tr>"
        for e in glossary
    )
    out = _table(['Sigla', 'Significado', 'Apariciones'], rows)
    return json.dumps({'output': out, 'render_html': True, 'meta': {'siglas': len(glossary)}}, ensure_ascii=False)

def _boe_payload(report):
    return json.dumps({'output': boe_report_to_html(report), 'render_html': True, 'meta': {
        'detectadas': report.stats.total_detected,
        'resueltas': report.stats.total_resolved,
        'ambiguas': report.stats.total_ambiguous,
    }}, ensure_ascii=False)

def le_boe_detect(text):
    # Nivel 1: detección offline (nombre + norma + URL oficial), sin red.
    report = enriquecer_boe(text, BOEOptions(mode='offline'))
    return _boe_payload(report)

def le_boe_online(text, proxy, full):
    # Niveles 2 y 3: consulta al BOE mediante el transporte inyectable del
    # paquete. full=True trae además el texto íntegro del artículo.
    from legal_expand.boe import BOEClient
    from pyodide.http import open_url

    def transport(url, accept):
        return open_url(url).read()

    options = BOEOptions(mode='online', include_unit_text=full, max_retries=0)
    client = BOEClient(options, base_url=proxy, transport=transport)
    report = enriquecer_boe(text, options, client=client)
    return _boe_payload(report)
`;

function setStatus(state, text) {
  if (els.dot) els.dot.className = 'runtime-dot is-' + state;
  if (els.status) els.status.textContent = text;
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function renderMeta(meta) {
  if (!els.meta) return;
  els.meta.innerHTML = '';
  Object.entries(meta || {}).forEach(([k, v]) => {
    const span = document.createElement('span');
    span.innerHTML = `${k} <b>${v}</b>`;
    els.meta.appendChild(span);
  });
}

// Separa el texto de un artículo del BOE en sus apartados numerados para
// que se lea como un articulado y no como un bloque denso.
function formatBoeArticles(root) {
  root.querySelectorAll('.boe-unit-text details p').forEach((p) => {
    const text = p.textContent.trim();
    const parts = text.split(/\s+(?=\d{1,2}\.\s+[A-ZÁÉÍÓÚÑ])/);
    if (parts.length <= 1) return;
    p.textContent = '';
    parts.forEach((part) => {
      const span = document.createElement('span');
      span.className = 'art-parrafo';
      span.textContent = part.trim();
      p.appendChild(span);
    });
  });
}

function showOutput(payload) {
  lastHtml = null;
  if (els.renderToggle) els.renderToggle.hidden = true;
  if (payload.render_html) {
    // Informes (auditoría, glosario, BOE): HTML generado por el paquete o
    // construido con valores escapados. Se renderiza directamente.
    els.output.innerHTML = payload.output;
    formatBoeArticles(els.output);
  } else if (payload.is_html) {
    // Expansión en formato HTML: toggle entre código escapado y vista.
    lastHtml = payload.output;
    if (els.renderToggle) {
      els.renderToggle.hidden = false;
      els.renderToggle.querySelectorAll('button').forEach((b) =>
        b.setAttribute('aria-selected', String(b.dataset.render === 'code')));
    }
    els.output.textContent = payload.output;
  } else {
    els.output.textContent = payload.output;
  }
  renderMeta(payload.meta);
}

async function runDemo() {
  if (!pyodide) return;
  const text = els.text.value;
  const onlyFirst = els.first.checked;
  pyodide.globals.set('demo_text', text);
  els.run.disabled = true;
  els.output.textContent = 'Procesando…';
  try {
    let raw;
    if (mode === 'expand') {
      pyodide.globals.set('demo_fmt', els.format.value);
      pyodide.globals.set('demo_first', onlyFirst);
      raw = pyodide.runPython('le_expand(demo_text, demo_fmt, demo_first)');
    } else if (mode === 'audit') {
      pyodide.globals.set('demo_first', onlyFirst);
      raw = pyodide.runPython('le_audit(demo_text, demo_first)');
    } else if (mode === 'glossary') {
      raw = pyodide.runPython('le_glossary(demo_text)');
    } else if (mode === 'boe') {
      const level = els.boeMode.value; // detect | confirm | full
      if (level === 'detect') {
        raw = pyodide.runPython('le_boe_detect(demo_text)');
      } else if (!BOE_PROXY) {
        const off = JSON.parse(pyodide.runPython('le_boe_detect(demo_text)'));
        els.output.innerHTML =
          '<p class="notice">Este nivel consulta el BOE en vivo y necesita un proxy (el navegador bloquea la petición directa por CORS). Mostrando la detección offline.</p>' +
          off.output;
        renderMeta(off.meta);
        els.run.disabled = false;
        return;
      } else {
        pyodide.globals.set('demo_proxy', BOE_PROXY);
        pyodide.globals.set('demo_full', level === 'full');
        raw = await pyodide.runPythonAsync('le_boe_online(demo_text, demo_proxy, demo_full)');
      }
    }
    showOutput(JSON.parse(raw));
  } catch (err) {
    els.output.textContent = 'Error: ' + (err && err.message ? err.message : String(err));
    renderMeta({});
  } finally {
    els.run.disabled = false;
  }
}

function switchMode(next) {
  mode = next;
  document.querySelectorAll('.demo-tabs button').forEach((b) =>
    b.setAttribute('aria-selected', String(b.dataset.mode === next)));
  if (els.formatGroup) els.formatGroup.hidden = next !== 'expand';
  if (els.boeGroup) els.boeGroup.hidden = next !== 'boe';
  if (els.renderToggle) els.renderToggle.hidden = true;
  // El informe BOE es una tabla ancha: la salida ocupa todo el ancho.
  const body = document.querySelector('.demo-body');
  if (body) body.classList.toggle('is-wide', next === 'boe');
}

function wireUI() {
  document.querySelectorAll('.demo-tabs button').forEach((b) => {
    b.addEventListener('click', () => switchMode(b.dataset.mode));
  });
  els.run.addEventListener('click', runDemo);
  document.querySelectorAll('#demo-examples button').forEach((b) => {
    b.addEventListener('click', () => {
      // el atributo llega ya sin escapar por el navegador
      els.text.value = b.getAttribute('data-example');
      if (pyodide) runDemo();
    });
  });
  document.querySelectorAll('#demo-docs button').forEach((b) => {
    b.addEventListener('click', () => {
      const list = window.__LEGAL_EXPAND_EXAMPLES__ || [];
      const ex = list.find((e) => e.id === b.dataset.doc);
      if (!ex) return;
      els.text.value = ex.text;
      if (pyodide) runDemo();
    });
  });
  if (els.renderToggle) {
    els.renderToggle.querySelectorAll('button').forEach((b) => {
      b.addEventListener('click', () => {
        els.renderToggle.querySelectorAll('button').forEach((x) =>
          x.setAttribute('aria-selected', String(x === b)));
        if (lastHtml == null) return;
        if (b.dataset.render === 'preview') {
          els.output.innerHTML = lastHtml; // seguro: el formatter escapa el texto
        } else {
          els.output.textContent = lastHtml;
        }
      });
    });
  }
  if (els.copyOut) {
    els.copyOut.addEventListener('click', () => {
      const ui = window.__legalExpandUI;
      if (ui) ui.copyText(els.output.textContent || '');
    });
  }
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
    els.output.innerHTML = '<span class="placeholder">Escribe texto y pulsa Ejecutar.</span>';
    runDemo();
  } catch (err) {
    setStatus('error', 'No se pudo cargar Python');
    els.output.textContent = 'Error al iniciar Pyodide: ' + (err && err.message ? err.message : String(err));
  }
}

boot();
