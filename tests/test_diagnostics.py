"""
Tests para salida de diagnostico de legal-expand.
"""

from legal_expand import (
    ExpansionOptions,
    GlobalConfig,
    configurar_globalmente,
    expandir_siglas_detallado,
    resetear_configuracion,
)
from legal_expand.types import OmittedAcronymReason


class TestExpandirSiglasDetallado:
    """Tests para trazabilidad de siglas omitidas."""

    def setup_method(self):
        resetear_configuracion()

    def test_reporta_siglas_excluidas(self):
        resultado = expandir_siglas_detallado('AEAT y BOE', opciones=None)
        assert len(resultado.omitted_acronyms) == 0

        resultado = expandir_siglas_detallado(
            'AEAT y BOE',
            opciones=ExpansionOptions(exclude=['BOE'])
        )

        assert len(resultado.acronyms) == 1
        assert any(
            item.acronym == 'BOE' and item.reason == 'excluded'
            for item in resultado.omitted_acronyms
        )

    def test_reporta_filtro_include(self):
        resultado = expandir_siglas_detallado(
            'AEAT y BOE',
            ExpansionOptions(include=['AEAT'])
        )

        assert len(resultado.acronyms) == 1
        assert any(
            item.acronym == 'BOE' and item.reason == 'not-in-include'
            for item in resultado.omitted_acronyms
        )

    def test_reporta_expand_only_first(self):
        resultado = expandir_siglas_detallado(
            'AEAT y AEAT',
            ExpansionOptions(expand_only_first=True)
        )

        assert len(resultado.acronyms) == 1
        assert any(
            item.acronym == 'AEAT' and item.reason == 'expand-only-first'
            for item in resultado.omitted_acronyms
        )

    def test_reporta_contextos_protegidos(self):
        texto = 'Visita https://aeat.es y escribe a info@boe.es y usa `AEAT` fuera AEAT'
        resultado = expandir_siglas_detallado(texto)
        reasons = {item.reason for item in resultado.omitted_acronyms}

        assert 'inside-url' in reasons
        assert 'inside-email' in reasons
        assert 'inside-inline-code' in reasons
        assert 'fuera AEAT (Agencia Estatal de Administración Tributaria)' in resultado.expanded_text

    def test_devuelve_diagnostico_vacio_si_esta_desactivado(self):
        configurar_globalmente(GlobalConfig(enabled=False))
        resultado = expandir_siglas_detallado('AEAT y BOE')

        assert len(resultado.acronyms) == 0
        assert len(resultado.omitted_acronyms) == 0
        assert resultado.stats.total_acronyms_found == 0

    def test_expone_razones_estables(self):
        reasons: list[OmittedAcronymReason] = [
            'excluded',
            'not-in-include',
            'expand-only-first',
            'ambiguous-unresolved',
            'inside-url',
            'inside-email',
            'inside-code-block',
            'inside-inline-code',
            'not-found',
        ]

        assert len(reasons) == 9
