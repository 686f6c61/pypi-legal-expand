"""
Tests básicos para legal-expand

Verifica la funcionalidad principal de expansión de siglas.
"""

import pytest

from legal_expand import (
    buscar_sigla,
    expandir_siglas,
    listar_siglas,
    obtener_estadisticas,
    resetear_configuracion,
    ExpansionOptions,
)


class TestExpandirSiglas:
    """Tests para la función expandir_siglas."""

    def setup_method(self):
        """Reset configuración antes de cada test."""
        resetear_configuracion()

    def test_expansion_simple(self):
        """Debe expandir una sigla simple."""
        resultado = expandir_siglas('La AEAT notifica')
        assert 'Agencia Estatal de Administración Tributaria' in resultado
        assert 'AEAT' in resultado

    def test_expansion_multiple(self):
        """Debe expandir múltiples siglas."""
        resultado = expandir_siglas('La AEAT gestiona el IVA')
        assert 'Agencia Estatal de Administración Tributaria' in resultado
        assert 'Impuesto sobre el Valor Añadido' in resultado

    def test_texto_sin_siglas(self):
        """Debe retornar texto sin cambios si no hay siglas."""
        texto = 'Este texto no tiene siglas legales'
        resultado = expandir_siglas(texto)
        assert resultado == texto

    def test_texto_vacio(self):
        """Debe manejar texto vacío."""
        resultado = expandir_siglas('')
        assert resultado == ''

    def test_variantes_con_puntos(self):
        """Debe detectar variantes con puntos."""
        resultado = expandir_siglas('Según el art. 5')
        assert 'artículo' in resultado.lower() or 'Artículo' in resultado

    def test_expand_only_first(self):
        """Debe expandir solo la primera ocurrencia."""
        texto = 'La AEAT informa. La AEAT notifica.'
        resultado = expandir_siglas(texto, ExpansionOptions(expand_only_first=True))
        # Solo la primera AEAT debe expandirse
        count = resultado.count('Agencia Estatal de Administración Tributaria')
        assert count == 1

    def test_exclude_siglas(self):
        """Debe excluir siglas especificadas."""
        texto = 'La AEAT gestiona el IVA'
        resultado = expandir_siglas(texto, ExpansionOptions(exclude=['IVA']))
        assert 'Agencia Estatal de Administración Tributaria' in resultado
        assert 'Impuesto sobre el Valor Añadido' not in resultado

    def test_include_siglas(self):
        """Debe incluir solo siglas especificadas."""
        texto = 'La AEAT gestiona el IVA según el BOE'
        resultado = expandir_siglas(texto, ExpansionOptions(include=['AEAT']))
        assert 'Agencia Estatal de Administración Tributaria' in resultado
        assert 'Impuesto sobre el Valor Añadido' not in resultado
        assert 'Boletín Oficial del Estado' not in resultado


class TestFormatos:
    """Tests para diferentes formatos de salida."""

    def setup_method(self):
        """Reset configuración antes de cada test."""
        resetear_configuracion()

    def test_formato_plain(self):
        """Debe generar formato texto plano."""
        resultado = expandir_siglas('La AEAT', ExpansionOptions(format='plain'))
        assert isinstance(resultado, str)
        assert '(' in resultado
        assert ')' in resultado

    def test_formato_html(self):
        """Debe generar formato HTML con abbr."""
        resultado = expandir_siglas('La AEAT', ExpansionOptions(format='html'))
        assert isinstance(resultado, str)
        assert '<abbr' in resultado
        assert 'title=' in resultado
        assert '</abbr>' in resultado

    def test_formato_structured(self):
        """Debe generar formato estructurado."""
        resultado = expandir_siglas('La AEAT', ExpansionOptions(format='structured'))
        assert hasattr(resultado, 'original_text')
        assert hasattr(resultado, 'expanded_text')
        assert hasattr(resultado, 'acronyms')
        assert hasattr(resultado, 'stats')
        assert resultado.original_text == 'La AEAT'
        assert len(resultado.acronyms) == 1
        assert resultado.acronyms[0].acronym == 'AEAT'


class TestBuscarSigla:
    """Tests para la función buscar_sigla."""

    def test_sigla_existente(self):
        """Debe encontrar sigla existente."""
        resultado = buscar_sigla('AEAT')
        assert resultado is not None
        assert resultado.acronym == 'AEAT'
        assert len(resultado.meanings) > 0
        assert 'Agencia Estatal de Administración Tributaria' in resultado.meanings

    def test_sigla_no_existente(self):
        """Debe retornar None para sigla no existente."""
        resultado = buscar_sigla('XYZABC123')
        assert resultado is None


class TestListarSiglas:
    """Tests para la función listar_siglas."""

    def test_lista_no_vacia(self):
        """Debe retornar lista no vacía."""
        siglas = listar_siglas()
        assert len(siglas) > 0

    def test_contiene_siglas_conocidas(self):
        """Debe contener siglas conocidas."""
        siglas = listar_siglas()
        assert 'AEAT' in siglas
        assert 'IVA' in siglas
        assert 'BOE' in siglas


class TestObtenerEstadisticas:
    """Tests para la función obtener_estadisticas."""

    def test_estadisticas_validas(self):
        """Debe retornar estadísticas válidas."""
        stats = obtener_estadisticas()
        assert stats.total_acronyms > 0
        assert stats.acronyms_with_duplicates >= 0
        assert stats.acronyms_with_punctuation >= 0

    def test_total_aproximado(self):
        """Debe tener aproximadamente 646 siglas."""
        stats = obtener_estadisticas()
        # Permitir variación por actualizaciones del diccionario
        assert 600 <= stats.total_acronyms <= 700
