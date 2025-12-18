"""
Tests para la configuración global de legal-expand

Verifica el sistema de configuración global y opciones.
"""

import pytest

from legal_expand import (
    configurar_globalmente,
    expandir_siglas,
    obtener_configuracion_global,
    resetear_configuracion,
    ExpansionOptions,
    GlobalConfig,
)


class TestConfiguracionGlobal:
    """Tests para la configuración global."""

    def setup_method(self):
        """Reset configuración antes de cada test."""
        resetear_configuracion()

    def test_configuracion_por_defecto(self):
        """Debe tener configuración por defecto correcta."""
        config = obtener_configuracion_global()
        assert config.enabled is True

    def test_desactivar_expansion(self):
        """Debe poder desactivar la expansión."""
        configurar_globalmente(GlobalConfig(enabled=False))
        resultado = expandir_siglas('La AEAT notifica')
        assert 'Agencia Estatal de Administración Tributaria' not in resultado

    def test_activar_expansion(self):
        """Debe poder activar la expansión."""
        configurar_globalmente(GlobalConfig(enabled=False))
        configurar_globalmente(GlobalConfig(enabled=True))
        resultado = expandir_siglas('La AEAT notifica')
        assert 'Agencia Estatal de Administración Tributaria' in resultado

    def test_force_expansion_true(self):
        """force_expansion=True debe expandir aunque esté desactivado."""
        configurar_globalmente(GlobalConfig(enabled=False))
        resultado = expandir_siglas(
            'La AEAT notifica',
            ExpansionOptions(force_expansion=True)
        )
        assert 'Agencia Estatal de Administración Tributaria' in resultado

    def test_force_expansion_false(self):
        """force_expansion=False debe NO expandir aunque esté activado."""
        configurar_globalmente(GlobalConfig(enabled=True))
        resultado = expandir_siglas(
            'La AEAT notifica',
            ExpansionOptions(force_expansion=False)
        )
        assert 'Agencia Estatal de Administración Tributaria' not in resultado

    def test_resetear_configuracion(self):
        """Debe restaurar configuración por defecto."""
        configurar_globalmente(GlobalConfig(enabled=False))
        resetear_configuracion()
        config = obtener_configuracion_global()
        assert config.enabled is True

    def test_opciones_por_defecto_globales(self):
        """Debe aplicar opciones por defecto globales."""
        configurar_globalmente(GlobalConfig(
            enabled=True,
            default_options=ExpansionOptions(expand_only_first=True)
        ))
        texto = 'La AEAT informa. La AEAT notifica.'
        resultado = expandir_siglas(texto)
        count = resultado.count('Agencia Estatal de Administración Tributaria')
        assert count == 1

    def test_override_opciones_globales(self):
        """Las opciones locales deben sobreescribir las globales."""
        configurar_globalmente(GlobalConfig(
            enabled=True,
            default_options=ExpansionOptions(expand_only_first=True)
        ))
        texto = 'La AEAT informa. La AEAT notifica.'
        resultado = expandir_siglas(texto, ExpansionOptions(expand_only_first=False))
        count = resultado.count('Agencia Estatal de Administración Tributaria')
        assert count == 2


class TestFormatoEstructuradoDesactivado:
    """Tests para formato estructurado cuando la expansión está desactivada."""

    def setup_method(self):
        """Reset configuración antes de cada test."""
        resetear_configuracion()

    def test_structured_cuando_desactivado(self):
        """Debe retornar StructuredOutput vacío cuando está desactivado."""
        configurar_globalmente(GlobalConfig(enabled=False))
        resultado = expandir_siglas(
            'La AEAT notifica',
            ExpansionOptions(format='structured')
        )
        assert resultado.original_text == 'La AEAT notifica'
        assert resultado.expanded_text == 'La AEAT notifica'
        assert len(resultado.acronyms) == 0
        assert resultado.stats.total_acronyms_found == 0
