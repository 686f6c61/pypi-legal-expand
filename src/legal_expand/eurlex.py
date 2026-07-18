"""
Resolución de normativa de la Unión Europea a su página oficial en EUR-Lex.

El BOE solo publica legislación española consolidada; la normativa de la UE
(reglamentos, directivas, decisiones) vive en EUR-Lex. Este módulo construye el
identificador **CELEX** de una referencia UE y su URL oficial en EUR-Lex, para
enlazarla en lugar de descartarla como «no soportada».

El CELEX del derecho derivado tiene la forma ``3`` + año (4 dígitos) + sector
(``R`` reglamento, ``L`` directiva, ``D`` decisión) + número con relleno a 4
dígitos. Ejemplos verificados contra EUR-Lex:

- Reglamento (UE) 2016/679 (RGPD) -> ``32016R0679``
- Directiva 2000/31/CE           -> ``32000L0031``
- Reglamento (CE) 1049/2001       -> ``32001R1049`` (número/año invertidos)

El año se identifica como el grupo de cuatro dígitos que cae en un rango de años
plausible; el otro grupo es el número de la norma. Ante ambigüedad no resuelve.
"""

from __future__ import annotations

import re
import urllib.parse
from html.parser import HTMLParser
from typing import Optional

from .types import BOENorm


_EURLEX_URL = 'https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:{celex}'


def eurlex_html_path(celex: str) -> str:
    """Ruta del documento consolidado en HTML dentro de EUR-Lex (por CELEX)."""
    return f'/legal-content/ES/TXT/HTML/?uri=CELEX:{urllib.parse.quote(celex)}'


class _ArticleTextExtractor(HTMLParser):
    """Acumula el texto visible de un fragmento HTML de EUR-Lex."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return re.sub(r'\s+', ' ', ' '.join(self._parts)).strip()


def unit_number(unit_text: Optional[str]) -> Optional[str]:
    """Extrae el número de artículo de una unidad citada ('art. 6' -> '6')."""
    if not unit_text:
        return None
    match = re.search(r'\d+', unit_text)
    return match.group(0) if match else None


def _fragment_text(html_doc: str, start: int, after: int, next_match: Optional[re.Match]) -> str:
    if next_match is not None:
        end = html_doc.rfind('<', after, after + next_match.start())
        if end <= start:
            end = after + next_match.start()
    else:
        end = len(html_doc)
    parser = _ArticleTextExtractor()
    parser.feed(html_doc[start:end])
    return parser.text()


def extract_article_text(html_doc: str, numero: str) -> str:
    """
    Extrae el texto de un artículo del HTML consolidado de EUR-Lex.

    Soporta los dos formatos de EUR-Lex: el moderno con anclas ``id="art_N"`` y
    el antiguo con títulos ``<p>Artículo N</p>``. El contenido llega hasta el
    siguiente artículo. Devuelve cadena vacía si no se localiza.
    """
    # Formato moderno: anclas id="art_N".
    marker = f'id="art_{numero}"'
    marker_pos = html_doc.find(marker)
    if marker_pos != -1:
        tag_start = html_doc.rfind('<', 0, marker_pos)
        start = tag_start if tag_start != -1 else marker_pos
        after = marker_pos + len(marker)
        return _fragment_text(html_doc, start, after, re.search(r'id="art_\d+"', html_doc[after:]))

    # Formato antiguo: <p>Artículo N</p> hasta el siguiente <p>Artículo M</p>.
    title_re = re.compile(r'>\s*Art[íi]culo\s+' + re.escape(numero) + r'\s*<\s*/')
    match = title_re.search(html_doc)
    if match is None:
        return ''
    start = html_doc.rfind('<', 0, match.start())
    after = match.end()
    next_re = re.compile(r'>\s*Art[íi]culo\s+\d+\s*<\s*/')
    return _fragment_text(html_doc, start, after, next_re.search(html_doc[after:]))

# Normas UE muy citadas por su sigla -> (CELEX, título).
_EU_ALIASES: dict[str, tuple[str, str]] = {
    'rgpd': ('32016R0679', 'Reglamento (UE) 2016/679 (RGPD)'),
    'gdpr': ('32016R0679', 'Reglamento (UE) 2016/679 (GDPR)'),
    'reglamento general de proteccion de datos': (
        '32016R0679', 'Reglamento (UE) 2016/679 (RGPD)'
    ),
}

# Palabra de rango en la cita -> sector CELEX.
_SECTORES: dict[str, str] = {
    'reglamento': 'R',
    'directiva': 'L',
    'decision': 'D',
}

_NUMERO_RE = re.compile(r'(\d{1,4})/(\d{1,4})')


def _strip_accents(text: str) -> str:
    table = str.maketrans({
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u', 'ñ': 'n',
        'Á': 'a', 'É': 'e', 'Í': 'i', 'Ó': 'o', 'Ú': 'u', 'Ü': 'u', 'Ñ': 'n',
    })
    return text.translate(table)


def _celex_url(celex: str) -> str:
    return _EURLEX_URL.format(celex=celex)


def build_celex(sector: str, anio: str, numero: str) -> str:
    """Construye el CELEX del derecho derivado: 3 + año + sector + número(4)."""
    return f'3{anio}{sector}{int(numero):04d}'


def _es_anio(valor: str) -> bool:
    return valor.isdigit() and 1950 <= int(valor) <= 2099


def _anio_y_numero(grupo1: str, grupo2: str) -> Optional[tuple[str, str]]:
    """Identifica cuál grupo es el año y cuál el número de la norma."""
    if _es_anio(grupo1) and not _es_anio(grupo2):
        return grupo1, grupo2
    if _es_anio(grupo2) and not _es_anio(grupo1):
        return grupo2, grupo1
    # Ambos o ninguno son años plausibles: no se resuelve sin arriesgar.
    return None


def resolve_eu_norm(norm_text: str) -> Optional[BOENorm]:
    """
    Resuelve una referencia de normativa UE a su norma en EUR-Lex.

    Devuelve un BOENorm con el CELEX como identificador, el título y la URL de
    EUR-Lex. Ante una cita que no pueda mapearse con seguridad devuelve None.
    """
    normalized = re.sub(r'\s+', ' ', _strip_accents(norm_text).lower()).strip()

    for alias, (celex, titulo) in _EU_ALIASES.items():
        if alias in normalized:
            return BOENorm(
                boe_id=celex, title=titulo, url=_celex_url(celex), source='eur-lex',
            )

    sector = next((letra for palabra, letra in _SECTORES.items() if palabra in normalized), None)
    if sector is None:
        return None

    match = _NUMERO_RE.search(norm_text)
    if match is None:
        return None
    par = _anio_y_numero(match.group(1), match.group(2))
    if par is None:
        return None

    anio, numero = par
    celex = build_celex(sector, anio, numero)
    return BOENorm(
        boe_id=celex,
        title=norm_text.strip(),
        url=_celex_url(celex),
        official_number=f'{numero}/{anio}',
        source='eur-lex',
    )
