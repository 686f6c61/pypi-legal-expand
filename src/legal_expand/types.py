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

from dataclasses import dataclass, field
from typing import Literal, Optional


# ============================================================================
# TIPOS PÚBLICOS
# ============================================================================

@dataclass
class ExpansionOptions:
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
    """
    format: Literal['plain', 'html', 'structured'] = 'plain'
    force_expansion: Optional[bool] = None
    preserve_case: bool = True
    auto_resolve_duplicates: bool = False
    duplicate_resolution: dict[str, str] = field(default_factory=dict)
    expand_only_first: bool = False
    exclude: list[str] = field(default_factory=list)
    include: Optional[list[str]] = None


@dataclass
class Position:
    """
    Posición de una sigla en el texto.

    Attributes:
        start: Índice de inicio (inclusive)
        end: Índice de fin (exclusive)
    """
    start: int
    end: int


@dataclass
class ExpandedAcronym:
    """
    Información pública de una sigla expandida.

    Attributes:
        acronym: La sigla original encontrada
        expansion: El significado completo
        position: Posición en el texto original
        has_multiple_meanings: Indica si tiene múltiples significados posibles
        all_meanings: Lista de todos los significados posibles (si aplica)
    """
    acronym: str
    expansion: str
    position: Position
    has_multiple_meanings: bool = False
    all_meanings: Optional[list[str]] = None


@dataclass
class Stats:
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
class StructuredOutput:
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


@dataclass
class GlobalConfig:
    """
    Configuración global del paquete.

    Attributes:
        enabled: Activar/desactivar la expansión globalmente
        default_options: Opciones por defecto para todas las llamadas
    """
    enabled: bool = True
    default_options: Optional[ExpansionOptions] = None


@dataclass
class AcronymSearchResult:
    """
    Resultado de búsqueda de una sigla en el diccionario.

    Attributes:
        acronym: La sigla buscada
        meanings: Lista de significados encontrados
        has_duplicates: Indica si hay múltiples significados
    """
    acronym: str
    meanings: list[str]
    has_duplicates: bool


@dataclass
class DictionaryStats:
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
    """
    original: str
    expansion: str
    start_pos: int
    end_pos: int
    confidence: float = 1.0
    has_multiple_meanings: bool = False
    all_meanings: Optional[list[str]] = None


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
    """
    id: str
    original: str
    significado: str
    variants: list[str]
    priority: int = 100


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
