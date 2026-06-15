"""
Detección y enriquecimiento conservador de referencias BOE.

Esta capa no interpreta jurídicamente el documento. Solo detecta referencias
explícitas o manualmente confirmadas, y evita resolver cuando hay ambigüedad.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from .core.normalizer import is_in_special_context
from .types import (
    BOEEnrichmentOutput,
    BOEEnrichmentStats,
    BOENorm,
    BOEOptions,
    BOEReference,
    BOEReviewItem,
    BOEReviewOutput,
    BOEReviewSection,
    BOEReviewSummary,
    BOEUnitBlock,
    Position,
)


BOE_BASE_URL = 'https://www.boe.es'
BOE_CONSOLIDATED_API = '/datosabiertos/api/legislacion-consolidada'
BOE_INFORMATION_WARNING = (
    'Los textos consolidados del BOE tienen carácter meramente informativo; '
    'verifica siempre la versión oficial antes de usar una referencia en un acto jurídico.'
)
_STATUS_EXPLANATIONS = {
    'resolved': 'Norma y unidad concreta localizadas en el índice de legislación consolidada del BOE.',
    'resolved-url-only': 'La norma completa se identificó con seguridad y se enlaza a su página consolidada.',
    'manual': 'Referencia confirmada manualmente mediante overrides aportados por la persona revisora.',
    'needs-boe-search': 'La referencia parece BOE, pero necesita consulta a la API para confirmar la norma.',
    'ambiguous': 'Hay demasiada duda para elegir una norma BOE sin intervención humana.',
    'not-found': 'No se encontró una norma o unidad suficientemente identificable.',
    'unsupported': 'Referencia fuera del alcance BOE de esta función, por ejemplo normativa UE o RGPD.',
    'network-error': 'La consulta al BOE falló o superó el timeout configurado.',
}
_REASON_EXPLANATIONS = {
    ('ambiguous', 'bare-number-year-known-ambiguous'): (
        'Número y año sin fecha o título suficiente; puede referirse a más de una norma.'
    ),
    ('ambiguous', 'multiple-norms-for-same-unit'): (
        'Una misma unidad aparece asociada a varias leyes en la misma frase.'
    ),
    ('not-found', 'unit-without-norm'): (
        'La unidad se cita sin una norma inequívoca en el mismo párrafo.'
    ),
    ('not-found', 'boe-unit-block-not-found'): (
        'La norma se identificó, pero no se encontró esa unidad en el índice BOE consultado.'
    ),
}
_STATUS_ACTIONS = {
    'resolved': 'Verifica la URL oficial antes de usarla en un documento final.',
    'manual': 'Mantén el override junto al expediente para trazabilidad.',
    'needs-boe-search': 'Reejecuta con --mode cache-first u online, o confirma la norma con un override.',
    'ambiguous': 'Completa fecha, título o BOE-A en un override manual.',
    'not-found': 'Añade la norma citada o confirma manualmente si la referencia es correcta.',
    'unsupported': 'Revísala con una fuente distinta de BOE; no se resolverá automáticamente aquí.',
    'network-error': 'Reintenta con caché, más timeout o revisión manual.',
}

_MONTH = (
    r'(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|'
    r'octubre|noviembre|diciembre)'
)
_ARTICLE_WORD = r'(?:arts?\.?|art[íi]culos?|art\.)'
_ARTICLE_VALUE = r'\d+(?:\s+(?:bis|ter|quater))?(?:\.\d+)*(?:\.[a-z])?\)?(?:[ºª])?'
_ARTICLE_VALUES = (
    _ARTICLE_VALUE +
    rf'(?:\s*(?:,|y|e|a|-)\s*{_ARTICLE_VALUE})*'
    r'(?:\s+y\s+ss\.?)?'
)
_ARTICLE_REF = rf'(?:{_ARTICLE_WORD}\s+{_ARTICLE_VALUES})'
_DISPOSITION_KIND = r'(?:adicional|adic\.?|transitoria|trans\.?|derogatoria|derog\.?|final)'
_ORDINAL = (
    r'(?:(?:primera|segunda|tercera|cuarta|quinta|sexta|s[eé]ptima|octava|'
    r'novena|d[eé]cima|und[eé]cima|duod[eé]cima|[0-9]+(?:\.ª|ª|a)?)|'
    r'(?:única|unica))'
)
_DISPOSITION_REF = (
    rf'(?:(?:disposici[óo]n|disp\.)\s+{_DISPOSITION_KIND}\s+{_ORDINAL}|'
    rf'(?:DA|DF|DT|DD)\s*{_ORDINAL})'
)
_ANNEX_REF = r'(?:anexo\s+(?:[IVXLCDM]+|\d+))'
_UNIT_REF = rf'(?:{_ARTICLE_REF}|{_DISPOSITION_REF}|{_ANNEX_REF})'

_RANK_NUMBERED = (
    r'(?:Ley\s+Org[áa]nica|Ley|Real\s+Decreto-ley|Real\s+Decreto\s+Legislativo|'
    r'Real\s+Decreto|Decreto\s+Legislativo|Decreto)\s+\d{1,4}/[12]\d{3}'
    rf'(?:,\s+de\s+\d{{1,2}}\s+de\s+{_MONTH})?'
)
_ABBREVIATED_NORM = r'(?:LO|RD|RDL)\s+\d{1,4}/[12]\d{3}'
_ORDER_NUMBERED = r'Orden\s+[A-Z]{2,8}/\d{1,5}/[12]\d{3}'
_RESOLUTION_DATED = rf'Resoluci[óo]n\s+de\s+\d{{1,2}}\s+de\s+{_MONTH}\s+de\s+[12]\d{{3}}'
_NUMBERED_NORM = rf'(?:{_RANK_NUMBERED}|{_ABBREVIATED_NORM}|{_ORDER_NUMBERED}|{_RESOLUTION_DATED})'
_FULL_ALIAS = (
    r'(?:Constituci[óo]n(?:\s+Espa[ñn]ola)?|C[óo]digo\s+Civil|C[óo]digo\s+Penal|'
    r'Ley\s+de\s+Enjuiciamiento\s+Civil|Ley\s+de\s+Enjuiciamiento\s+Criminal|'
    r'Ley\s+de\s+Contratos\s+del\s+Sector\s+P[úu]blico)'
)
_SHORT_ALIAS = r'(?:LPACAP|LRJSP|LOPDGDD|LECrim|LEC|LCSP|TREBEP|EBEP|ENS|CC|CP|CE)'
_NORM_TOKEN = rf'(?:{_NUMBERED_NORM}|{_FULL_ALIAS}|{_SHORT_ALIAS})'
_NORM_ONLY_TOKEN = rf'(?:{_NUMBERED_NORM}|{_FULL_ALIAS})'
_EU_ALIAS = r'(?:RGPD|GDPR|Reglamento\s+General\s+de\s+Protecci[óo]n\s+de\s+Datos)'
_EU_NORM = rf'(?:Reglamento\s*\((?:UE|CE)\)\s+\d{{3,4}}/\d{{3,4}}|{_EU_ALIAS})'
_CONNECTOR = r'(?:(?:de\s+la|de\s+el|del|de|en|seg[uú]n)\s+)?'

_DIRECT_BOE_RE = re.compile(r'\bBOE-[A-Z]-\d{4}-\d{1,6}\b')
_UNIT_THEN_NORM_RE = re.compile(
    rf'\b(?P<unit_text>{_UNIT_REF})\s+{_CONNECTOR}(?P<norm>{_NORM_TOKEN})',
    re.IGNORECASE,
)
_UNIT_THEN_EU_RE = re.compile(
    rf'\b(?P<unit_text>{_UNIT_REF})\s+{_CONNECTOR}(?P<norm>{_EU_NORM})',
    re.IGNORECASE,
)
_MULTI_NORM_RE = re.compile(
    rf'\b(?P<unit_text>{_ARTICLE_REF})\s+de\s+las?\s+Leyes\s+'
    r'(?P<num1>\d{1,4}/[12]\d{3})\s+(?:y|e|,)\s+'
    r'(?P<num2>\d{1,4}/[12]\d{3})',
    re.IGNORECASE,
)
_NORM_ONLY_RE = re.compile(rf'\b(?P<norm>{_NORM_ONLY_TOKEN})\b', re.IGNORECASE)
_NORM_CONTEXT_RE = re.compile(rf'\b(?P<norm>{_NORM_TOKEN})\b', re.IGNORECASE)
_UNIT_ONLY_RE = re.compile(rf'\b(?P<unit_text>{_UNIT_REF})\b', re.IGNORECASE)
_EU_ONLY_RE = re.compile(rf'\b(?P<norm>{_EU_NORM})\b', re.IGNORECASE)


def _boe_url(boe_id: str, block_id: Optional[str] = None) -> str:
    url = f'{BOE_BASE_URL}/buscar/act.php?id={urllib.parse.quote(boe_id)}'
    return f'{url}#{block_id}' if block_id else url


def _normalize_text(text: str) -> str:
    table = str.maketrans({
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'Ü': 'U', 'Ñ': 'N',
        'á': 'A', 'é': 'E', 'í': 'I', 'ó': 'O', 'ú': 'U', 'ü': 'U', 'ñ': 'N',
    })
    return re.sub(r'\s+', ' ', text.translate(table).upper().strip())


def _norm(boe_id: str, title: str, source: str = 'curated') -> BOENorm:
    return BOENorm(
        boe_id=boe_id,
        title=title,
        url=_boe_url(boe_id),
        source=source,
    )


_TITLE_LAW_39 = 'Ley 39/2015, de 1 de octubre'
_TITLE_LAW_40 = 'Ley 40/2015, de 1 de octubre'
_TITLE_LOPDGDD = 'Ley Orgánica 3/2018, de 5 de diciembre'
_TITLE_CONSTITUTION = 'Constitución Española'
_TITLE_CIVIL_CODE = 'Código Civil'
_TITLE_CRIMINAL_CODE = 'Código Penal'
_TITLE_CIVIL_PROCEDURE = 'Ley 1/2000, de 7 de enero'
_TITLE_CRIMINAL_PROCEDURE = 'Ley de Enjuiciamiento Criminal'
_TITLE_PUBLIC_CONTRACTS = 'Ley 9/2017, de 8 de noviembre'
_TITLE_PUBLIC_EMPLOYEES = 'Real Decreto Legislativo 5/2015, de 30 de octubre'
_TITLE_NATIONAL_SECURITY = 'Real Decreto 311/2022, de 3 de mayo'
_CURATED_ALIASES: dict[str, BOENorm] = {
    _normalize_text('Ley 39/2015'): _norm('BOE-A-2015-10565', _TITLE_LAW_39),
    _normalize_text(_TITLE_LAW_39): _norm('BOE-A-2015-10565', _TITLE_LAW_39),
    _normalize_text('LPACAP'): _norm('BOE-A-2015-10565', _TITLE_LAW_39),
    _normalize_text('Ley 40/2015'): _norm('BOE-A-2015-10566', _TITLE_LAW_40),
    _normalize_text(_TITLE_LAW_40): _norm('BOE-A-2015-10566', _TITLE_LAW_40),
    _normalize_text('LRJSP'): _norm('BOE-A-2015-10566', _TITLE_LAW_40),
    _normalize_text('Ley Orgánica 3/2018'): _norm('BOE-A-2018-16673', _TITLE_LOPDGDD),
    _normalize_text('LO 3/2018'): _norm('BOE-A-2018-16673', _TITLE_LOPDGDD),
    _normalize_text('LOPDGDD'): _norm('BOE-A-2018-16673', _TITLE_LOPDGDD),
    _normalize_text('Ley 2/2023, de 20 de febrero'): _norm('BOE-A-2023-4513', 'Ley 2/2023, de 20 de febrero'),
    _normalize_text('Real Decreto 203/2021'): _norm('BOE-A-2021-5032', 'Real Decreto 203/2021, de 30 de marzo'),
    _normalize_text('RD 203/2021'): _norm('BOE-A-2021-5032', 'Real Decreto 203/2021, de 30 de marzo'),
    _normalize_text('Real Decreto 463/2020'): _norm('BOE-A-2020-3692', 'Real Decreto 463/2020, de 14 de marzo'),
    _normalize_text('RD 463/2020'): _norm('BOE-A-2020-3692', 'Real Decreto 463/2020, de 14 de marzo'),
    _normalize_text('Constitución'): _norm('BOE-A-1978-31229', _TITLE_CONSTITUTION),
    _normalize_text(_TITLE_CONSTITUTION): _norm('BOE-A-1978-31229', _TITLE_CONSTITUTION),
    _normalize_text('CE'): _norm('BOE-A-1978-31229', _TITLE_CONSTITUTION),
    _normalize_text(_TITLE_CIVIL_CODE): _norm('BOE-A-1889-4763', _TITLE_CIVIL_CODE),
    _normalize_text('CC'): _norm('BOE-A-1889-4763', _TITLE_CIVIL_CODE),
    _normalize_text(_TITLE_CRIMINAL_CODE): _norm('BOE-A-1995-25444', _TITLE_CRIMINAL_CODE),
    _normalize_text('CP'): _norm('BOE-A-1995-25444', _TITLE_CRIMINAL_CODE),
    _normalize_text('Ley 1/2000'): _norm('BOE-A-2000-323', _TITLE_CIVIL_PROCEDURE),
    _normalize_text('Ley de Enjuiciamiento Civil'): _norm('BOE-A-2000-323', _TITLE_CIVIL_PROCEDURE),
    _normalize_text('LEC'): _norm('BOE-A-2000-323', _TITLE_CIVIL_PROCEDURE),
    _normalize_text(_TITLE_CRIMINAL_PROCEDURE): _norm('BOE-A-1882-6036', _TITLE_CRIMINAL_PROCEDURE),
    _normalize_text('LECrim'): _norm('BOE-A-1882-6036', _TITLE_CRIMINAL_PROCEDURE),
    _normalize_text('Ley 9/2017'): _norm('BOE-A-2017-12902', _TITLE_PUBLIC_CONTRACTS),
    _normalize_text('Ley de Contratos del Sector Público'): _norm('BOE-A-2017-12902', _TITLE_PUBLIC_CONTRACTS),
    _normalize_text('LCSP'): _norm('BOE-A-2017-12902', _TITLE_PUBLIC_CONTRACTS),
    _normalize_text('Real Decreto Legislativo 5/2015'): _norm('BOE-A-2015-11719', _TITLE_PUBLIC_EMPLOYEES),
    _normalize_text('TREBEP'): _norm('BOE-A-2015-11719', _TITLE_PUBLIC_EMPLOYEES),
    _normalize_text('EBEP'): _norm('BOE-A-2015-11719', _TITLE_PUBLIC_EMPLOYEES),
    _normalize_text('Real Decreto 311/2022'): _norm('BOE-A-2022-7191', _TITLE_NATIONAL_SECURITY),
    _normalize_text('RD 311/2022'): _norm('BOE-A-2022-7191', _TITLE_NATIONAL_SECURITY),
    _normalize_text('ENS'): _norm('BOE-A-2022-7191', _TITLE_NATIONAL_SECURITY),
    _normalize_text('Orden HFP/1030/2021'): _norm('BOE-A-2021-15860', 'Orden HFP/1030/2021, de 29 de septiembre'),
}

_KNOWN_AMBIGUOUS_BARE_NORMS = {
    _normalize_text('Ley 2/2023'),
}


class BOENetworkError(RuntimeError):
    """Error estable para fallos de red BOE."""


class BOEClient:
    """
    Cliente mínimo de la API de legislación consolidada del BOE.

    Las pruebas unitarias no dependen de red: pueden inyectar un cliente falso
    con los mismos métodos públicos.
    """

    def __init__(self, options: Optional[BOEOptions] = None, base_url: str = BOE_BASE_URL):
        self.options = options or BOEOptions()
        self.base_url = base_url.rstrip('/')
        parsed_base = urllib.parse.urlparse(self.base_url)
        if parsed_base.scheme != 'https' or parsed_base.netloc != 'www.boe.es':
            raise ValueError('BOEClient only allows https://www.boe.es as base_url')

    def _cache_dir(self) -> Path:
        if self.options.cache_path:
            return Path(self.options.cache_path)
        return Path.home() / '.cache' / 'legal-expand' / 'boe'

    def _cache_key(self, path: str) -> str:
        return hashlib.sha256(path.encode('utf-8')).hexdigest() + '.json'

    def _read_cache(self, path: str) -> Optional[str]:
        cache_file = self._cache_dir() / self._cache_key(path)
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return None
        timestamp = float(data.get('timestamp', 0))
        if time.time() - timestamp > self.options.cache_ttl_days * 86400:
            return None
        body = data.get('body')
        return body if isinstance(body, str) else None

    def _write_cache(self, path: str, body: str) -> None:
        cache_dir = self._cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / self._cache_key(path)
        cache_file.write_text(
            json.dumps({'timestamp': time.time(), 'body': body}, ensure_ascii=False),
            encoding='utf-8',
        )

    def _get(self, path: str) -> str:
        cached = self._read_cache(path)
        if cached is not None:
            return cached
        if self.options.mode == 'offline':
            raise BOENetworkError('boe-offline-mode')

        url = self.base_url + path
        request = urllib.request.Request(
            url,
            headers={
                'Accept': 'application/json, application/xml;q=0.9, */*;q=0.1',
                'User-Agent': 'legal-expand/1.5 (+https://github.com/686f6c61/pypi-legal-expand)',
            },
        )
        try:
            # base_url is restricted to https://www.boe.es in __init__.
            with urllib.request.urlopen(  # nosec B310
                request,
                timeout=self.options.timeout_seconds,
            ) as response:
                body = response.read().decode('utf-8', errors='replace')
        except Exception as exc:  # pragma: no cover - depends on network
            raise BOENetworkError(str(exc)) from exc

        self._write_cache(path, body)
        return body

    def search(self, query: str) -> list[BOENorm]:
        params = urllib.parse.urlencode({
            'query': query,
            'limit': str(self.options.max_results),
        })
        body = self._get(f'{BOE_CONSOLIDATED_API}?{params}')
        return _parse_norms(body)

    def resolve_norm(self, norm_text: str) -> tuple[Optional[BOENorm], list[BOENorm]]:
        candidates = self.search(norm_text)
        if len(candidates) == 1:
            return candidates[0], candidates
        exact = [
            candidate
            for candidate in candidates
            if _normalize_text(candidate.official_number or '') in _normalize_text(norm_text)
        ]
        if len(exact) == 1:
            return exact[0], candidates
        return None, candidates

    def get_index(self, boe_id: str) -> list[dict[str, str]]:
        body = self._get(f'{BOE_CONSOLIDATED_API}/id/{urllib.parse.quote(boe_id)}/texto/indice')
        return _parse_index(body)

    def get_block_text(self, boe_id: str, block_id: str) -> str:
        body = self._get(
            f'{BOE_CONSOLIDATED_API}/id/{urllib.parse.quote(boe_id)}/texto/bloque/'
            f'{urllib.parse.quote(block_id)}'
        )
        return _plain_text(body)

    def find_unit_blocks(self, boe_id: str, unit_text: str) -> list[BOEUnitBlock]:
        index = self.get_index(boe_id)
        blocks: list[BOEUnitBlock] = []
        for target in _unit_targets(unit_text):
            match = _find_index_block(index, target)
            if match is None:
                continue
            block_id = match.get('id')
            if not block_id:
                continue
            text = self.get_block_text(boe_id, block_id)
            blocks.append(BOEUnitBlock(
                unit=target,
                block_id=block_id,
                title=match.get('title') or target,
                url=_boe_url(boe_id, block_id),
                text=text or None,
                source='boe-api',
            ))
        return blocks


def _parse_norms(body: str) -> list[BOENorm]:
    stripped = body.lstrip()
    if stripped.startswith(('{', '[')):
        return _parse_norms_json(json.loads(body))
    return _parse_norms_xml(body)


def _parse_norms_json(data: Any) -> list[BOENorm]:
    norms: list[BOENorm] = []
    for item in _iter_dicts(data):
        boe_id = _first_str(item, 'identificador', 'id', 'boe_id')
        if not boe_id or not boe_id.startswith('BOE-'):
            continue
        title = _first_str(item, 'titulo', 'title') or boe_id
        norms.append(BOENorm(
            boe_id=boe_id,
            title=title,
            url=_first_str(item, 'url_html_consolidada', 'url') or _boe_url(boe_id),
            official_number=_first_str(item, 'numero_oficial', 'official_number'),
            rank=_first_str(item, 'rango', 'rank'),
            source='boe-api',
        ))
    return _dedupe_norms(norms)


def _parse_norms_xml(body: str) -> list[BOENorm]:
    try:
        root = _xml_fromstring(body)
    except ET.ParseError:
        return []

    norms: list[BOENorm] = []
    for element in root.iter():
        data = {
            _local_name(child.tag): (child.text or '').strip()
            for child in element
            if (child.text or '').strip()
        }
        boe_id = data.get('identificador') or data.get('id')
        if not boe_id or not boe_id.startswith('BOE-'):
            continue
        norms.append(BOENorm(
            boe_id=boe_id,
            title=data.get('titulo') or boe_id,
            url=data.get('url_html_consolidada') or _boe_url(boe_id),
            official_number=data.get('numero_oficial'),
            rank=data.get('rango'),
            source='boe-api',
        ))
    return _dedupe_norms(norms)


def _parse_index(body: str) -> list[dict[str, str]]:
    stripped = body.lstrip()
    if stripped.startswith(('{', '[')):
        return _parse_index_json(json.loads(body))
    return _parse_index_xml(body)


def _parse_index_json(data: Any) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for item in _iter_dicts(data):
        block_id = _first_str(item, 'id', 'id_bloque', 'bloque')
        title = _first_str(item, 'titulo', 'title', 'texto')
        if block_id and title:
            blocks.append({'id': block_id, 'title': title})
    return blocks


def _parse_index_xml(body: str) -> list[dict[str, str]]:
    try:
        root = _xml_fromstring(body)
    except ET.ParseError:
        return []
    return [
        block
        for element in root.iter()
        if (block := _index_block_from_element(element)) is not None
    ]


def _index_block_from_element(element: ET.Element) -> Optional[dict[str, str]]:
    block_id = element.attrib.get('id') or element.attrib.get('id_bloque')
    title = element.attrib.get('titulo') or element.attrib.get('title')
    if not title:
        title = _index_title_from_children(element)
    return {'id': block_id, 'title': title} if block_id and title else None


def _index_title_from_children(element: ET.Element) -> Optional[str]:
    for child in element:
        if _local_name(child.tag) in {'titulo', 'title'} and child.text:
            return child.text.strip()
    return None


def _plain_text(body: str) -> str:
    stripped = body.lstrip()
    if stripped.startswith(('{', '[')):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return ''
        parts = [
            value.strip()
            for value in _iter_strings(data)
            if value.strip()
        ]
        return re.sub(r'\s+', ' ', ' '.join(parts)).strip()
    try:
        root = _xml_fromstring(body)
    except ET.ParseError:
        return re.sub(r'\s+', ' ', body).strip()
    return re.sub(r'\s+', ' ', ''.join(root.itertext())).strip()


def _xml_fromstring(body: str) -> ET.Element:
    lowered = body[:1000].lower()
    if '<!doctype' in lowered or '<!entity' in lowered:
        raise ET.ParseError('unsafe XML declaration rejected')
    # DTD/entity declarations are rejected before parsing.
    return ET.fromstring(body)  # nosec B314


def _iter_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_iter_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_iter_dicts(child))
    return found


def _iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for child in value.values():
            strings.extend(_iter_strings(child))
        return strings
    if isinstance(value, list):
        strings = []
        for child in value:
            strings.extend(_iter_strings(child))
        return strings
    return []


def _first_str(data: dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1].lower()


def _dedupe_norms(norms: list[BOENorm]) -> list[BOENorm]:
    seen: set[str] = set()
    unique: list[BOENorm] = []
    for norm in norms:
        if norm.boe_id in seen:
            continue
        seen.add(norm.boe_id)
        unique.append(norm)
    return unique


def _is_protected(text: str, start: int, end: int) -> bool:
    return is_in_special_context(text, start, end) is not None


def _overlaps(match: re.Match[str], spans: list[tuple[int, int]]) -> bool:
    return any(match.start() < end and match.end() > start for start, end in spans)


def _reference(
    original_text: str,
    start: int,
    end: int,
    kind: str,
    status: str,
    **kwargs: Any,
) -> BOEReference:
    return BOEReference(
        original_text=original_text,
        position=Position(start=start, end=end),
        kind=kind,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        **kwargs,
    )


def _resolve_alias(norm_text: str, options: BOEOptions, overrides: dict[str, Any]) -> Optional[BOENorm]:
    manual = _manual_alias(norm_text, overrides)
    if manual is not None:
        return manual
    if not options.use_curated_aliases:
        return None
    return _CURATED_ALIASES.get(_normalize_text(norm_text))


def _is_known_ambiguous_norm(norm_text: str) -> bool:
    return _normalize_text(norm_text) in _KNOWN_AMBIGUOUS_BARE_NORMS


def _manual_alias(norm_text: str, overrides: dict[str, Any]) -> Optional[BOENorm]:
    aliases = overrides.get('aliases', {})
    if not isinstance(aliases, dict):
        return None
    data = aliases.get(norm_text) or aliases.get(_normalize_text(norm_text))
    if data is None:
        for alias, value in aliases.items():
            if _normalize_text(str(alias)) == _normalize_text(norm_text):
                data = value
                break
    return _norm_from_override(data, source='manual') if data is not None else None


def _norm_from_override(data: Any, source: str = 'manual') -> Optional[BOENorm]:
    if isinstance(data, str):
        return _norm(data, data, source=source)
    if not isinstance(data, dict):
        return None
    boe_id = data.get('boe_id') or data.get('id')
    if not isinstance(boe_id, str) or not boe_id:
        return None
    title = data.get('title') or data.get('titulo') or boe_id
    url = data.get('url') or _boe_url(boe_id)
    return BOENorm(
        boe_id=boe_id,
        title=str(title),
        url=str(url),
        official_number=data.get('official_number') if isinstance(data.get('official_number'), str) else None,
        rank=data.get('rank') if isinstance(data.get('rank'), str) else None,
        source=source,
    )


def _status_for_resolved_unit(options: BOEOptions) -> tuple[str, Optional[str]]:
    if options.mode == 'offline':
        return 'resolved-url-only', 'offline-mode-no-unit-block-fetch'
    return 'resolved-url-only', 'unit-block-not-fetched'


def _build_norm_reference(
    match: re.Match[str],
    options: BOEOptions,
    overrides: dict[str, Any],
) -> BOEReference:
    norm_text = match.group('norm')
    norm = _resolve_alias(norm_text, options, overrides)
    if norm is not None:
        status = 'manual' if norm.source == 'manual' else 'resolved-url-only'
        return _reference(
            match.group(0), match.start(), match.end(), 'norm', status,
            norm_text=norm_text, norm=norm, confidence=0.9, source=norm.source,
            reason='whole-norm-url-only',
        )
    if _is_known_ambiguous_norm(norm_text):
        return _reference(
            match.group(0), match.start(), match.end(), 'norm', 'ambiguous',
            norm_text=norm_text, confidence=0.1, reason='bare-number-year-known-ambiguous',
        )
    return _reference(
        match.group(0), match.start(), match.end(), 'norm', 'needs-boe-search',
        norm_text=norm_text, confidence=0.35, reason='norm-requires-boe-search',
    )


def _build_unit_reference(
    match: re.Match[str],
    options: BOEOptions,
    overrides: dict[str, Any],
    inferred_norm: Optional[str] = None,
) -> BOEReference:
    unit_text = match.group('unit_text')
    norm_text = inferred_norm or match.group('norm')
    norm = _resolve_alias(norm_text, options, overrides)
    if norm is not None:
        status, reason = _status_for_resolved_unit(options)
        if norm.source == 'manual':
            status = 'manual'
            reason = 'manual-alias-override'
        return _reference(
            match.group(0), match.start(), match.end(), 'unit', status,
            norm_text=norm_text, unit_text=unit_text, norm=norm,
            confidence=0.86 if inferred_norm else 0.95,
            source=norm.source,
            reason='inferred-single-active-norm' if inferred_norm else reason,
        )
    if _is_known_ambiguous_norm(norm_text):
        return _reference(
            match.group(0), match.start(), match.end(), 'unit', 'ambiguous',
            norm_text=norm_text, unit_text=unit_text, confidence=0.1,
            reason='bare-number-year-known-ambiguous',
        )
    return _reference(
        match.group(0), match.start(), match.end(), 'unit', 'needs-boe-search',
        norm_text=norm_text, unit_text=unit_text, confidence=0.55,
        reason='unit-norm-requires-boe-search',
    )


def _infer_single_active_norm(text: str, unit_start: int) -> Optional[str]:
    paragraph_start = text.rfind('\n\n', 0, unit_start) + 2
    paragraph = text[paragraph_start:unit_start]
    norms = []
    for match in _NORM_CONTEXT_RE.finditer(paragraph):
        norms.append(match.group('norm'))
    unique = list(dict.fromkeys(_normalize_text(norm) for norm in norms))
    if len(unique) != 1:
        return None
    return norms[-1]


def _load_overrides(path: Optional[str]) -> dict[str, Any]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    return data if isinstance(data, dict) else {}


def _apply_reference_override(reference: BOEReference, overrides: dict[str, Any]) -> BOEReference:
    for item in _manual_reference_items(overrides):
        item_text = item.get('text')
        if not isinstance(item_text, str):
            continue
        if _normalize_text(item_text) != _normalize_text(reference.original_text):
            continue
        norm = _norm_from_override(item, source='manual')
        if norm is None:
            continue
        reference.norm = norm
        reference.status = 'manual'
        reference.source = 'manual'
        reference.confidence = 1.0
        reference.reason = 'manual-reference-override'
        if isinstance(item.get('unit'), str):
            reference.unit_text = item['unit']
            reference.kind = 'unit'
        return reference
    return reference


def _manual_reference_items(overrides: dict[str, Any]) -> list[dict[str, Any]]:
    references = overrides.get('references', [])
    if not isinstance(references, list):
        return []
    return [item for item in references if isinstance(item, dict)]


def _add_manual_references(
    text: str,
    references: list[BOEReference],
    consumed: list[tuple[int, int]],
    overrides: dict[str, Any],
) -> None:
    for item in _manual_reference_items(overrides):
        manual = _manual_reference_data(item)
        if manual is None:
            continue
        item_text = manual[0]
        for index, end in _manual_reference_spans(text, item_text, consumed):
            references.append(_manual_reference(manual, index, end))
            consumed.append((index, end))


_ManualReferenceData = tuple[str, BOENorm, Optional[str], Optional[str]]


def _manual_reference_data(
    item: dict[str, Any],
) -> Optional[_ManualReferenceData]:
    item_text = item.get('text')
    if not isinstance(item_text, str) or not item_text:
        return None
    norm = _norm_from_override(item, source='manual')
    if norm is None:
        return None
    norm_text = item.get('norm') if isinstance(item.get('norm'), str) else None
    unit_text = item.get('unit') if isinstance(item.get('unit'), str) else None
    return item_text, norm, norm_text, unit_text


def _manual_reference_spans(
    text: str,
    item_text: str,
    consumed: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        index = text.find(item_text, start)
        if index == -1:
            return spans
        end = index + len(item_text)
        start = end
        if _span_is_available(text, index, end, consumed):
            spans.append((index, end))


def _span_is_available(
    text: str,
    start: int,
    end: int,
    consumed: list[tuple[int, int]],
) -> bool:
    if _is_protected(text, start, end):
        return False
    return not any(start < consumed_end and end > consumed_start for consumed_start, consumed_end in consumed)


def _manual_reference(manual: _ManualReferenceData, start: int, end: int) -> BOEReference:
    item_text, norm, norm_text, unit_text = manual
    return _reference(
        item_text, start, end, 'unit' if unit_text else 'norm', 'manual',
        norm_text=norm_text,
        unit_text=unit_text,
        norm=norm,
        confidence=1.0,
        source='manual',
        reason='manual-reference-added',
    )


ReferenceAdder = Callable[[BOEReference], None]


def _build_reference_adder(
    text: str,
    references: list[BOEReference],
    consumed: list[tuple[int, int]],
    overrides: dict[str, Any],
) -> ReferenceAdder:
    def add(reference: BOEReference) -> None:
        if _is_protected(text, reference.position.start, reference.position.end):
            return
        references.append(_apply_reference_override(reference, overrides))
        consumed.append((reference.position.start, reference.position.end))

    return add


def _detect_direct_boe_ids(text: str, add: ReferenceAdder) -> None:
    for match in _DIRECT_BOE_RE.finditer(text):
        boe_id = match.group(0)
        add(_reference(
            boe_id, match.start(), match.end(), 'boe-id', 'resolved-url-only',
            norm_text=boe_id,
            norm=_norm(boe_id, boe_id, source='explicit-boe-id'),
            confidence=1.0,
            source='explicit-boe-id',
            reason='explicit-boe-id',
        ))


def _detect_multi_norm_references(text: str, add: ReferenceAdder) -> None:
    for match in _MULTI_NORM_RE.finditer(text):
        add(_reference(
            match.group(0), match.start(), match.end(), 'unit', 'ambiguous',
            unit_text=match.group('unit_text'),
            confidence=0.2,
            reason='multiple-norms-for-same-unit',
        ))


def _detect_unit_then_eu_references(
    text: str,
    consumed: list[tuple[int, int]],
    add: ReferenceAdder,
) -> None:
    for match in _UNIT_THEN_EU_RE.finditer(text):
        if _overlaps(match, consumed):
            continue
        add(_reference(
            match.group(0), match.start(), match.end(), 'unsupported', 'unsupported',
            norm_text=match.group('norm'),
            unit_text=match.group('unit_text'),
            confidence=1.0,
            reason='non-boe-eu-reference',
        ))


def _detect_unit_then_norm_references(
    text: str,
    options: BOEOptions,
    overrides: dict[str, Any],
    consumed: list[tuple[int, int]],
    add: ReferenceAdder,
) -> None:
    for match in _UNIT_THEN_NORM_RE.finditer(text):
        if not _overlaps(match, consumed):
            add(_build_unit_reference(match, options, overrides))


def _detect_eu_only_references(
    text: str,
    consumed: list[tuple[int, int]],
    add: ReferenceAdder,
) -> None:
    for match in _EU_ONLY_RE.finditer(text):
        if _overlaps(match, consumed):
            continue
        add(_reference(
            match.group(0), match.start(), match.end(), 'unsupported', 'unsupported',
            norm_text=match.group('norm'),
            confidence=1.0,
            reason='non-boe-eu-reference',
        ))


def _detect_norm_only_references(
    text: str,
    options: BOEOptions,
    overrides: dict[str, Any],
    consumed: list[tuple[int, int]],
    add: ReferenceAdder,
) -> None:
    for match in _NORM_ONLY_RE.finditer(text):
        if not _overlaps(match, consumed):
            add(_build_norm_reference(match, options, overrides))


def _build_unit_only_reference(
    text: str,
    match: re.Match[str],
    options: BOEOptions,
    overrides: dict[str, Any],
) -> BOEReference:
    inferred_norm = (
        _infer_single_active_norm(text, match.start())
        if options.infer_single_active_norm
        else None
    )
    if inferred_norm:
        return _build_unit_reference(match, options, overrides, inferred_norm=inferred_norm)
    return _reference(
        match.group(0), match.start(), match.end(), 'unit', 'not-found',
        unit_text=match.group('unit_text'),
        confidence=0.0,
        reason='unit-without-norm',
    )


def _detect_unit_only_references(
    text: str,
    options: BOEOptions,
    overrides: dict[str, Any],
    consumed: list[tuple[int, int]],
    add: ReferenceAdder,
) -> None:
    for match in _UNIT_ONLY_RE.finditer(text):
        if not _overlaps(match, consumed):
            add(_build_unit_only_reference(text, match, options, overrides))


def detectar_referencias_boe(
    texto: str,
    opciones: Optional[BOEOptions] = None,
    overrides: Optional[dict[str, Any]] = None,
) -> BOEEnrichmentOutput:
    """
    Detecta referencias BOE sin consultar red.

    Las referencias ambiguas se reportan como tales. Si se proporcionan
    overrides, estos pueden confirmar aliases o añadir referencias manuales.
    """
    options = opciones or BOEOptions()
    override_data = overrides or _load_overrides(options.overrides_path)
    references: list[BOEReference] = []
    consumed: list[tuple[int, int]] = []
    add = _build_reference_adder(texto, references, consumed, override_data)

    _detect_direct_boe_ids(texto, add)
    _detect_multi_norm_references(texto, add)
    _detect_unit_then_eu_references(texto, consumed, add)
    _detect_unit_then_norm_references(texto, options, override_data, consumed, add)
    _detect_eu_only_references(texto, consumed, add)
    _detect_norm_only_references(texto, options, override_data, consumed, add)
    _detect_unit_only_references(texto, options, override_data, consumed, add)

    _add_manual_references(texto, references, consumed, override_data)
    references.sort(key=lambda item: item.position.start)
    return _output(texto, references)


def enriquecer_boe(
    texto: str,
    opciones: Optional[BOEOptions] = None,
    client: Optional[BOEClient] = None,
    overrides: Optional[dict[str, Any]] = None,
) -> BOEEnrichmentOutput:
    """
    Detecta y, si el modo lo permite, consulta BOE para completar referencias.
    """
    options = opciones or BOEOptions()
    output = detectar_referencias_boe(texto, options, overrides)
    if options.mode == 'offline':
        return output

    boe_client = client or BOEClient(options)
    enriched: list[BOEReference] = []
    for reference in output.references:
        try:
            enriched.append(_enrich_reference(reference, options, boe_client))
        except BOENetworkError as exc:
            reference.status = 'network-error'
            reference.reason = str(exc)
            enriched.append(reference)
    return _output(texto, enriched)


_ENRICH_SKIP_STATUSES = {'unsupported', 'ambiguous', 'not-found'}


def _enrich_reference(reference: BOEReference, options: BOEOptions, client: BOEClient) -> BOEReference:
    if reference.status in _ENRICH_SKIP_STATUSES:
        return reference
    if _needs_norm_lookup(reference) and not _resolve_reference_norm(reference, client):
        return reference

    if _should_fetch_unit_blocks(reference, options):
        return _enrich_unit_blocks(reference, client)
    return reference


def _needs_norm_lookup(reference: BOEReference) -> bool:
    return (
        reference.norm is None
        and reference.norm_text is not None
        and reference.status == 'needs-boe-search'
    )


def _resolve_reference_norm(reference: BOEReference, client: BOEClient) -> bool:
    norm, candidates = client.resolve_norm(reference.norm_text or '')
    reference.candidates = candidates
    if norm is None:
        reference.status = 'ambiguous' if candidates else 'not-found'
        reference.reason = 'boe-search-ambiguous' if candidates else 'boe-search-not-found'
        return False
    reference.norm = norm
    reference.status = 'resolved-url-only'
    reference.source = norm.source
    reference.reason = 'boe-search-resolved-url-only'
    return True


def _should_fetch_unit_blocks(reference: BOEReference, options: BOEOptions) -> bool:
    return reference.norm is not None and reference.unit_text is not None and options.include_unit_text


def _enrich_unit_blocks(reference: BOEReference, client: BOEClient) -> BOEReference:
    if reference.norm is None or reference.unit_text is None:
        return reference
    blocks = client.find_unit_blocks(reference.norm.boe_id, reference.unit_text)
    if blocks:
        reference.unit_blocks = blocks
        reference.status = 'resolved'
        reference.reason = 'boe-unit-block-resolved'
        return reference
    if reference.status != 'manual':
        reference.status = 'not-found'
        reference.reason = 'boe-unit-block-not-found'
    return reference


def _output(texto: str, references: list[BOEReference]) -> BOEEnrichmentOutput:
    stats = BOEEnrichmentStats(
        total_detected=len(references),
        total_resolved=sum(1 for item in references if item.status in {'resolved', 'resolved-url-only'}),
        total_manual=sum(1 for item in references if item.status == 'manual'),
        total_ambiguous=sum(1 for item in references if item.status == 'ambiguous'),
        total_unresolved=sum(1 for item in references if item.status in {'needs-boe-search', 'not-found', 'network-error'}),
        total_unsupported=sum(1 for item in references if item.status == 'unsupported'),
    )
    return BOEEnrichmentOutput(
        original_text=texto,
        references=references,
        stats=stats,
        warnings=[BOE_INFORMATION_WARNING],
    )


def explicar_referencia_boe(reference: BOEReference) -> str:
    """
    Explica por qué una referencia BOE quedó en su estado actual.
    """
    if reference.status == 'resolved-url-only' and reference.unit_text:
        return (
            'La norma se identificó con seguridad, pero no se insertó texto de la unidad. '
            'Activa cache-first u online para intentar localizar artículos o anexos.'
        )
    if reference.status == 'ambiguous' and reference.candidates:
        return 'La consulta devolvió varios candidatos y no se elige ninguno automáticamente.'
    reason = _REASON_EXPLANATIONS.get((reference.status, reference.reason or ''))
    return reason or _STATUS_EXPLANATIONS.get(reference.status, reference.reason or 'Sin explicación disponible.')


def _review_section(reference: BOEReference) -> BOEReviewSection:
    if reference.status == 'manual':
        return 'manual'
    if reference.status in {'resolved', 'resolved-url-only'}:
        return 'resolved'
    if reference.status == 'unsupported':
        return 'unsupported'
    return 'review-required'


def _suggested_action(reference: BOEReference) -> str:
    status = 'resolved' if reference.status == 'resolved-url-only' else reference.status
    return _STATUS_ACTIONS.get(status, 'Revisa la referencia antes de usarla.')


def revisar_boe(output: BOEEnrichmentOutput) -> BOEReviewOutput:
    """
    Agrupa un informe BOE en secciones útiles para revisión humana.
    """
    items = [
        BOEReviewItem(
            reference=reference,
            section=_review_section(reference),
            explanation=explicar_referencia_boe(reference),
            suggested_action=_suggested_action(reference),
        )
        for reference in output.references
    ]
    summary = BOEReviewSummary(
        total_references=len(items),
        resolved=sum(1 for item in items if item.section == 'resolved'),
        manual=sum(1 for item in items if item.section == 'manual'),
        review_required=sum(1 for item in items if item.section == 'review-required'),
        unsupported=sum(1 for item in items if item.section == 'unsupported'),
        ready_count=sum(1 for item in items if item.section in {'resolved', 'manual'}),
    )
    return BOEReviewOutput(
        original_text=output.original_text,
        items=items,
        summary=summary,
        warnings=output.warnings,
    )


def boe_overrides_template(output: BOEEnrichmentOutput) -> dict[str, Any]:
    """
    Genera un template JSON editable para referencias BOE pendientes.
    """
    references: list[dict[str, Any]] = []
    for item in revisar_boe(output).items:
        reference = item.reference
        if item.section != 'review-required':
            continue
        data: dict[str, Any] = {
            'text': reference.original_text,
            'boe_id': '',
            'title': '',
        }
        if reference.norm_text:
            data['norm'] = reference.norm_text
        if reference.unit_text:
            data['unit'] = reference.unit_text
        if reference.candidates:
            data['candidates'] = [
                {
                    'boe_id': candidate.boe_id,
                    'title': candidate.title,
                    'url': candidate.url,
                }
                for candidate in reference.candidates
            ]
        data['review_note'] = item.explanation
        references.append(data)
    return {
        'aliases': {},
        'references': references,
    }


def _unit_targets(unit_text: str) -> list[str]:
    normalized = _normalize_text(unit_text)
    if normalized.startswith('ART'):
        return _article_unit_targets(unit_text)
    return [_normalize_for_title(unit_text)]


def _article_unit_targets(unit_text: str) -> list[str]:
    article_refs = re.findall(
        r'(\d+)(?:\s+(bis|ter|quater))?(?:\.\d+)*(?:\.[a-z])?\)?',
        unit_text,
        flags=re.IGNORECASE,
    )
    range_targets = _article_range_targets(article_refs, unit_text)
    if range_targets is not None:
        return range_targets
    return _dedupe_article_targets(article_refs)


def _article_range_targets(
    article_refs: list[tuple[str, str]],
    unit_text: str,
) -> Optional[list[str]]:
    if len(article_refs) < 2 or not _has_article_range_connector(unit_text):
        return None
    start, end = article_refs[0][0], article_refs[-1][0]
    start_i, end_i = int(start), int(end)
    if 0 < end_i - start_i <= 50:
        return [f'artículo {number}' for number in range(start_i, end_i + 1)]
    return None


def _has_article_range_connector(unit_text: str) -> bool:
    return '-' in unit_text or re.search(r'\ba\b', unit_text, flags=re.IGNORECASE) is not None


def _dedupe_article_targets(article_refs: list[tuple[str, str]]) -> list[str]:
    targets: list[str] = []
    for number, suffix in article_refs:
        target = f'artículo {number}'
        if suffix:
            target += f' {suffix.lower()}'
        if target not in targets:
            targets.append(target)
    return targets


def _normalize_for_title(text: str) -> str:
    normalized = _normalize_text(text).lower()
    normalized = re.sub(r'^disp\.\s*adic\.?', 'disposición adicional', normalized)
    normalized = re.sub(r'^disp\.\s*trans\.?', 'disposición transitoria', normalized)
    normalized = re.sub(r'^disp\.\s*derog\.?', 'disposición derogatoria', normalized)
    normalized = re.sub(r'^disp\.\s*final', 'disposición final', normalized)
    normalized = re.sub(r'^da\s*', 'disposición adicional ', normalized)
    normalized = re.sub(r'^dt\s*', 'disposición transitoria ', normalized)
    normalized = re.sub(r'^dd\s*', 'disposición derogatoria ', normalized)
    normalized = re.sub(r'^df\s*', 'disposición final ', normalized)
    normalized = normalized.replace('septima', 'séptima')
    return normalized


def _find_index_block(index: list[dict[str, str]], target: str) -> Optional[dict[str, str]]:
    normalized_target = _normalize_text(target)
    for item in index:
        title = item.get('title') or ''
        normalized_title = _normalize_text(title)
        if normalized_target == normalized_title or normalized_title.startswith(normalized_target):
            return item
    return None


_RESOLVED_STATUSES = {'resolved', 'resolved-url-only', 'manual'}
_PENDING_STATUSES = {'needs-boe-search', 'ambiguous', 'not-found', 'network-error'}


def boe_report_to_markdown(output: BOEEnrichmentOutput) -> str:
    """
    Convierte un informe BOE a Markdown legible.
    """
    lines = _boe_markdown_summary(output)
    resolved = [item for item in output.references if item.status in _RESOLVED_STATUSES]
    pending = [item for item in output.references if item.status in _PENDING_STATUSES]
    unsupported = [item for item in output.references if item.status == 'unsupported']

    _append_resolved_markdown(lines, resolved)
    _append_pending_markdown(lines, pending)
    _append_unsupported_markdown(lines, unsupported)
    _append_warning_markdown(lines, output.warnings)

    return '\n'.join(lines).strip() + '\n'


def _boe_markdown_summary(output: BOEEnrichmentOutput) -> list[str]:
    return [
        '# legal-expand BOE',
        '',
        f"- Detectadas: {output.stats.total_detected}",
        f"- Resueltas: {output.stats.total_resolved}",
        f"- Manuales: {output.stats.total_manual}",
        f"- Ambiguas: {output.stats.total_ambiguous}",
        f"- Pendientes/no encontradas: {output.stats.total_unresolved}",
        f"- No soportadas: {output.stats.total_unsupported}",
        '',
    ]


def _append_resolved_markdown(lines: list[str], items: list[BOEReference]) -> None:
    if not items:
        return
    lines.extend([
        '## Referencias resueltas',
        '',
        '| Texto | Estado | Norma | Unidad | URL | Explicación |',
        '| --- | --- | --- | --- | --- | --- |',
    ])
    for item in items:
        lines.append(_resolved_markdown_row(item))
        _append_unit_blocks_markdown(lines, item)


def _resolved_markdown_row(item: BOEReference) -> str:
    norm_title = item.norm.title if item.norm else ''
    return (
        f"| {_md(item.original_text)} | {item.status} | {_md(norm_title)} | "
        f"{_md(item.unit_text or '')} | {_best_url(item)} | "
        f"{_md(explicar_referencia_boe(item))} |"
    )


def _append_unit_blocks_markdown(lines: list[str], item: BOEReference) -> None:
    for block in item.unit_blocks:
        if block.text:
            lines.extend(['', f"### {_md(block.title)}", '', block.text, ''])


def _append_pending_markdown(lines: list[str], items: list[BOEReference]) -> None:
    if not items:
        return
    lines.extend([
        '',
        '## Requieren revisión',
        '',
        '| Texto | Estado | Motivo | Explicación | Acción sugerida |',
        '| --- | --- | --- | --- | --- |',
    ])
    lines.extend(_pending_markdown_row(item) for item in items)


def _pending_markdown_row(item: BOEReference) -> str:
    return (
        f"| {_md(item.original_text)} | {item.status} | {_md(item.reason or '')} | "
        f"{_md(explicar_referencia_boe(item))} | {_md(_suggested_action(item))} |"
    )


def _append_unsupported_markdown(lines: list[str], items: list[BOEReference]) -> None:
    if not items:
        return
    lines.extend([
        '',
        '## No soportadas',
        '',
        '| Texto | Motivo | Explicación |',
        '| --- | --- | --- |',
    ])
    lines.extend(_unsupported_markdown_row(item) for item in items)


def _unsupported_markdown_row(item: BOEReference) -> str:
    return (
        f"| {_md(item.original_text)} | {_md(item.reason or '')} | "
        f"{_md(explicar_referencia_boe(item))} |"
    )


def _append_warning_markdown(lines: list[str], warnings: list[str]) -> None:
    if warnings:
        lines.extend(['', '## Avisos', ''])
        lines.extend(f"- {warning}" for warning in warnings)


def boe_report_to_html(output: BOEEnrichmentOutput) -> str:
    """
    Convierte un informe BOE a HTML semántico con enlaces seguros.
    """
    review = revisar_boe(output)
    lines = [
        '<section class="legal-expand-boe">',
        '<h1>legal-expand BOE</h1>',
        '<dl>',
        f'<dt>Detectadas</dt><dd>{review.summary.total_references}</dd>',
        f'<dt>Listas</dt><dd>{review.summary.ready_count}</dd>',
        f'<dt>Requieren revisión</dt><dd>{review.summary.review_required}</dd>',
        f'<dt>No soportadas</dt><dd>{review.summary.unsupported}</dd>',
        '</dl>',
    ]
    for section, title in (
        ('resolved', 'Referencias resueltas'),
        ('manual', 'Referencias manuales'),
        ('review-required', 'Requieren revisión'),
        ('unsupported', 'No soportadas'),
    ):
        items = [item for item in review.items if item.section == section]
        if not items:
            continue
        lines.extend([
            f'<h2>{html.escape(title)}</h2>',
            '<table>',
            '<thead><tr><th>Texto</th><th>Estado</th><th>Norma</th>'
            '<th>Unidad</th><th>URL</th><th>Explicación</th><th>Acción</th></tr></thead>',
            '<tbody>',
        ])
        for item in items:
            reference = item.reference
            norm_title = reference.norm.title if reference.norm else ''
            url = _best_url(reference)
            url_html = (
                f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>'
                if url
                else ''
            )
            lines.append(
                '<tr>'
                f'<td>{html.escape(reference.original_text)}</td>'
                f'<td>{html.escape(reference.status)}</td>'
                f'<td>{html.escape(norm_title)}</td>'
                f'<td>{html.escape(reference.unit_text or "")}</td>'
                f'<td>{url_html}</td>'
                f'<td>{html.escape(item.explanation)}</td>'
                f'<td>{html.escape(item.suggested_action)}</td>'
                '</tr>'
            )
        lines.extend(['</tbody>', '</table>'])

    if output.warnings:
        lines.append('<h2>Avisos</h2>')
        lines.append('<ul>')
        lines.extend(f'<li>{html.escape(warning)}</li>' for warning in output.warnings)
        lines.append('</ul>')
    lines.append('</section>')
    return '\n'.join(lines) + '\n'


def boe_report_by_paragraph_markdown(output: BOEEnrichmentOutput) -> str:
    """
    Devuelve el texto original con un bloque de referencias BOE tras cada párrafo afectado.
    """
    parts: list[str] = []
    for start, end, paragraph in _paragraph_spans(output.original_text):
        refs = [
            reference
            for reference in output.references
            if start <= reference.position.start < end
        ]
        parts.append(paragraph.rstrip())
        if refs:
            parts.extend(['', '> Referencias BOE sugeridas:'])
            for reference in refs:
                url = _best_url(reference)
                explanation = explicar_referencia_boe(reference)
                label = reference.unit_text or reference.norm_text or reference.original_text
                if url:
                    parts.append(
                        f"> - {reference.status}: [{_md(label)}]({url}) - {_md(explanation)}"
                    )
                else:
                    parts.append(
                        f"> - {reference.status}: {_md(label)} - {_md(explanation)}"
                    )
        parts.append('')
    if output.warnings:
        parts.append('> Aviso BOE: ' + _md(output.warnings[0]))
        parts.append('')
    return '\n'.join(parts).strip() + '\n'


def _paragraph_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    start = 0
    for match in re.finditer(r'\n\s*\n', text):
        paragraph = text[start:match.start()]
        if paragraph.strip():
            spans.append((start, match.start(), paragraph))
        start = match.end()
    paragraph = text[start:]
    if paragraph.strip():
        spans.append((start, len(text), paragraph))
    return spans


def _best_url(reference: BOEReference) -> str:
    if reference.unit_blocks:
        return reference.unit_blocks[0].url
    if reference.norm:
        return reference.norm.url
    return ''


def _md(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ')
