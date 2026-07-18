"""
legal-expand - Definiciones de tipos y estructuras de datos

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Define todas las estructuras de datos utilizadas en el paquete.
Implementa dataclasses inmutables para seguridad y claridad.

ARQUITECTURA:
El sistema de tipos se organiza en tres capas:
1. Tipos públicos: Expuestos a usuarios del paquete
2. Tipos internos: Usados solo dentro del paquete
3. Tipos de configuración: Para gestión de opciones

RESPONSABILIDADES:
- Definir contratos de datos claros
- Proporcionar type hints para IDE y mypy
- Documentar estructura de datos esperada
- Facilitar validación de datos

CARACTERÍSTICAS:
- Dataclasses con valores por defecto sensatos
- Campos opcionales marcados con Optional
- Documentación completa de cada campo
- Compatibilidad con serialización JSON

TIPOS PÚBLICOS PRINCIPALES:
- ExpansionOptions: Opciones de configuración
- ExpandedAcronym: Sigla expandida con metadata
- StructuredOutput: Salida completa estructurada
- GlobalConfig: Configuración global del paquete
- AcronymSearchResult: Resultado de búsqueda
- DictionaryStats: Estadísticas del diccionario
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Literal, Optional


def _to_plain(value: Any) -> Any:
    """Convierte dataclasses y contenedores anidados a tipos JSON-friendly."""
    if is_dataclass(value):
        return {
            key: _to_plain(val)
            for key, val in value.__dict__.items()
            if not key.startswith('_')
        }
    if isinstance(value, dict):
        return {str(key): _to_plain(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_plain(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


class SerializableMixin:
    """Mixin pequeño para exponer resultados como dict o JSON."""

    def to_dict(self) -> dict[str, Any]:
        return _to_plain(self)

    def to_json(self, *, ensure_ascii: bool = False, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)


# ============================================================================
# TIPOS PÚBLICOS
# ============================================================================

@dataclass
class ExpansionOptions(SerializableMixin):
    """
    Opciones para configurar el comportamiento de la expansión de siglas.

    Attributes:
        format: Formato de salida ('plain', 'html', 'structured')
        force_expansion: Override de configuración global (None respeta global)
        preserve_case: Mantener mayúsculas originales en búsqueda
        auto_resolve_duplicates: Resolver automáticamente siglas con múltiples significados
        duplicate_resolution: Mapa manual de resolución de duplicados
        expand_only_first: Expandir solo la primera ocurrencia de cada sigla
        exclude: Lista de siglas a ignorar
        include: Lista de siglas a incluir (si se proporciona, solo estas se expanden)
        custom_dictionaries: Rutas a diccionarios JSON/CSV adicionales
    """
    format: Literal['plain', 'html', 'structured'] = 'plain'
    force_expansion: Optional[bool] = None
    preserve_case: bool = True
    auto_resolve_duplicates: bool = False
    duplicate_resolution: dict[str, str] = field(default_factory=dict)
    expand_only_first: bool = False
    exclude: list[str] = field(default_factory=list)
    include: Optional[list[str]] = None
    custom_dictionaries: list[str] = field(default_factory=list)


@dataclass
class Position(SerializableMixin):
    """
    Posición de una sigla en el texto.

    Attributes:
        start: Índice de inicio (inclusive)
        end: Índice de fin (exclusive)
    """
    start: int
    end: int


@dataclass
class ExpandedAcronym(SerializableMixin):
    """
    Información pública de una sigla expandida.

    Attributes:
        acronym: La sigla original encontrada
        expansion: El significado completo
        position: Posición en el texto original
        has_multiple_meanings: Indica si tiene múltiples significados posibles
        all_meanings: Lista de todos los significados posibles (si aplica)
        source: Fuente opcional si procede de un diccionario personalizado
    """
    acronym: str
    expansion: str
    position: Position
    has_multiple_meanings: bool = False
    all_meanings: Optional[list[str]] = None
    source: Optional[str] = None


@dataclass
class Stats(SerializableMixin):
    """
    Estadísticas de procesamiento de un texto.

    Attributes:
        total_acronyms_found: Total de siglas detectadas en el texto
        total_expanded: Siglas efectivamente expandidas
        ambiguous_not_expanded: Siglas ambiguas que no fueron expandidas
    """
    total_acronyms_found: int
    total_expanded: int
    ambiguous_not_expanded: int


@dataclass
class StructuredOutput(SerializableMixin):
    """
    Salida estructurada con metadata completa del procesamiento.

    Attributes:
        original_text: Texto original sin modificar
        expanded_text: Texto con las siglas expandidas
        acronyms: Lista de todas las siglas procesadas
        stats: Estadísticas del procesamiento
    """
    original_text: str
    expanded_text: str
    acronyms: list[ExpandedAcronym]
    stats: Stats


OmittedAcronymReason = Literal[
    'excluded',
    'not-in-include',
    'expand-only-first',
    'ambiguous-unresolved',
    'inside-url',
    'inside-email',
    'inside-code-block',
    'inside-inline-code',
    'common-word',
    'not-found',
]


@dataclass
class OmittedAcronym(SerializableMixin):
    """
    Información de una sigla detectada pero no expandida.

    Attributes:
        acronym: Sigla original detectada
        position: Posición en el texto original
        reason: Motivo estable por el que se omitió la expansión
        details: Detalle opcional para depuración o UI
    """
    acronym: str
    position: Position
    reason: OmittedAcronymReason
    details: Optional[str] = None


@dataclass
class DiagnosticOutput(StructuredOutput):
    """
    Salida estructurada con trazabilidad de siglas omitidas.

    Extiende StructuredOutput añadiendo omitted_acronyms, una lista de
    detecciones que no se expandieron por filtros, contexto protegido,
    repetición o ambigüedad.
    """
    omitted_acronyms: list[OmittedAcronym] = field(default_factory=list)


@dataclass
class GlobalConfig(SerializableMixin):
    """
    Configuración global del paquete.

    Attributes:
        enabled: Activar/desactivar la expansión globalmente
        default_options: Opciones por defecto para todas las llamadas
    """
    enabled: bool = True
    default_options: Optional[ExpansionOptions] = None


@dataclass
class AcronymSearchResult(SerializableMixin):
    """
    Resultado de búsqueda de una sigla en el diccionario.

    Attributes:
        acronym: La sigla buscada
        meanings: Lista de significados encontrados
        has_duplicates: Indica si hay múltiples significados
        source: Fuente opcional si procede de un diccionario personalizado
    """
    acronym: str
    meanings: list[str]
    has_duplicates: bool
    source: Optional[str] = None


@dataclass
class DictionaryStats(SerializableMixin):
    """
    Estadísticas del diccionario de siglas.

    Attributes:
        total_acronyms: Total de siglas únicas en el diccionario
        acronyms_with_duplicates: Siglas con múltiples significados
        acronyms_with_punctuation: Siglas que contienen puntuación
    """
    total_acronyms: int
    acronyms_with_duplicates: int
    acronyms_with_punctuation: int


@dataclass
class DictionaryInfo(SerializableMixin):
    """
    Metadata del diccionario cargado.
    """
    dictionary_version: str
    build_date: str
    total_entries: int
    total_acronyms: int
    total_variants: int
    conflicts: int
    custom_dictionaries: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class ExtractedAcronym(SerializableMixin):
    """
    Sigla detectada sin modificar el texto.
    """
    acronym: str
    position: Position
    known: bool
    expansion: Optional[str] = None
    has_multiple_meanings: bool = False
    all_meanings: Optional[list[str]] = None
    omitted_reason: Optional[OmittedAcronymReason] = None
    details: Optional[str] = None
    repeated: bool = False
    occurrence_index: int = 1
    total_occurrences: int = 1
    source: Optional[str] = None


@dataclass
class ExtractionOutput(SerializableMixin):
    """
    Resultado de extracción de siglas sin expansión inline.
    """
    original_text: str
    acronyms: list[ExtractedAcronym]


@dataclass
class GlossaryEntry(SerializableMixin):
    """
    Entrada única de glosario.
    """
    acronym: str
    expansion: str
    count: int
    first_position: Position
    has_multiple_meanings: bool = False
    all_meanings: Optional[list[str]] = None
    source: Optional[str] = None


@dataclass
class AuditStats(SerializableMixin):
    """
    Estadísticas de auditoría de un texto o documento.
    """
    total_detected: int
    total_known: int
    total_unknown: int
    total_expanded: int
    total_omitted: int
    total_repeated: int


@dataclass
class AuditReport(SerializableMixin):
    """
    Informe de auditoría sin modificar el documento.
    """
    original_text: str
    stats: AuditStats
    acronyms: list[ExtractedAcronym]
    glossary: list[GlossaryEntry]
    omitted_acronyms: list[OmittedAcronym]
    unknown_acronyms: list[ExtractedAcronym]


BOEMode = Literal['offline', 'cache-first', 'online']
BOEReferenceKind = Literal[
    'boe-id',
    'norm',
    'unit',
    'eu',
    'unsupported',
]
BOEReferenceStatus = Literal[
    'manual',
    'resolved',
    'resolved-url-only',
    'resolved-eurlex',
    'needs-boe-search',
    'ambiguous',
    'unsupported',
    'not-found',
    'network-error',
]


@dataclass
class BOEOptions(SerializableMixin):
    """
    Opciones para detección y enriquecimiento de referencias BOE.

    La integración BOE es opt-in y conservadora: nunca interpreta el
    documento ni inventa artículos, solo enlaza referencias explícitas o
    confirmadas mediante overrides/manual.
    """
    mode: BOEMode = 'offline'
    timeout_seconds: float = 4.0
    max_results: int = 5
    include_unit_text: bool = True
    infer_single_active_norm: bool = True
    use_curated_aliases: bool = True
    use_boe_index: bool = True
    cache_path: Optional[str] = None
    cache_ttl_days: int = 30
    overrides_path: Optional[str] = None
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5


@dataclass
class BOENorm(SerializableMixin):
    """
    Norma BOE resuelta o candidata.
    """
    boe_id: str
    title: str
    url: str
    official_number: Optional[str] = None
    rank: Optional[str] = None
    source: str = 'boe'


@dataclass
class BOEUnitBlock(SerializableMixin):
    """
    Bloque concreto dentro de una norma consolidada: artículo, disposición o anexo.
    """
    unit: str
    block_id: Optional[str]
    title: str
    url: str
    text: Optional[str] = None
    source: str = 'boe'


@dataclass
class BOEReference(SerializableMixin):
    """
    Referencia legal detectada en un texto.

    status distingue entre lo resuelto automáticamente, lo añadido por una
    persona, lo ambiguo y lo que queda pendiente para no crear falsas certezas.
    """
    original_text: str
    position: Position
    kind: BOEReferenceKind
    status: BOEReferenceStatus
    norm_text: Optional[str] = None
    unit_text: Optional[str] = None
    norm: Optional[BOENorm] = None
    unit_blocks: list[BOEUnitBlock] = field(default_factory=list)
    confidence: float = 0.0
    source: str = 'detector'
    reason: Optional[str] = None
    candidates: list[BOENorm] = field(default_factory=list)


@dataclass
class BOEEnrichmentStats(SerializableMixin):
    """
    Resumen estable del informe BOE.
    """
    total_detected: int
    total_resolved: int
    total_manual: int
    total_ambiguous: int
    total_unresolved: int
    total_unsupported: int


@dataclass
class BOEEnrichmentOutput(SerializableMixin):
    """
    Salida completa de detección/enriquecimiento BOE.
    """
    original_text: str
    references: list[BOEReference]
    stats: BOEEnrichmentStats
    warnings: list[str] = field(default_factory=list)


BOEReviewSection = Literal[
    'resolved',
    'manual',
    'review-required',
    'unsupported',
]


@dataclass
class BOEReviewItem(SerializableMixin):
    """
    Elemento de revisión BOE con explicación y acción sugerida.

    No sustituye a BOEReference: lo envuelve para que la salida histórica siga
    siendo estable y las UIs puedan mostrar por qué una referencia quedó en una
    sección concreta.
    """
    reference: BOEReference
    section: BOEReviewSection
    explanation: str
    suggested_action: str


@dataclass
class BOEReviewSummary(SerializableMixin):
    """
    Resumen orientado a revisión humana.
    """
    total_references: int
    resolved: int
    manual: int
    review_required: int
    unsupported: int
    ready_count: int


@dataclass
class BOEReviewOutput(SerializableMixin):
    """
    Salida BOE agrupada para revisión legal.
    """
    original_text: str
    items: list[BOEReviewItem]
    summary: BOEReviewSummary
    warnings: list[str] = field(default_factory=list)


@dataclass
class BatchResult(SerializableMixin):
    """
    Resultado de procesar un archivo dentro de un lote.
    """
    input_path: str
    output_path: str
    processed: bool
    error: Optional[str] = None


@dataclass
class BenchmarkResult(SerializableMixin):
    """
    Resultado de benchmark simple de expansión.
    """
    iterations: int
    total_seconds: float
    average_ms: float
    characters: int
    characters_per_second: float


# ============================================================================
# TIPOS INTERNOS
# ============================================================================

@dataclass
class MatchInfo:
    """
    Información interna de un match encontrado.

    Uso interno del paquete para pasar datos entre matcher y formatters.

    Attributes:
        original: Sigla original encontrada en el texto
        expansion: Texto de expansión/significado
        start_pos: Posición inicial en el texto
        end_pos: Posición final en el texto
        confidence: Nivel de confianza del match (0.0-1.0)
        has_multiple_meanings: Si tiene múltiples significados posibles
        all_meanings: Todos los significados posibles
        source: Fuente opcional
    """
    original: str
    expansion: str
    start_pos: int
    end_pos: int
    confidence: float = 1.0
    has_multiple_meanings: bool = False
    all_meanings: Optional[list[str]] = None
    source: Optional[str] = None


@dataclass
class OmittedMatchInfo:
    """
    Información interna de un match omitido.

    Uso interno del matcher para construir salidas de diagnóstico.
    """
    original: str
    start_pos: int
    end_pos: int
    reason: OmittedAcronymReason
    details: Optional[str] = None


@dataclass
class MatchRunStats:
    """
    Estadísticas internas del proceso de matching.
    """
    total_acronyms_found: int = 0
    ambiguous_not_expanded: int = 0


@dataclass
class MatchRunResult:
    """
    Resultado interno completo de una ejecución del matcher.
    """
    matches: list[MatchInfo]
    omitted_matches: list[OmittedMatchInfo]
    stats: MatchRunStats


@dataclass
class DictionaryEntry:
    """
    Entrada del diccionario de siglas.

    Representa una sigla con su significado y variantes.

    Attributes:
        id: Identificador único de la entrada
        original: Forma original/canónica de la sigla
        significado: Definición completa
        variants: Lista de variantes alternativas
        priority: Prioridad para resolución de conflictos (mayor = más prioritario)
        source: Fuente opcional
        context_keywords: Palabras clave para resolver ambigüedad por contexto
    """
    id: str
    original: str
    significado: str
    variants: list[str]
    priority: int = 100
    source: Optional[str] = None
    context_keywords: list[str] = field(default_factory=list)


@dataclass
class InternalOptions:
    """
    Opciones internas completamente resueltas (sin valores None).

    Versión interna de ExpansionOptions donde todos los valores
    están garantizados de tener un valor (no None).
    """
    format: Literal['plain', 'html', 'structured'] = 'plain'
    force_expansion: Optional[bool] = None
    preserve_case: bool = True
    auto_resolve_duplicates: bool = False
    duplicate_resolution: dict[str, str] = field(default_factory=dict)
    expand_only_first: bool = False
    exclude: list[str] = field(default_factory=list)
    include: Optional[list[str]] = None
    custom_dictionaries: list[str] = field(default_factory=list)
