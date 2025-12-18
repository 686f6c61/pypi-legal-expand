"""
legal-expand - Formatter de texto plano

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Formatea las siglas expandidas insertando el significado entre
paréntesis después de cada sigla. Es el formato por defecto.

ARQUITECTURA:
Implementa el patrón Strategy como formatter concreto:
1. Hereda de Formatter (ABC)
2. Implementa format() con lógica específica de texto plano
3. Procesa matches en orden DESCENDENTE por posición

RESPONSABILIDADES:
- Insertar expansiones entre paréntesis
- Mantener el texto original legible
- Preservar posiciones mediante procesamiento reverso

ALGORITMO:
1. Ordena matches por posición DESCENDENTE
2. Procesa desde el final hacia el inicio del texto
3. Inserta " (expansión)" después de cada sigla

NOTA CRÍTICA:
El ordenamiento descendente es ESENCIAL para evitar invalidar
los índices de posición al insertar texto.

FORMATO DE SALIDA:
"La AEAT (Agencia Estatal de Administración Tributaria) notifica..."
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Formatter

if TYPE_CHECKING:
    from ..types import MatchInfo


class PlainTextFormatter(Formatter):
    """
    Formatter de texto plano.

    Inserta el significado entre paréntesis justo después de cada sigla.
    Es el formato por defecto y más legible para documentos de texto.

    Output format:
        "SIGLA (significado completo)"

    Example:
        >>> formatter = PlainTextFormatter()
        >>> matches = [MatchInfo(original='AEAT', expansion='Agencia...', start_pos=3, end_pos=7, ...)]
        >>> formatter.format("La AEAT notifica", matches)
        'La AEAT (Agencia...) notifica'

    Algorithm:
        1. Ordena matches en orden DESCENDENTE por posición
        2. Procesa desde el final hacia el inicio del texto
        3. Inserta " (expansión)" después de cada sigla

    Note:
        El ordenamiento descendente es CRÍTICO para evitar invalidar
        los índices de posición al insertar texto.
    """

    def format(self, original_text: str, matches: list['MatchInfo']) -> str:
        """
        Formatea el texto insertando expansiones entre paréntesis.

        Args:
            original_text: Texto original sin modificar
            matches: Lista de matches encontrados

        Returns:
            Texto con las siglas expandidas en formato plano
        """
        if not matches:
            return original_text

        # PASO 1: Ordenar matches en orden DESCENDENTE por posición
        # Esto es CRÍTICO para evitar invalidar índices al insertar texto
        sorted_matches = sorted(matches, key=lambda m: m.start_pos, reverse=True)

        result = original_text

        # PASO 2: Procesar desde el final hacia el inicio
        for match in sorted_matches:
            # PASO 3: Insertar " (significado)" justo después de la sigla
            before = result[:match.end_pos]
            after = result[match.end_pos:]
            result = f"{before} ({match.expansion}){after}"

        return result
