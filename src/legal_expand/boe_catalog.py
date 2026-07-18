"""
Resolución de normas del BOE mediante un índice local del catálogo de
legislación consolidada.

La API de datos abiertos del BOE **no ofrece búsqueda por texto** (el parámetro
``query`` devuelve HTTP 500). Es un listado paginado accesible por identificador.
Para poder resolver cualquier norma española citada por su rango y número
oficial (por ejemplo «Ley Orgánica 3/2018» → ``BOE-A-2018-16673``) sin depender
de esa búsqueda inexistente, este módulo carga un índice compacto
(``data/boe_index.json``) generado a partir del catálogo consolidado del BOE.

El índice mapea ``numero_oficial`` (por ejemplo ``"3/2018"``) a la lista de
normas que comparten ese número, cada una descrita de forma compacta como
``[identificador, rango, ambito, fecha]``. La resolución filtra por rango y, ante
varias candidatas, prefiere la estatal; si sigue habiendo ambigüedad no resuelve
(coherente con el criterio conservador del paquete: nunca inventa una norma).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from .types import BOENorm


_LOGGER = logging.getLogger(__name__)

_INDEX_PATH = Path(__file__).parent / 'data' / 'boe_index.json'

# Posiciones de cada campo en las entradas compactas del índice.
_ID, _RANGO, _AMBITO, _FECHA = 0, 1, 2, 3

# Variantes de rango tal como aparecen en las citas (normalizadas a minúsculas y
# sin acentos) mapeadas al rango exacto que usa el catálogo del BOE. Una misma
# abreviatura puede corresponder a varios rangos (por ejemplo «RDL»), en cuyo
# caso se listan todos los candidatos.
_RANGO_ALIASES: dict[str, tuple[str, ...]] = {
    'ley organica': ('Ley Orgánica',),
    'lo': ('Ley Orgánica',),
    'ley foral': ('Ley Foral',),
    'ley': ('Ley',),
    'real decreto-ley': ('Real Decreto-ley',),
    'real decreto ley': ('Real Decreto-ley',),
    'rd-ley': ('Real Decreto-ley',),
    'rd-l': ('Real Decreto-ley',),
    'real decreto legislativo': ('Real Decreto Legislativo',),
    'rd legislativo': ('Real Decreto Legislativo',),
    'rdleg': ('Real Decreto Legislativo',),
    'rdl': ('Real Decreto-ley', 'Real Decreto Legislativo'),
    'real decreto': ('Real Decreto',),
    'rd': ('Real Decreto',),
    'decreto-ley': ('Decreto-ley',),
    'decreto legislativo': ('Decreto Legislativo',),
    'decreto': ('Decreto',),
    'orden': ('Orden',),
    'resolucion': ('Resolución',),
    'circular': ('Circular',),
    'instruccion': ('Instrucción',),
    'acuerdo internacional': ('Acuerdo Internacional',),
    'acuerdo': ('Acuerdo',),
}

# Rangos ordenados por longitud descendente para que «Real Decreto Legislativo»
# gane a «Real Decreto» al identificar el prefijo de la cita.
_RANGO_KEYS = sorted(_RANGO_ALIASES, key=len, reverse=True)

_MESES = (
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
    'septiembre', 'octubre', 'noviembre', 'diciembre',
)

# numero_oficial: 39/2015, 3/2018, o con prefijo de departamento (HFP/1030/2021).
_NUMERO_RE = re.compile(r'(?:[A-Za-zÁÉÍÓÚÑ]{2,8}/)?\d{1,5}/[12]\d{3}')


@lru_cache(maxsize=1)
def _load_index() -> dict[str, Any]:
    """Carga el índice del catálogo BOE una sola vez."""
    try:
        data = json.loads(_INDEX_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        # Un fallo aquí suele indicar un problema de empaquetado del .json.
        # Se degrada a índice vacío (no inventa normas) pero se deja constancia.
        _LOGGER.warning('No se pudo cargar el índice BOE (%s): %s', _INDEX_PATH, exc)
        return {'index': {}}
    return data if isinstance(data, dict) else {'index': {}}


def _strip_accents(text: str) -> str:
    table = str.maketrans({
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u', 'ñ': 'n',
        'Á': 'a', 'É': 'e', 'Í': 'i', 'Ó': 'o', 'Ú': 'u', 'Ü': 'u', 'Ñ': 'n',
    })
    return text.translate(table)


def _boe_url(boe_id: str) -> str:
    return f'https://www.boe.es/buscar/act.php?id={urllib.parse.quote(boe_id)}'


def _fecha_legible(fecha: str) -> str:
    """Convierte una fecha AAAAMMDD del catálogo en «5 de diciembre de 2018»."""
    if len(fecha) != 8 or not fecha.isdigit():
        return ''
    anio, mes, dia = fecha[:4], int(fecha[4:6]), int(fecha[6:8])
    if not 1 <= mes <= 12:
        return ''
    return f'{dia} de {_MESES[mes - 1]} de {anio}'


def _compose_title(rango: str, numero: str, fecha: str) -> str:
    """Título legible a partir de rango, número y fecha (sin la materia)."""
    fecha_texto = _fecha_legible(fecha)
    base = f'{rango} {numero}'
    return f'{base}, de {fecha_texto}' if fecha_texto else base


def _candidate_rangos(rango_text: str) -> tuple[str, ...]:
    """Devuelve los rangos de catálogo compatibles con el prefijo citado."""
    normalized = re.sub(r'\s+', ' ', _strip_accents(rango_text).lower()).strip()
    normalized = normalized.rstrip('.')
    for key in _RANGO_KEYS:
        if normalized == key or normalized.endswith(' ' + key) or normalized.startswith(key + ' '):
            return _RANGO_ALIASES[key]
    return ()


def parse_citation(text: str) -> Optional[tuple[str, str]]:
    """
    Extrae (texto de rango, número oficial) de una cita de norma.

    Por ejemplo «Ley Orgánica 3/2018, de 5 de diciembre» -> ("Ley Orgánica", "3/2018").
    Devuelve None si no hay un número oficial reconocible.
    """
    match = _NUMERO_RE.search(text)
    if match is None:
        return None
    numero = match.group(0)
    rango_text = text[:match.start()].strip()
    return rango_text, numero


def resolve_norm_from_catalog(norm_text: str) -> Optional[BOENorm]:
    """
    Resuelve una norma citada contra el índice del catálogo consolidado del BOE.

    Devuelve un BOENorm con identificador, título compuesto y URL oficial cuando
    la resolución es inequívoca (una sola norma, prefiriendo la estatal). Ante
    ambigüedad o ausencia de coincidencia devuelve None, sin inventar.
    """
    parsed = parse_citation(norm_text)
    if parsed is None:
        return None
    rango_text, numero = parsed

    entries = _load_index().get('index', {}).get(numero)
    if not entries:
        return None

    candidate_rangos = _candidate_rangos(rango_text)
    if candidate_rangos:
        matches = [entry for entry in entries if entry[_RANGO] in candidate_rangos]
    else:
        # Sin rango explícito en la cita: solo se resuelve si hay una única norma.
        matches = list(entries)
    if not matches:
        return None

    # Preferir la norma estatal cuando conviven estatal y autonómicas.
    estatales = [entry for entry in matches if entry[_AMBITO] == 'E']
    pool = estatales or matches
    if len(pool) != 1:
        return None  # ambiguo: no se resuelve automáticamente

    boe_id, rango, _ambito, fecha = pool[0]
    return BOENorm(
        boe_id=boe_id,
        title=_compose_title(rango, numero, fecha),
        url=_boe_url(boe_id),
        official_number=numero,
        rank=rango,
        source='boe-index',
    )
