"""
legal-expand - Formatter HTML

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Formatea las siglas expandidas generando HTML semántico con
etiquetas <abbr> para accesibilidad y SEO.

ARQUITECTURA:
Implementa el patrón Strategy como formatter concreto:
1. Hereda de Formatter (ABC)
2. Implementa format() con lógica específica de HTML
3. Incluye método estático escape_html() para seguridad

RESPONSABILIDADES:
- Generar HTML semántico con <abbr>
- Prevenir vulnerabilidades XSS
- Proporcionar tooltips nativos del navegador
- Mejorar accesibilidad para screen readers

SEGURIDAD:
El método escape_html() escapa todos los caracteres peligrosos:
- & → &amp;
- < → &lt;
- > → &gt;
- " → &quot;
- ' → &#039;

FORMATO DE SALIDA:
'<abbr title="Agencia Estatal...">AEAT</abbr> (Agencia Estatal...)'

BENEFICIOS:
- Tooltips nativos en hover
- Mejor indexación SEO
- Accesibilidad WCAG
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Formatter

if TYPE_CHECKING:
    from ..types import MatchInfo


class HtmlFormatter(Formatter):
    """
    Formatter HTML semántico.

    Genera HTML con etiquetas <abbr> que proporcionan tooltips nativos
    en navegadores y mejoran la accesibilidad para screen readers.

    Output format:
        '<abbr title="significado">SIGLA</abbr> (significado)'

    Example:
        >>> formatter = HtmlFormatter()
        >>> matches = [MatchInfo(original='AEAT', expansion='Agencia...', ...)]
        >>> formatter.format("La AEAT", matches)
        'La <abbr title="Agencia...">AEAT</abbr> (Agencia...)'

    Security:
        El método escape_html() previene vulnerabilidades XSS escapando
        todos los caracteres HTML especiales.

    Algorithm:
        1. Ordena matches en orden DESCENDENTE
        2. Para cada match, genera <abbr> + expansión inline
        3. Reemplaza desde el final hacia el inicio
    """

    @staticmethod
    def escape_html(text: str) -> str:
        """
        Escapa entidades HTML para prevenir XSS.

        Args:
            text: Texto a escapar

        Returns:
            Texto con caracteres HTML escapados

        Example:
            >>> HtmlFormatter.escape_html('<script>alert("xss")</script>')
            '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
        """
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#039;'))

    def format(self, original_text: str, matches: list['MatchInfo']) -> str:
        """
        Formatea el texto con HTML semántico.

        Args:
            original_text: Texto original sin modificar
            matches: Lista de matches encontrados

        Returns:
            Texto con siglas expandidas en formato HTML
        """
        if not matches:
            return original_text

        # PASO 1: Ordenar matches en orden DESCENDENTE
        sorted_matches = sorted(matches, key=lambda m: m.start_pos, reverse=True)

        result = original_text

        # PASO 2: Procesar desde el final hacia el inicio
        for match in sorted_matches:
            # PASO 3: Extraer texto original de la sigla
            acronym_text = original_text[match.start_pos:match.end_pos]

            # PASO 4: Generar reemplazo con <abbr> + expansión inline
            escaped_expansion = self.escape_html(match.expansion)
            escaped_acronym = self.escape_html(acronym_text)

            replacement = (
                f'<abbr title="{escaped_expansion}">'
                f'{escaped_acronym}</abbr> ({escaped_expansion})'
            )

            # PASO 5: Reemplazar en el resultado
            result = result[:match.start_pos] + replacement + result[match.end_pos:]

        return result
