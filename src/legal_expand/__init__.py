"""
legal-expand - Expansión inteligente de siglas legales españolas

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Punto de entrada principal del paquete legal-expand para Python.
Librería para expandir automáticamente siglas legales en textos
jurídicos españoles, añadiendo su significado completo.

646 siglas legales verificadas de fuentes oficiales (RAE, BOE, DPEJ).

ARQUITECTURA:
Este módulo actúa como fachada pública del paquete, exponiendo:
1. Funciones principales de expansión (expandir_siglas, buscar_sigla)
2. Sistema de configuración global
3. Factory de formatters para extensibilidad
4. Tipos públicos para type hints

RESPONSABILIDADES:
- Exportar la API pública del paquete
- Proporcionar documentación de alto nivel
- Mantener compatibilidad de versiones
- Facilitar imports simplificados

INTEGRACIÓN CON OTROS MÓDULOS:
- core/engine: Motor principal de expansión
- core/matcher: Detección y validación de siglas
- config: Sistema de configuración global
- formatters: Transformación de salida
- types: Definiciones de tipos

Example:
    >>> from legal_expand import expandir_siglas
    >>> expandir_siglas('La AEAT notifica el IVA')
    'La AEAT (Agencia Estatal de Administración Tributaria) notifica el IVA (Impuesto sobre el Valor Añadido)'

    >>> from legal_expand import expandir_siglas, ExpansionOptions
    >>> expandir_siglas('La AEAT', ExpansionOptions(format='html'))
    'La <abbr title="Agencia...">AEAT</abbr> (Agencia...)'

    >>> from legal_expand import buscar_sigla
    >>> buscar_sigla('AEAT').meanings
    ['Agencia Estatal de Administración Tributaria']
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "686f6c61"

# ============================================================================
# FUNCIONES PRINCIPALES
# ============================================================================

from .core.engine import (
    buscar_sigla,
    expandir_siglas,
    listar_siglas,
    obtener_estadisticas,
)

# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

from .config import (
    configurar_globalmente,
    obtener_configuracion_global,
    resetear_configuracion,
)

# ============================================================================
# FORMATTERS (EXTENSIBILIDAD)
# ============================================================================

from .formatters import Formatter, FormatterFactory

# ============================================================================
# TIPOS
# ============================================================================

from .types import (
    AcronymSearchResult,
    DictionaryStats,
    ExpandedAcronym,
    ExpansionOptions,
    GlobalConfig,
    Position,
    Stats,
    StructuredOutput,
)

# ============================================================================
# EXPORTS PÚBLICOS
# ============================================================================

__all__ = [
    # Versión
    "__version__",
    "__author__",
    # Funciones principales
    "expandir_siglas",
    "buscar_sigla",
    "listar_siglas",
    "obtener_estadisticas",
    # Configuración global
    "configurar_globalmente",
    "obtener_configuracion_global",
    "resetear_configuracion",
    # Formatters
    "Formatter",
    "FormatterFactory",
    # Tipos
    "ExpansionOptions",
    "ExpandedAcronym",
    "StructuredOutput",
    "GlobalConfig",
    "AcronymSearchResult",
    "DictionaryStats",
    "Position",
    "Stats",
]
