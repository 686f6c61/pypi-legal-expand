"""
legal-expand - Factory de formatters

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Proporciona el FormatterFactory para gestión centralizada de formatters
y permite registrar formatters personalizados para formatos adicionales.

ARQUITECTURA:
El sistema de formatters sigue el patrón Factory + Strategy:
1. Formatter (ABC): Define la interfaz común
2. Implementaciones concretas: Plain, HTML, Structured
3. FormatterFactory: Gestiona registro y acceso

RESPONSABILIDADES:
- Proporcionar acceso a formatters built-in
- Permitir registro de formatters personalizados
- Mantener instancias únicas de cada formatter
- Validar nombres de formatos solicitados

FORMATTERS DISPONIBLES:
- plain: Texto con expansión entre paréntesis
- html: Etiquetas <abbr> con tooltips
- structured: Objeto JSON con metadata completa

EXTENSIBILIDAD:
Los usuarios pueden registrar formatters personalizados:
>>> class CustomFormatter(Formatter):
...     def format(self, text, matches): ...
>>> FormatterFactory.register_formatter('custom', CustomFormatter())
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from .base import Formatter
from .html import HtmlFormatter
from .plain_text import PlainTextFormatter
from .structured import StructuredFormatter

if TYPE_CHECKING:
    from ..types import MatchInfo, StructuredOutput

__all__ = [
    'Formatter',
    'FormatterFactory',
    'PlainTextFormatter',
    'HtmlFormatter',
    'StructuredFormatter',
]


class FormatterFactory:
    """
    Factory centralizada para gestión de formatters.

    Proporciona acceso a los formatters built-in y permite registrar
    formatters personalizados para formatos de salida adicionales.

    Built-in formatters:
        - 'plain': PlainTextFormatter (texto con paréntesis)
        - 'html': HtmlFormatter (etiquetas <abbr>)
        - 'structured': StructuredFormatter (objeto JSON)

    Example:
        >>> # Usar formatter built-in
        >>> formatter = FormatterFactory.get_formatter('html')
        >>> result = formatter.format(text, matches)

        >>> # Registrar formatter personalizado
        >>> class MarkdownFormatter(Formatter):
        ...     def format(self, text, matches):
        ...         # Implementación
        ...         pass
        >>> FormatterFactory.register_formatter('markdown', MarkdownFormatter())
    """

    _formatters: dict[str, Formatter] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Inicializa los formatters built-in si no están inicializados."""
        if not cls._initialized:
            cls._formatters = {
                'plain': PlainTextFormatter(),
                'html': HtmlFormatter(),
                'structured': StructuredFormatter(),
            }
            cls._initialized = True

    @classmethod
    def get_formatter(cls, format_name: str) -> Formatter:
        """
        Obtiene un formatter por nombre.

        Args:
            format_name: Nombre del formato ('plain', 'html', 'structured' o personalizado)

        Returns:
            Instancia del formatter solicitado

        Raises:
            ValueError: Si el formato no existe

        Example:
            >>> formatter = FormatterFactory.get_formatter('html')
            >>> isinstance(formatter, HtmlFormatter)
            True
        """
        cls._ensure_initialized()

        if format_name not in cls._formatters:
            available = ', '.join(cls._formatters.keys())
            raise ValueError(
                f"Unknown format: '{format_name}'. "
                f"Available formats: {available}"
            )

        return cls._formatters[format_name]

    @classmethod
    def register_formatter(cls, name: str, formatter: Formatter) -> None:
        """
        Registra un formatter personalizado.

        Args:
            name: Nombre único para el formatter
            formatter: Instancia del formatter a registrar

        Example:
            >>> class CustomFormatter(Formatter):
            ...     def format(self, text, matches):
            ...         return text.upper()
            >>> FormatterFactory.register_formatter('custom', CustomFormatter())
        """
        cls._ensure_initialized()
        cls._formatters[name] = formatter

    @classmethod
    def list_formatters(cls) -> list[str]:
        """
        Lista todos los formatters disponibles.

        Returns:
            Lista de nombres de formatters registrados

        Example:
            >>> FormatterFactory.list_formatters()
            ['plain', 'html', 'structured']
        """
        cls._ensure_initialized()
        return list(cls._formatters.keys())

    @classmethod
    def reset(cls) -> None:
        """
        Resetea los formatters a los valores por defecto.

        Útil para testing. Elimina formatters personalizados y
        reinicializa los built-in.
        """
        cls._initialized = False
        cls._formatters = {}
