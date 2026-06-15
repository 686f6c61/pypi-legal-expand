"""
Detección y enriquecimiento conservador de referencias BOE.

Esta capa no interpreta jurídicamente el documento. Solo detecta referencias
explícitas o manualmente confirmadas, y evita resolver cuando hay ambigüedad.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

from .core.normalizer import is_in_special_context
from .types import (
    BOEEnrichmentOutput,
    BOEEnrichmentStats,
    BOENorm,
    BOEOptions,
    BOEReference,
    BOEUnitBlock,
    Position,
)


BOE_BASE_URL = 'https://www.boe.es'
BOE_CONSOLIDATED_API = '/datosabiertos/api/legislacion-consolidada'
BOE_INFORMATION_WARNING = (
    'Los textos consolidados del BOE tienen carácter meramente informativo; '
    'verifica siempre la versión oficial antes de usar una referencia en un acto jurídico.'
)

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


_CURATED_ALIASES: dict[str, BOENorm] = {
    _normalize_text('Ley 39/2015'): _norm('BOE-A-2015-10565', 'Ley 39/2015, de 1 de octubre'),
    _normalize_text('Ley 39/2015, de 1 de octubre'): _norm('BOE-A-2015-10565', 'Ley 39/2015, de 1 de octubre'),
    _normalize_text('LPACAP'): _norm('BOE-A-2015-10565', 'Ley 39/2015, de 1 de octubre'),
    _normalize_text('Ley 40/2015'): _norm('BOE-A-2015-10566', 'Ley 40/2015, de 1 de octubre'),
    _normalize_text('Ley 40/2015, de 1 de octubre'): _norm('BOE-A-2015-10566', 'Ley 40/2015, de 1 de octubre'),
    _normalize_text('LRJSP'): _norm('BOE-A-2015-10566', 'Ley 40/2015, de 1 de octubre'),
    _normalize_text('Ley Orgánica 3/2018'): _norm('BOE-A-2018-16673', 'Ley Orgánica 3/2018, de 5 de diciembre'),
    _normalize_text('LO 3/2018'): _norm('BOE-A-2018-16673', 'Ley Orgánica 3/2018, de 5 de diciembre'),
    _normalize_text('LOPDGDD'): _norm('BOE-A-2018-16673', 'Ley Orgánica 3/2018, de 5 de diciembre'),
    _normalize_text('Ley 2/2023, de 20 de febrero'): _norm('BOE-A-2023-4513', 'Ley 2/2023, de 20 de febrero'),
    _normalize_text('Real Decreto 203/2021'): _norm('BOE-A-2021-5032', 'Real Decreto 203/2021, de 30 de marzo'),
    _normalize_text('RD 203/2021'): _norm('BOE-A-2021-5032', 'Real Decreto 203/2021, de 30 de marzo'),
    _normalize_text('Real Decreto 463/2020'): _norm('BOE-A-2020-3692', 'Real Decreto 463/2020, de 14 de marzo'),
    _normalize_text('RD 463/2020'): _norm('BOE-A-2020-3692', 'Real Decreto 463/2020, de 14 de marzo'),
    _normalize_text('Constitución'): _norm('BOE-A-1978-31229', 'Constitución Española'),
    _normalize_text('Constitución Española'): _norm('BOE-A-1978-31229', 'Constitución Española'),
    _normalize_text('CE'): _norm('BOE-A-1978-31229', 'Constitución Española'),
    _normalize_text('Código Civil'): _norm('BOE-A-1889-4763', 'Código Civil'),
    _normalize_text('CC'): _norm('BOE-A-1889-4763', 'Código Civil'),
    _normalize_text('Código Penal'): _norm('BOE-A-1995-25444', 'Código Penal'),
    _normalize_text('CP'): _norm('BOE-A-1995-25444', 'Código Penal'),
    _normalize_text('Ley 1/2000'): _norm('BOE-A-2000-323', 'Ley 1/2000, de 7 de enero'),
    _normalize_text('Ley de Enjuiciamiento Civil'): _norm('BOE-A-2000-323', 'Ley 1/2000, de 7 de enero'),
    _normalize_text('LEC'): _norm('BOE-A-2000-323', 'Ley 1/2000, de 7 de enero'),
    _normalize_text('Ley de Enjuiciamiento Criminal'): _norm('BOE-A-1882-6036', 'Ley de Enjuiciamiento Criminal'),
    _normalize_text('LECrim'): _norm('BOE-A-1882-6036', 'Ley de Enjuiciamiento Criminal'),
    _normalize_text('Ley 9/2017'): _norm('BOE-A-2017-12902', 'Ley 9/2017, de 8 de noviembre'),
    _normalize_text('Ley de Contratos del Sector Público'): _norm('BOE-A-2017-12902', 'Ley 9/2017, de 8 de noviembre'),
    _normalize_text('LCSP'): _norm('BOE-A-2017-12902', 'Ley 9/2017, de 8 de noviembre'),
    _normalize_text('Real Decreto Legislativo 5/2015'): _norm('BOE-A-2015-11719', 'Real Decreto Legislativo 5/2015, de 30 de octubre'),
    _normalize_text('TREBEP'): _norm('BOE-A-2015-11719', 'Real Decreto Legislativo 5/2015, de 30 de octubre'),
    _normalize_text('EBEP'): _norm('BOE-A-2015-11719', 'Real Decreto Legislativo 5/2015, de 30 de octubre'),
    _normalize_text('Real Decreto 311/2022'): _norm('BOE-A-2022-7191', 'Real Decreto 311/2022, de 3 de mayo'),
    _normalize_text('RD 311/2022'): _norm('BOE-A-2022-7191', 'Real Decreto 311/2022, de 3 de mayo'),
    _normalize_text('ENS'): _norm('BOE-A-2022-7191', 'Real Decreto 311/2022, de 3 de mayo'),
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
                'User-Agent': 'legal-expand/1.4 (+https://github.com/686f6c61/pypi-legal-expand)',
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.options.timeout_seconds) as response:
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
    if stripped.startswith('{') or stripped.startswith('['):
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
        root = ET.fromstring(body)
    except ET.ParseError:
        return []

    norms: list[BOENorm] = []
    for element in root.iter():
        data = {
            _local_name(child.tag): (child.text or '').strip()
            for child in list(element)
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
    if stripped.startswith('{') or stripped.startswith('['):
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
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    blocks: list[dict[str, str]] = []
    for element in root.iter():
        block_id = element.attrib.get('id') or element.attrib.get('id_bloque')
        title = element.attrib.get('titulo') or element.attrib.get('title')
        if not title:
            for child in list(element):
                if _local_name(child.tag) in {'titulo', 'title'} and child.text:
                    title = child.text.strip()
                    break
        if block_id and title:
            blocks.append({'id': block_id, 'title': title})
    return blocks


def _plain_text(body: str) -> str:
    stripped = body.lstrip()
    if stripped.startswith('{') or stripped.startswith('['):
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
        root = ET.fromstring(body)
    except ET.ParseError:
        return re.sub(r'\s+', ' ', body).strip()
    return re.sub(r'\s+', ' ', ''.join(root.itertext())).strip()


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
        item_text = item.get('text')
        if not isinstance(item_text, str) or not item_text:
            continue
        norm = _norm_from_override(item, source='manual')
        if norm is None:
            continue
        start = 0
        while True:
            index = text.find(item_text, start)
            if index == -1:
                break
            end = index + len(item_text)
            start = end
            if _is_protected(text, index, end):
                continue
            if any(index < consumed_end and end > consumed_start for consumed_start, consumed_end in consumed):
                continue
            unit_text = item.get('unit') if isinstance(item.get('unit'), str) else None
            references.append(_reference(
                item_text, index, end, 'unit' if unit_text else 'norm', 'manual',
                norm_text=item.get('norm') if isinstance(item.get('norm'), str) else None,
                unit_text=unit_text,
                norm=norm,
                confidence=1.0,
                source='manual',
                reason='manual-reference-added',
            ))
            consumed.append((index, end))


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

    def add(reference: BOEReference) -> None:
        if _is_protected(texto, reference.position.start, reference.position.end):
            return
        references.append(_apply_reference_override(reference, override_data))
        consumed.append((reference.position.start, reference.position.end))

    for match in _DIRECT_BOE_RE.finditer(texto):
        if _is_protected(texto, match.start(), match.end()):
            continue
        boe_id = match.group(0)
        add(_reference(
            boe_id, match.start(), match.end(), 'boe-id', 'resolved-url-only',
            norm_text=boe_id,
            norm=_norm(boe_id, boe_id, source='explicit-boe-id'),
            confidence=1.0,
            source='explicit-boe-id',
            reason='explicit-boe-id',
        ))

    for match in _MULTI_NORM_RE.finditer(texto):
        add(_reference(
            match.group(0), match.start(), match.end(), 'unit', 'ambiguous',
            unit_text=match.group('unit_text'),
            confidence=0.2,
            reason='multiple-norms-for-same-unit',
        ))

    for match in _UNIT_THEN_EU_RE.finditer(texto):
        if _overlaps(match, consumed):
            continue
        add(_reference(
            match.group(0), match.start(), match.end(), 'unsupported', 'unsupported',
            norm_text=match.group('norm'),
            unit_text=match.group('unit_text'),
            confidence=1.0,
            reason='non-boe-eu-reference',
        ))

    for match in _UNIT_THEN_NORM_RE.finditer(texto):
        if _overlaps(match, consumed):
            continue
        add(_build_unit_reference(match, options, override_data))

    for match in _EU_ONLY_RE.finditer(texto):
        if _overlaps(match, consumed):
            continue
        add(_reference(
            match.group(0), match.start(), match.end(), 'unsupported', 'unsupported',
            norm_text=match.group('norm'),
            confidence=1.0,
            reason='non-boe-eu-reference',
        ))

    for match in _NORM_ONLY_RE.finditer(texto):
        if _overlaps(match, consumed):
            continue
        add(_build_norm_reference(match, options, override_data))

    for match in _UNIT_ONLY_RE.finditer(texto):
        if _overlaps(match, consumed):
            continue
        inferred_norm = (
            _infer_single_active_norm(texto, match.start())
            if options.infer_single_active_norm
            else None
        )
        if inferred_norm:
            add(_build_unit_reference(match, options, override_data, inferred_norm=inferred_norm))
        else:
            add(_reference(
                match.group(0), match.start(), match.end(), 'unit', 'not-found',
                unit_text=match.group('unit_text'),
                confidence=0.0,
                reason='unit-without-norm',
            ))

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


def _enrich_reference(reference: BOEReference, options: BOEOptions, client: BOEClient) -> BOEReference:
    if reference.status in {'unsupported', 'ambiguous', 'not-found', 'manual'}:
        if reference.status != 'manual':
            return reference
    if reference.norm is None and reference.norm_text and reference.status == 'needs-boe-search':
        norm, candidates = client.resolve_norm(reference.norm_text)
        reference.candidates = candidates
        if norm is None:
            reference.status = 'ambiguous' if candidates else 'not-found'
            reference.reason = 'boe-search-ambiguous' if candidates else 'boe-search-not-found'
            return reference
        reference.norm = norm
        reference.status = 'resolved-url-only'
        reference.source = norm.source
        reference.reason = 'boe-search-resolved-url-only'

    if (
        reference.norm is not None
        and reference.unit_text
        and options.include_unit_text
    ):
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


def _unit_targets(unit_text: str) -> list[str]:
    normalized = _normalize_text(unit_text)
    if normalized.startswith('ART'):
        article_refs = re.findall(
            r'(\d+)(?:\s+(bis|ter|quater))?(?:\.\d+)*(?:\.[a-z])?\)?',
            unit_text,
            flags=re.IGNORECASE,
        )
        targets: list[str] = []
        if len(article_refs) >= 2 and re.search(r'\b(?:a|-)\b', unit_text):
            start, end = article_refs[0][0], article_refs[-1][0]
            if start.isdigit() and end.isdigit():
                start_i, end_i = int(start), int(end)
                if 0 < end_i - start_i <= 50:
                    return [f'artículo {number}' for number in range(start_i, end_i + 1)]
        for number, suffix in article_refs:
            target = f'artículo {number}'
            if suffix:
                target += f' {suffix.lower()}'
            if target not in targets:
                targets.append(target)
        return targets
    if normalized.startswith(('DISPOSICION', 'DISP', 'DA', 'DF', 'DT', 'DD')):
        return [_normalize_for_title(unit_text)]
    if normalized.startswith('ANEXO'):
        return [_normalize_for_title(unit_text)]
    return [_normalize_for_title(unit_text)]


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


def boe_report_to_markdown(output: BOEEnrichmentOutput) -> str:
    """
    Convierte un informe BOE a Markdown legible.
    """
    lines = [
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
    resolved = [item for item in output.references if item.status in {'resolved', 'resolved-url-only', 'manual'}]
    pending = [item for item in output.references if item.status in {'needs-boe-search', 'ambiguous', 'not-found', 'network-error'}]
    unsupported = [item for item in output.references if item.status == 'unsupported']

    if resolved:
        lines.extend([
            '## Referencias resueltas',
            '',
            '| Texto | Estado | Norma | Unidad | URL |',
            '| --- | --- | --- | --- | --- |',
        ])
        for item in resolved:
            norm_title = item.norm.title if item.norm else ''
            url = _best_url(item)
            lines.append(
                f"| {_md(item.original_text)} | {item.status} | {_md(norm_title)} | "
                f"{_md(item.unit_text or '')} | {url} |"
            )
            for block in item.unit_blocks:
                if block.text:
                    lines.extend(['', f"### {_md(block.title)}", '', block.text, ''])

    if pending:
        lines.extend([
            '',
            '## Requieren revisión',
            '',
            '| Texto | Estado | Motivo |',
            '| --- | --- | --- |',
        ])
        for item in pending:
            lines.append(f"| {_md(item.original_text)} | {item.status} | {_md(item.reason or '')} |")

    if unsupported:
        lines.extend([
            '',
            '## No soportadas',
            '',
            '| Texto | Motivo |',
            '| --- | --- |',
        ])
        for item in unsupported:
            lines.append(f"| {_md(item.original_text)} | {_md(item.reason or '')} |")

    if output.warnings:
        lines.extend(['', '## Avisos', ''])
        lines.extend(f"- {warning}" for warning in output.warnings)

    return '\n'.join(lines).strip() + '\n'


def _best_url(reference: BOEReference) -> str:
    if reference.unit_blocks:
        return reference.unit_blocks[0].url
    if reference.norm:
        return reference.norm.url
    return ''


def _md(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ')
