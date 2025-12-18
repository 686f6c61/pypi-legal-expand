"""
Tests para los formatters de legal-expand

Verifica el funcionamiento de cada formatter.
"""

import pytest

from legal_expand import (
    FormatterFactory,
    Formatter,
    resetear_configuracion,
)
from legal_expand.types import MatchInfo


class TestFormatterFactory:
    """Tests para el FormatterFactory."""

    def setup_method(self):
        """Reset formatters antes de cada test."""
        FormatterFactory.reset()

    def test_get_formatter_plain(self):
        """Debe obtener formatter plain."""
        formatter = FormatterFactory.get_formatter('plain')
        assert formatter is not None

    def test_get_formatter_html(self):
        """Debe obtener formatter html."""
        formatter = FormatterFactory.get_formatter('html')
        assert formatter is not None

    def test_get_formatter_structured(self):
        """Debe obtener formatter structured."""
        formatter = FormatterFactory.get_formatter('structured')
        assert formatter is not None

    def test_get_formatter_invalido(self):
        """Debe lanzar error para formatter inválido."""
        with pytest.raises(ValueError) as exc_info:
            FormatterFactory.get_formatter('invalido')
        assert 'Unknown format' in str(exc_info.value)

    def test_list_formatters(self):
        """Debe listar formatters disponibles."""
        formatters = FormatterFactory.list_formatters()
        assert 'plain' in formatters
        assert 'html' in formatters
        assert 'structured' in formatters

    def test_register_custom_formatter(self):
        """Debe poder registrar formatter personalizado."""
        class CustomFormatter(Formatter):
            def format(self, original_text, matches):
                return original_text.upper()

        FormatterFactory.register_formatter('custom', CustomFormatter())
        formatter = FormatterFactory.get_formatter('custom')
        assert formatter is not None
        result = formatter.format('test', [])
        assert result == 'TEST'


class TestPlainTextFormatter:
    """Tests para PlainTextFormatter."""

    def setup_method(self):
        """Reset formatters."""
        FormatterFactory.reset()

    def test_formato_basico(self):
        """Debe formatear con paréntesis."""
        formatter = FormatterFactory.get_formatter('plain')
        matches = [
            MatchInfo(
                original='AEAT',
                expansion='Agencia Estatal de Administración Tributaria',
                start_pos=3,
                end_pos=7,
                confidence=1.0,
                has_multiple_meanings=False
            )
        ]
        result = formatter.format('La AEAT notifica', matches)
        assert 'AEAT (Agencia Estatal de Administración Tributaria)' in result

    def test_sin_matches(self):
        """Debe retornar texto original si no hay matches."""
        formatter = FormatterFactory.get_formatter('plain')
        result = formatter.format('Texto sin siglas', [])
        assert result == 'Texto sin siglas'


class TestHtmlFormatter:
    """Tests para HtmlFormatter."""

    def setup_method(self):
        """Reset formatters."""
        FormatterFactory.reset()

    def test_genera_abbr_tag(self):
        """Debe generar tag abbr."""
        formatter = FormatterFactory.get_formatter('html')
        matches = [
            MatchInfo(
                original='AEAT',
                expansion='Agencia Estatal',
                start_pos=3,
                end_pos=7,
                confidence=1.0,
                has_multiple_meanings=False
            )
        ]
        result = formatter.format('La AEAT notifica', matches)
        assert '<abbr title="Agencia Estatal">' in result
        assert '</abbr>' in result

    def test_escapa_html(self):
        """Debe escapar caracteres HTML."""
        formatter = FormatterFactory.get_formatter('html')
        matches = [
            MatchInfo(
                original='TEST',
                expansion='<script>alert("xss")</script>',
                start_pos=0,
                end_pos=4,
                confidence=1.0,
                has_multiple_meanings=False
            )
        ]
        result = formatter.format('TEST', matches)
        assert '<script>' not in result
        assert '&lt;script&gt;' in result


class TestStructuredFormatter:
    """Tests para StructuredFormatter."""

    def setup_method(self):
        """Reset formatters."""
        FormatterFactory.reset()

    def test_retorna_objeto_estructurado(self):
        """Debe retornar StructuredOutput."""
        formatter = FormatterFactory.get_formatter('structured')
        matches = [
            MatchInfo(
                original='AEAT',
                expansion='Agencia Estatal',
                start_pos=3,
                end_pos=7,
                confidence=1.0,
                has_multiple_meanings=False
            )
        ]
        result = formatter.format('La AEAT notifica', matches)

        assert hasattr(result, 'original_text')
        assert hasattr(result, 'expanded_text')
        assert hasattr(result, 'acronyms')
        assert hasattr(result, 'stats')

    def test_estadisticas_correctas(self):
        """Debe calcular estadísticas correctamente."""
        formatter = FormatterFactory.get_formatter('structured')
        matches = [
            MatchInfo(
                original='AEAT',
                expansion='Agencia',
                start_pos=0,
                end_pos=4,
                confidence=1.0,
                has_multiple_meanings=False
            ),
            MatchInfo(
                original='IVA',
                expansion='Impuesto',
                start_pos=5,
                end_pos=8,
                confidence=1.0,
                has_multiple_meanings=False
            )
        ]
        result = formatter.format('AEAT IVA', matches)

        assert result.stats.total_acronyms_found == 2
        assert result.stats.total_expanded == 2
        assert result.stats.ambiguous_not_expanded == 0
