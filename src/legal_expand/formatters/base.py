"""
legal-expand - Interfaz base para formatters

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Define la interfaz abstracta (ABC) que deben implementar todos los
formatters. Garantiza un contrato común para la transformación de
matches a diferentes formatos de salida.

ARQUITECTURA:
Utiliza ABC (Abstract Base Class) de Python para definir:
1. Método abstracto format() que todas las implementaciones deben definir
2. Tipo de retorno Union[str, StructuredOutput] para flexibilidad

RESPONSABILIDADES:
- Definir contrato de interfaz para formatters
- Documentar parámetros y tipos esperados
- Facilitar implementación de formatters personalizados

IMPLEMENTACIONES:
- PlainTextFormatter: Texto con paréntesis
- HtmlFormatter: Etiquetas <abbr> semánticas
- StructuredFormatter: Objeto con metadata
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ..types import MatchInfo, StructuredOutput


class Formatter(ABC):
    """
    Interfaz base abstracta para formatters.

    Todos los formatters deben heredar de esta clase e implementar
    el método format() para transformar matches en el formato deseado.

    Example:
        >>> class CustomFormatter(Formatter):
        ...     def format(self, original_text, matches):
        ...         # Implementación personalizada
        ...         return original_text
    """

    @abstractmethod
    def format(
        self,
        original_text: str,
        matches: list['MatchInfo']
    ) -> Union[str, 'StructuredOutput']:
        """
        Transforma el texto original con los matches encontrados.

        Args:
            original_text: Texto original sin modificar
            matches: Lista de matches encontrados por el matcher

        Returns:
            Texto formateado (string) o StructuredOutput dependiendo
            del tipo de formatter
        """
        pass
