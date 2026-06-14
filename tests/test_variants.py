"""
Tests de paridad con las mejoras de variantes del paquete NPM.
"""

from legal_expand import ExpansionOptions, expandir_siglas, resetear_configuracion


class TestMatchingVariants:
    """Tests para variantes minusculas y con puntos."""

    def setup_method(self):
        resetear_configuracion()

    def test_expande_siglas_minusculas(self):
        resultado = expandir_siglas('La aeat notifica el iva')

        assert 'aeat' in resultado
        assert 'Agencia Estatal de Administración Tributaria' in resultado
        assert 'iva' in resultado
        assert 'Impuesto sobre el Valor Añadido' in resultado

    def test_expande_siglas_con_puntos_generados(self):
        resultado = expandir_siglas('La A.E.A.T. notifica')

        assert 'A.E.A.T.' in resultado
        assert 'Agencia Estatal de Administración Tributaria' in resultado

    def test_preserve_case_false_usa_sigla_canonica(self):
        resultado = expandir_siglas(
            'La aeat notifica',
            ExpansionOptions(preserve_case=False)
        )

        assert 'AEAT (Agencia Estatal de Administración Tributaria)' in resultado
