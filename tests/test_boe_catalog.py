"""Tests del índice de resolución del catálogo BOE (boe_catalog)."""

from legal_expand.boe_catalog import (
    _candidate_rangos,
    _compose_title,
    parse_citation,
    resolve_norm_from_catalog,
)


def test_parse_citation_extrae_rango_y_numero():
    assert parse_citation('Ley Orgánica 3/2018, de 5 de diciembre') == ('Ley Orgánica', '3/2018')
    assert parse_citation('Real Decreto 203/2021') == ('Real Decreto', '203/2021')
    assert parse_citation('Orden HFP/1030/2021') == ('Orden', 'HFP/1030/2021')
    assert parse_citation('un texto sin número de norma') is None


def test_candidate_rangos_abreviaturas():
    assert _candidate_rangos('Ley Orgánica') == ('Ley Orgánica',)
    assert _candidate_rangos('RD') == ('Real Decreto',)
    assert _candidate_rangos('Real Decreto') == ('Real Decreto',)
    # RDL es ambiguo: Real Decreto-ley o Real Decreto Legislativo.
    assert set(_candidate_rangos('RDL')) == {'Real Decreto-ley', 'Real Decreto Legislativo'}


def test_compose_title_desde_fecha():
    assert _compose_title('Ley', '19/2013', '20131209') == 'Ley 19/2013, de 9 de diciembre de 2013'
    assert _compose_title('Ley', '19/2013', '') == 'Ley 19/2013'


def test_resolve_norma_estatal_por_indice():
    norm = resolve_norm_from_catalog('Ley 19/2013')
    assert norm is not None
    assert norm.boe_id == 'BOE-A-2013-12887'
    assert norm.source == 'boe-index'
    assert norm.official_number == '19/2013'
    assert 'www.boe.es/buscar/act.php?id=BOE-A-2013-12887' in norm.url


def test_resolve_real_decreto_ley_por_indice():
    norm = resolve_norm_from_catalog('Real Decreto-ley 8/2020')
    assert norm is not None
    assert norm.boe_id == 'BOE-A-2020-3824'
    assert norm.rank == 'Real Decreto-ley'


def test_resolve_norma_inexistente_devuelve_none():
    assert resolve_norm_from_catalog('Ley 99/2099') is None
    assert resolve_norm_from_catalog('texto sin norma') is None


def test_fecha_ilegible_no_rompe_el_titulo():
    from legal_expand.boe_catalog import _fecha_legible

    assert _fecha_legible('bad') == ''
    assert _fecha_legible('20261399') == ''  # mes inválido
    assert _compose_title('Orden', 'HFP/1030/2021', 'malformada') == 'Orden HFP/1030/2021'
