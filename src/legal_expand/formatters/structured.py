"""
legal-expand - Formatter estructurado (JSON)

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Genera un objeto estructurado con metadata completa del procesamiento,
incluyendo texto expandido, información de siglas y estadísticas.

ARQUITECTURA:
Implementa el patrón Strategy como formatter concreto:
1. Hereda de Formatter (ABC)
2. Reutiliza PlainTextFormatter para generar texto expandido
3. Retorna StructuredOutput en lugar de string

RESPONSABILIDADES:
- Generar metadata completa del procesamiento
- Calcular estadísticas de expansión
- Proporcionar información detallada de cada sigla
- Permitir acceso programático a los datos

ESTRUCTURA DE SALIDA:
StructuredOutput(
    original_text="...",      # Texto sin modificar
    expanded_text="...",      # Texto con expansiones
    acronyms=[...],           # Lista de ExpandedAcronym
    stats=Stats(...)          # Estadísticas de procesamiento
)

ESTADÍSTICAS INCLUIDAS:
- total_acronyms_found: Siglas detectadas
- total_expanded: Siglas efectivamente expandidas
- ambiguous_not_expanded: Siglas ambiguas no expandidas

USO TÍPICO:
- APIs que necesitan metadata
- Análisis de documentos
- Interfaces de usuario ricas
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Formatter
from .plain_text import PlainTextFormatter

if TYPE_CHECKING:
    from ..types import MatchInfo, MatchRunStats

from ..types import ExpandedAcronym, Position, Stats, StructuredOutput


class StructuredFormatter(Formatter):
    """
    Formatter que produce objeto estructurado con metadata.

    Genera un StructuredOutput con:
    - Texto original y expandido
    - Lista detallada de todas las siglas procesadas
    - Estadísticas del procesamiento

    Output format:
        StructuredOutput(
            original_text="...",
            expanded_text="...",
            acronyms=[ExpandedAcronym(...)],
            stats=Stats(...)
        )

    Example:
        >>> formatter = StructuredFormatter()
        >>> result = formatter.format("La AEAT informa", matches)
        >>> result.stats.total_expanded
        1
        >>> result.acronyms[0].acronym
        'AEAT'

    Note:
        Reutiliza PlainTextFormatter para generar el texto expandido,
        evitando duplicación de código.
    """

    def format_with_stats(
        self,
        original_text: str,
        matches: list['MatchInfo'],
        stats: 'MatchRunStats'
    ) -> StructuredOutput:
        """
        Formatea usando estadísticas explícitas del matcher.

        Args:
            original_text: Texto original sin modificar
            matches: Lista de matches expandidos
            stats: Estadísticas calculadas durante el matching

        Returns:
            StructuredOutput con estadísticas coherentes
        """
        return self._build_output(original_text, matches, stats)

    def format(self, original_text: str, matches: list['MatchInfo']) -> StructuredOutput:
        """
        Formatea el texto y genera metadata estructurada.

        Args:
            original_text: Texto original sin modificar
            matches: Lista de matches encontrados

        Returns:
            StructuredOutput con metadata completa
        """
        return self._build_output(original_text, matches)

    def _build_output(
        self,
        original_text: str,
        matches: list['MatchInfo'],
        stats: 'MatchRunStats | None' = None
    ) -> StructuredOutput:
        """Construye el StructuredOutput compartido por ambas rutas."""
        # PASO 1: Generar texto expandido reutilizando PlainTextFormatter
        plain_formatter = PlainTextFormatter()
        expanded_text = plain_formatter.format(original_text, matches)

        # PASO 2: Transformar matches internos a formato público ExpandedAcronym
        acronyms = [
            ExpandedAcronym(
                acronym=match.original,
                expansion=match.expansion,
                position=Position(start=match.start_pos, end=match.end_pos),
                has_multiple_meanings=match.has_multiple_meanings,
                all_meanings=match.all_meanings,
                source=match.source
            )
            for match in matches
        ]

        # PASO 3: Calcular estadísticas de procesamiento
        total_acronyms_found = (
            stats.total_acronyms_found
            if stats is not None
            else len(matches)
        )
        # Las siglas ambiguas se filtran antes de llegar aquí, por lo que la
        # lista de matches ya contiene solo expansiones efectivas.
        total_expanded = len(matches)
        ambiguous_not_expanded = (
            stats.ambiguous_not_expanded
            if stats is not None
            else total_acronyms_found - total_expanded
        )

        # PASO 4: Retornar objeto estructurado
        return StructuredOutput(
            original_text=original_text,
            expanded_text=expanded_text,
            acronyms=acronyms,
            stats=Stats(
                total_acronyms_found=total_acronyms_found,
                total_expanded=total_expanded,
                ambiguous_not_expanded=ambiguous_not_expanded
            )
        )
