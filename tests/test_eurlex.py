"""Tests de la resolución de normativa UE a EUR-Lex (eurlex)."""

from legal_expand.eurlex import (
    build_celex,
    extract_article_text,
    resolve_eu_norm,
    unit_number,
)


def test_unit_number():
    assert unit_number('art. 6') == '6'
    assert unit_number('artículo 14') == '14'
    assert unit_number(None) is None
    assert unit_number('sin número') is None


def test_extract_article_formato_moderno():
    html = (
        '<div id="art_6"><p class="oj-ti-art">Artículo 6</p>'
        '<p class="oj-normal">Licitud. 1. Texto del seis.</p></div>'
        '<div id="art_7"><p class="oj-ti-art">Artículo 7</p></div>'
    )
    texto = extract_article_text(html, '6')
    assert 'Licitud' in texto and 'Texto del seis' in texto
    assert 'Artículo 7' not in texto


def test_extract_article_formato_antiguo():
    html = (
        '<p>Artículo 5</p><p>Información general. 1. Texto del cinco.</p>'
        '<p>Artículo 6</p><p>Otro contenido.</p>'
    )
    texto = extract_article_text(html, '5')
    assert 'Información general' in texto and 'Texto del cinco' in texto
    assert 'Otro contenido' not in texto


def test_extract_article_inexistente():
    assert extract_article_text('<p>nada</p>', '9') == ''


def test_build_celex_con_relleno():
    assert build_celex('R', '2016', '679') == '32016R0679'
    assert build_celex('L', '2000', '31') == '32000L0031'
    assert build_celex('R', '2001', '1049') == '32001R1049'


def test_resolve_alias_rgpd():
    norm = resolve_eu_norm('RGPD')
    assert norm is not None
    assert norm.boe_id == '32016R0679'
    assert norm.source == 'eur-lex'
    assert 'CELEX:32016R0679' in norm.url


def test_resolve_reglamento_ue_moderno():
    norm = resolve_eu_norm('Reglamento (UE) 2016/679')
    assert norm is not None
    assert norm.boe_id == '32016R0679'


def test_resolve_reglamento_ce_invertido():
    # Formato antiguo número/año: el año (2001) es el segundo grupo.
    norm = resolve_eu_norm('Reglamento (CE) 1049/2001')
    assert norm is not None
    assert norm.boe_id == '32001R1049'


def test_resolve_directiva_y_decision():
    assert resolve_eu_norm('Directiva 2000/31/CE').boe_id == '32000L0031'
    assert resolve_eu_norm('Directiva (UE) 2016/943').boe_id == '32016L0943'
    assert resolve_eu_norm('Decisión (UE) 2015/1814').boe_id == '32015D1814'


def test_resolve_no_ue_devuelve_none():
    assert resolve_eu_norm('Ley 39/2015') is None
    assert resolve_eu_norm('un texto cualquiera') is None
    # Reglamento sin número reconocible.
    assert resolve_eu_norm('Reglamento interno') is None
