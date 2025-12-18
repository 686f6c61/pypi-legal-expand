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

from typing import Optional, Union

from ..config import _get_config_manager
from ..formatters import FormatterFactory
from ..types import (
    AcronymSearchResult,
    DictionaryStats,
    ExpansionOptions,
    StructuredOutput,
)
from .matcher import get_matcher


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
            from ..types import Stats
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
    matcher = get_matcher()

    # Buscar todas las siglas en el texto
    matches = matcher.find_matches(texto, merged_options)

    # Aplicar el formatter apropiado para el formato solicitado
    formatter = FormatterFactory.get_formatter(merged_options.format)
    return formatter.format(texto, matches)


# ============================================================================
# API DE CONSULTA DEL DICCIONARIO
# ============================================================================

def buscar_sigla(sigla: str) -> Optional[AcronymSearchResult]:
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
    matcher = get_matcher()
    return matcher.buscar_sigla(sigla)


def listar_siglas() -> list[str]:
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
    matcher = get_matcher()
    return matcher.listar_siglas()


def obtener_estadisticas() -> DictionaryStats:
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
    matcher = get_matcher()
    return matcher.obtener_estadisticas()
