"""
legal-expand - Motor Principal de Expansión de Siglas

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Punto de entrada principal del motor de expansión de siglas legales españolas.
Orquesta el flujo completo: configuración → matching → formateo → salida.

ARQUITECTURA:
1. Verifica configuración global y opciones locales
2. Delega detección de siglas al módulo matcher
3. Aplica el formatter apropiado según opciones
4. Retorna el texto expandido o datos estructurados

RESPONSABILIDADES:
- Coordinar los diferentes módulos del sistema
- Validar y combinar opciones de configuración
- Proporcionar la API pública de alto nivel
- Manejar casos edge (texto vacío, expansión desactivada)

FLUJO DE PROCESAMIENTO:
1. Verifica si la expansión está habilitada (respeta force_expansion)
2. Combina opciones locales con configuración global
3. Busca matches de siglas usando el matcher
4. Aplica el formatter según el formato especificado
5. Retorna el resultado en el formato solicitado

INTEGRACIÓN CON OTROS MÓDULOS:
- config: Gestión de configuración y opciones
- matcher: Detección y validación de siglas en texto
- formatters: Transformación de matches a salida formateada
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
from typing import Optional, Union

from ..config import _get_config_manager
from ..formatters import FormatterFactory
from ..types import (
    AcronymSearchResult,
    AuditReport,
    AuditStats,
    BenchmarkResult,
    DiagnosticOutput,
    DictionaryInfo,
    DictionaryStats,
    ExtractedAcronym,
    ExtractionOutput,
    ExpansionOptions,
    GlossaryEntry,
    MatchRunResult,
    OmittedAcronym,
    Position,
    Stats,
    StructuredOutput,
)
from .normalizer import normalize
from .matcher import SiglasMatcher, get_matcher


_ACRONYM_CANDIDATE_RE = re.compile(
    r'(?<![a-zA-ZáéíóúñÑüÜ0-9])'
    r'((?:[A-ZÁÉÍÓÚÑÜ]{2,12})|(?:[A-ZÁÉÍÓÚÑÜ]\.){2,12})'
    r'(?![a-zA-ZáéíóúñÑüÜ0-9])'
)


# ============================================================================
# API PRINCIPAL DE EXPANSIÓN
# ============================================================================

def expandir_siglas(
    texto: str,
    opciones: Optional[ExpansionOptions] = None
) -> Union[str, StructuredOutput]:
    """
    Expande siglas legales españolas encontradas en un texto.

    Función principal de la librería. Analiza el texto de entrada, identifica
    siglas legales del diccionario y las expande según las opciones configuradas.

    Args:
        texto: Texto a procesar
        opciones: Opciones de expansión (opcional)

    Returns:
        Texto expandido (str) para formatos 'plain' y 'html',
        o StructuredOutput para formato 'structured'

    Example:
        >>> # Uso básico
        >>> expandir_siglas('La AEAT notifica el IVA')
        'La AEAT (Agencia Estatal de Administración Tributaria) notifica el IVA (Impuesto sobre el Valor Añadido)'

        >>> # Formato HTML
        >>> expandir_siglas('La AEAT...', ExpansionOptions(format='html'))
        'La <abbr title="Agencia...">AEAT</abbr> (Agencia...) ...'

        >>> # Formato estructurado
        >>> result = expandir_siglas('Texto con AEAT', ExpansionOptions(format='structured'))
        >>> result.stats.total_expanded
        1

        >>> # Expandir solo primera ocurrencia
        >>> expandir_siglas('AEAT procesa. AEAT cobra.', ExpansionOptions(expand_only_first=True))
        'AEAT (Agencia...) procesa. AEAT cobra.'

        >>> # Forzar expansión aunque esté desactivado globalmente
        >>> from legal_expand import configurar_globalmente, GlobalConfig
        >>> configurar_globalmente(GlobalConfig(enabled=False))
        >>> expandir_siglas('Texto con AEAT', ExpansionOptions(force_expansion=True))
        'Texto con AEAT (Agencia...)'
    """
    config_manager = _get_config_manager()

    # Verificar si debe expandir (respeta force_expansion sobre config.enabled)
    if not config_manager.should_expand(opciones):
        # Expansión desactivada: retornar texto sin modificar
        if opciones and opciones.format == 'structured':
            # Para formato estructurado, retornar objeto vacío pero válido
            return StructuredOutput(
                original_text=texto,
                expanded_text=texto,
                acronyms=[],
                stats=Stats(
                    total_acronyms_found=0,
                    total_expanded=0,
                    ambiguous_not_expanded=0
                )
            )
        return texto

    # Combinar opciones locales con defaults globales
    merged_options = config_manager.merge_options(opciones)

    # Obtener instancia del matcher (Singleton)
    matcher = get_matcher(merged_options.custom_dictionaries)

    # Buscar todas las siglas en el texto
    run_result = matcher.find_matches_detailed(texto, merged_options)

    # Aplicar el formatter apropiado para el formato solicitado
    formatter = FormatterFactory.get_formatter(merged_options.format)
    if (
        merged_options.format == 'structured'
        and hasattr(formatter, 'format_with_stats')
    ):
        return formatter.format_with_stats(  # type: ignore[attr-defined]
            texto,
            run_result.matches,
            run_result.stats
        )

    return formatter.format(texto, run_result.matches)


def expandir_siglas_detallado(
    texto: str,
    opciones: Optional[ExpansionOptions] = None
) -> DiagnosticOutput:
    """
    Expande siglas y devuelve diagnóstico completo de omisiones.

    Además de la salida estructurada estándar, incluye siglas detectadas
    pero no expandidas, con una razón estable: filtros, contexto protegido,
    repetición por expand_only_first, ambigüedad o not-found.

    Args:
        texto: Texto a procesar
        opciones: Opciones de expansión (opcional)

    Returns:
        DiagnosticOutput con expansiones, omisiones y estadísticas
    """
    config_manager = _get_config_manager()

    if not config_manager.should_expand(opciones):
        return DiagnosticOutput(
            original_text=texto,
            expanded_text=texto,
            acronyms=[],
            stats=Stats(
                total_acronyms_found=0,
                total_expanded=0,
                ambiguous_not_expanded=0
            ),
            omitted_acronyms=[]
        )

    merged_options = config_manager.merge_options(opciones)
    matcher = get_matcher(merged_options.custom_dictionaries)
    run_result = matcher.find_matches_detailed(texto, merged_options)

    structured_formatter = FormatterFactory.get_formatter('structured')
    structured = structured_formatter.format_with_stats(  # type: ignore[attr-defined]
        texto,
        run_result.matches,
        run_result.stats
    )

    omitted_acronyms = [
        OmittedAcronym(
            acronym=omitted.original,
            position=Position(start=omitted.start_pos, end=omitted.end_pos),
            reason=omitted.reason,
            details=omitted.details
        )
        for omitted in run_result.omitted_matches
    ]

    return DiagnosticOutput(
        original_text=structured.original_text,
        expanded_text=structured.expanded_text,
        acronyms=structured.acronyms,
        stats=structured.stats,
        omitted_acronyms=omitted_acronyms
    )


def _known_acronyms(run_result: MatchRunResult) -> tuple[list[ExtractedAcronym], set[tuple[int, int]]]:
    acronyms: list[ExtractedAcronym] = []
    occupied_spans: set[tuple[int, int]] = set()
    for match in run_result.matches:
        occupied_spans.add((match.start_pos, match.end_pos))
        acronyms.append(ExtractedAcronym(
            acronym=match.original,
            position=Position(match.start_pos, match.end_pos),
            known=True,
            expansion=match.expansion,
            has_multiple_meanings=match.has_multiple_meanings,
            all_meanings=match.all_meanings,
            source=match.source
        ))
    return acronyms, occupied_spans


def _omitted_acronyms(
    run_result: MatchRunResult,
    matcher: SiglasMatcher
) -> tuple[list[ExtractedAcronym], set[tuple[int, int]]]:
    acronyms: list[ExtractedAcronym] = []
    occupied_spans: set[tuple[int, int]] = set()
    for omitted in run_result.omitted_matches:
        occupied_spans.add((omitted.start_pos, omitted.end_pos))
        info = matcher.buscar_sigla(omitted.original)
        acronyms.append(ExtractedAcronym(
            acronym=omitted.original,
            position=Position(omitted.start_pos, omitted.end_pos),
            known=info is not None,
            expansion=info.meanings[0] if info and info.meanings else None,
            has_multiple_meanings=info.has_duplicates if info else False,
            all_meanings=info.meanings if info else None,
            omitted_reason=omitted.reason,
            details=omitted.details,
            source=info.source if info else None
        ))
    return acronyms, occupied_spans


def _unknown_acronyms(
    texto: str,
    matcher: SiglasMatcher,
    occupied_spans: set[tuple[int, int]]
) -> list[ExtractedAcronym]:
    acronyms: list[ExtractedAcronym] = []
    for candidate in _ACRONYM_CANDIDATE_RE.finditer(texto):
        span = (candidate.start(), candidate.end())
        if span in occupied_spans:
            continue

        acronym = candidate.group(0)
        if matcher.buscar_sigla(acronym):
            continue

        acronyms.append(ExtractedAcronym(
            acronym=acronym,
            position=Position(candidate.start(), candidate.end()),
            known=False,
            omitted_reason='not-found'
        ))
    return acronyms


def _mark_repeated_acronyms(acronyms: list[ExtractedAcronym]) -> None:
    totals: dict[str, int] = {}
    seen: dict[str, int] = {}
    for item in acronyms:
        key = normalize(item.acronym)
        totals[key] = totals.get(key, 0) + 1

    for item in acronyms:
        key = normalize(item.acronym)
        seen[key] = seen.get(key, 0) + 1
        item.occurrence_index = seen[key]
        item.total_occurrences = totals[key]
        item.repeated = totals[key] > 1


def extraer_siglas(
    texto: str,
    opciones: Optional[ExpansionOptions] = None,
    incluir_desconocidas: bool = True
) -> ExtractionOutput:
    """
    Detecta siglas sin modificar el texto.

    Incluye siglas conocidas del diccionario y, opcionalmente, candidatos
    desconocidos en mayúsculas para auditoría documental.
    """
    config_manager = _get_config_manager()
    merged_options = config_manager.merge_options(opciones)
    matcher = get_matcher(merged_options.custom_dictionaries)
    run_result = matcher.find_matches_detailed(texto, merged_options)

    known_acronyms, known_spans = _known_acronyms(run_result)
    omitted_acronyms, omitted_spans = _omitted_acronyms(run_result, matcher)
    acronyms = known_acronyms + omitted_acronyms

    occupied_spans = known_spans | omitted_spans
    if incluir_desconocidas:
        acronyms.extend(_unknown_acronyms(texto, matcher, occupied_spans))

    acronyms.sort(key=lambda item: item.position.start)
    _mark_repeated_acronyms(acronyms)

    return ExtractionOutput(original_text=texto, acronyms=acronyms)


def generar_glosario(
    texto: str,
    opciones: Optional[ExpansionOptions] = None
) -> list[GlossaryEntry]:
    """
    Genera un glosario único de siglas conocidas detectadas.
    """
    extraction = extraer_siglas(texto, opciones, incluir_desconocidas=False)
    entries: dict[str, GlossaryEntry] = {}

    for item in extraction.acronyms:
        if not item.known or not item.expansion:
            continue

        key = normalize(item.acronym)
        if key not in entries:
            entries[key] = GlossaryEntry(
                acronym=item.acronym,
                expansion=item.expansion,
                count=0,
                first_position=item.position,
                has_multiple_meanings=item.has_multiple_meanings,
                all_meanings=item.all_meanings,
                source=item.source
            )

        entries[key].count += 1

    return sorted(entries.values(), key=lambda entry: entry.first_position.start)


def exportar_glosario(
    texto: str,
    formato: str = 'markdown',
    opciones: Optional[ExpansionOptions] = None
) -> str:
    """
    Exporta el glosario en markdown, csv o json.
    """
    glossary = generar_glosario(texto, opciones)
    normalized_format = formato.lower()

    if normalized_format == 'json':
        return json.dumps(
            [entry.to_dict() for entry in glossary],
            ensure_ascii=False,
            indent=2
        )

    if normalized_format == 'csv':
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                'acronym',
                'expansion',
                'count',
                'first_position_start',
                'first_position_end',
                'source',
            ]
        )
        writer.writeheader()
        for entry in glossary:
            writer.writerow({
                'acronym': entry.acronym,
                'expansion': entry.expansion,
                'count': entry.count,
                'first_position_start': entry.first_position.start,
                'first_position_end': entry.first_position.end,
                'source': entry.source or '',
            })
        return output.getvalue()

    if normalized_format == 'markdown':
        rows = [
            '| Sigla | Significado | Apariciones |',
            '| --- | --- | ---: |',
        ]
        for entry in glossary:
            rows.append(
                f"| {entry.acronym} | {entry.expansion} | {entry.count} |"
            )
        return '\n'.join(rows)

    raise ValueError("Unsupported glossary format. Use markdown, csv or json.")


def auditar_texto(
    texto: str,
    opciones: Optional[ExpansionOptions] = None
) -> AuditReport:
    """
    Audita un texto sin modificarlo.
    """
    diagnostic = expandir_siglas_detallado(texto, opciones)
    extraction = extraer_siglas(texto, opciones, incluir_desconocidas=True)
    glossary = generar_glosario(texto, opciones)
    unknown = [item for item in extraction.acronyms if not item.known]

    stats = AuditStats(
        total_detected=len(extraction.acronyms),
        total_known=sum(1 for item in extraction.acronyms if item.known),
        total_unknown=len(unknown),
        total_expanded=diagnostic.stats.total_expanded,
        total_omitted=len(diagnostic.omitted_acronyms),
        total_repeated=sum(1 for item in extraction.acronyms if item.repeated)
    )

    return AuditReport(
        original_text=texto,
        stats=stats,
        acronyms=extraction.acronyms,
        glossary=glossary,
        omitted_acronyms=diagnostic.omitted_acronyms,
        unknown_acronyms=unknown
    )


def benchmark_texto(
    texto: str,
    opciones: Optional[ExpansionOptions] = None,
    iterations: int = 100
) -> BenchmarkResult:
    """
    Mide rendimiento de expansión para un texto.
    """
    if iterations <= 0:
        raise ValueError("iterations must be greater than 0")

    start = time.perf_counter()
    for _ in range(iterations):
        expandir_siglas(texto, opciones)
    total_seconds = time.perf_counter() - start
    average_ms = (total_seconds / iterations) * 1000
    total_characters = len(texto) * iterations

    return BenchmarkResult(
        iterations=iterations,
        total_seconds=total_seconds,
        average_ms=average_ms,
        characters=len(texto),
        characters_per_second=(
            total_characters / total_seconds
            if total_seconds > 0
            else 0.0
        )
    )


# ============================================================================
# API DE CONSULTA DEL DICCIONARIO
# ============================================================================

def buscar_sigla(
    sigla: str,
    custom_dictionaries: Optional[list[str]] = None
) -> Optional[AcronymSearchResult]:
    """
    Busca información sobre una sigla específica en el diccionario.

    Útil para construir UIs de autocompletado, tooltips o para validar
    si una sigla está en el diccionario antes de procesarla.

    Args:
        sigla: La sigla a buscar (ej: "AEAT", "BOE")

    Returns:
        AcronymSearchResult con información de la sigla, o None si no existe

    Example:
        >>> result = buscar_sigla('AEAT')
        >>> result.meanings
        ['Agencia Estatal de Administración Tributaria']
        >>> result.has_duplicates
        False

        >>> result = buscar_sigla('NOEXISTE')
        >>> result is None
        True
    """
    matcher = get_matcher(custom_dictionaries)
    return matcher.buscar_sigla(sigla)


def listar_siglas(custom_dictionaries: Optional[list[str]] = None) -> list[str]:
    """
    Obtiene una lista de todas las siglas disponibles en el diccionario.

    Útil para generar índices, construir selectores de autocompletado
    o para propósitos de documentación.

    Returns:
        Lista ordenada de todas las siglas disponibles

    Example:
        >>> siglas = listar_siglas()
        >>> len(siglas)
        646
        >>> siglas[:5]
        ['AEAT', 'AENA', 'AIE', 'AJD', ...]
    """
    matcher = get_matcher(custom_dictionaries)
    return matcher.listar_siglas()


def obtener_estadisticas(
    custom_dictionaries: Optional[list[str]] = None
) -> DictionaryStats:
    """
    Obtiene estadísticas generales sobre el diccionario de siglas.

    Proporciona métricas útiles para debugging, monitoreo y documentación.

    Returns:
        DictionaryStats con métricas del diccionario

    Example:
        >>> stats = obtener_estadisticas()
        >>> stats.total_acronyms
        646
        >>> stats.acronyms_with_duplicates
        0
    """
    matcher = get_matcher(custom_dictionaries)
    return matcher.obtener_estadisticas()


def obtener_info_diccionario(
    custom_dictionaries: Optional[list[str]] = None
) -> DictionaryInfo:
    """
    Obtiene metadata del diccionario base y de diccionarios personalizados.
    """
    matcher = get_matcher(custom_dictionaries)
    return matcher.obtener_info_diccionario()
