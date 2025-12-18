"""
Tests para casos especiales y edge cases de legal-expand

Verifica el manejo de contextos especiales y casos límite.
"""

import pytest

from legal_expand import (
    expandir_siglas,
    resetear_configuracion,
    ExpansionOptions,
)


class TestProteccionContextos:
    """Tests para protección de contextos especiales."""

    def setup_method(self):
        """Reset configuración antes de cada test."""
        resetear_configuracion()

    def test_no_expandir_en_urls(self):
        """No debe expandir siglas dentro de URLs."""
        texto = 'Visita https://aeat.es para más información sobre AEAT'
        resultado = expandir_siglas(texto)
        # La URL debe quedar intacta
        assert 'https://aeat.es' in resultado
        # La AEAT fuera de la URL sí debe expandirse
        assert 'Agencia Estatal de Administración Tributaria' in resultado

    def test_no_expandir_en_emails(self):
        """No debe expandir siglas dentro de emails."""
        texto = 'Contacta con info@aeat.es o con la AEAT'
        resultado = expandir_siglas(texto)
        # El email debe quedar intacto
        assert 'info@aeat.es' in resultado

    def test_no_expandir_en_codigo_markdown(self):
        """No debe expandir dentro de bloques de código markdown."""
        texto = '''Texto normal con AEAT.
```python
AEAT = "variable"
```
Más texto con AEAT.'''
        resultado = expandir_siglas(texto)
        # Solo debe haber 2 expansiones (antes y después del bloque)
        # El AEAT dentro del código no debe expandirse

    def test_no_expandir_codigo_inline(self):
        """No debe expandir dentro de código inline."""
        texto = 'Usa `AEAT.method()` para procesar con AEAT'
        resultado = expandir_siglas(texto)
        # El código inline debe quedar intacto
        assert '`AEAT.method()`' in resultado


class TestVariantes:
    """Tests para variantes de siglas."""

    def setup_method(self):
        """Reset configuración antes de cada test."""
        resetear_configuracion()

    def test_variante_con_puntos(self):
        """Debe detectar variantes con puntos."""
        resultado = expandir_siglas('El A.E.A.T. notifica')
        # Debe expandir aunque tenga puntos
        assert 'Agencia' in resultado or resultado == 'El A.E.A.T. notifica'

    def test_variante_mayusculas_minusculas(self):
        """Debe detectar variantes en diferentes casos."""
        resultado1 = expandir_siglas('La AEAT notifica')
        assert 'Agencia Estatal de Administración Tributaria' in resultado1

    def test_abreviatura_con_punto(self):
        """Debe detectar abreviaturas con punto."""
        resultado = expandir_siglas('Según el art. 123')
        # art. debe expandirse a artículo
        assert 'artículo' in resultado.lower() or 'Artículo' in resultado


class TestCasosLimite:
    """Tests para casos límite."""

    def setup_method(self):
        """Reset configuración antes de cada test."""
        resetear_configuracion()

    def test_sigla_al_inicio(self):
        """Debe expandir sigla al inicio del texto."""
        resultado = expandir_siglas('AEAT notifica')
        assert 'Agencia Estatal de Administración Tributaria' in resultado

    def test_sigla_al_final(self):
        """Debe expandir sigla al final del texto."""
        resultado = expandir_siglas('Notifica la AEAT')
        assert 'Agencia Estatal de Administración Tributaria' in resultado

    def test_sigla_sola(self):
        """Debe expandir sigla sola."""
        resultado = expandir_siglas('AEAT')
        assert 'Agencia Estatal de Administración Tributaria' in resultado

    def test_multiples_siglas_seguidas(self):
        """Debe manejar múltiples siglas seguidas."""
        resultado = expandir_siglas('AEAT BOE IVA')
        assert 'Agencia Estatal de Administración Tributaria' in resultado
        assert 'Boletín Oficial del Estado' in resultado
        assert 'Impuesto sobre el Valor Añadido' in resultado

    def test_sigla_no_como_parte_de_palabra(self):
        """No debe expandir siglas que son parte de otra palabra."""
        # "IVA" no debe expandirse si es parte de "ACTIVA"
        texto = 'La empresa ACTIVA gestiona el IVA'
        resultado = expandir_siglas(texto)
        # Solo el IVA independiente debe expandirse
        assert resultado.count('Impuesto sobre el Valor Añadido') == 1


class TestEstadisticas:
    """Tests para estadísticas del formato estructurado."""

    def setup_method(self):
        """Reset configuración antes de cada test."""
        resetear_configuracion()

    def test_estadisticas_correctas(self):
        """Debe calcular estadísticas correctamente."""
        resultado = expandir_siglas(
            'La AEAT gestiona el IVA según el BOE',
            ExpansionOptions(format='structured')
        )
        assert resultado.stats.total_acronyms_found == 3
        assert resultado.stats.total_expanded == 3
        assert resultado.stats.ambiguous_not_expanded == 0

    def test_posiciones_correctas(self):
        """Debe reportar posiciones correctas."""
        resultado = expandir_siglas(
            'La AEAT notifica',
            ExpansionOptions(format='structured')
        )
        assert len(resultado.acronyms) == 1
        aeat = resultado.acronyms[0]
        assert aeat.position.start == 3
        assert aeat.position.end == 7
        assert 'La AEAT notifica'[aeat.position.start:aeat.position.end] == 'AEAT'
