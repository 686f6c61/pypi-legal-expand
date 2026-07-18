"""
Tests del enriquecimiento BOE introducido en 1.4.0.
"""

import json

import pytest

from legal_expand import (
    BOENorm,
    BOEOptions,
    BOEUnitBlock,
    boe_overrides_template,
    boe_report_by_paragraph_markdown,
    boe_report_to_html,
    boe_report_to_markdown,
    detectar_referencias_boe,
    enriquecer_boe,
    explicar_referencia_boe,
    revisar_boe,
)
from legal_expand.cli import main as cli_main
from legal_expand.boe import (
    BOEClient,
    _is_safe_http_url,
    _parse_norms,
    _plain_text,
    _unit_targets,
)


class FakeBOEClient:
    def resolve_norm(self, norm_text):
        if norm_text == 'Decreto 8/2021':
            return None, [
                BOENorm(
                    boe_id='BOE-A-2021-111',
                    title='Decreto 8/2021 candidato A',
                    url='https://www.boe.es/buscar/act.php?id=BOE-A-2021-111',
                    source='fixture',
                ),
                BOENorm(
                    boe_id='BOE-A-2021-222',
                    title='Decreto 8/2021 candidato B',
                    url='https://www.boe.es/buscar/act.php?id=BOE-A-2021-222',
                    source='fixture',
                ),
            ]
        return None, []

    def find_unit_blocks(self, boe_id, unit_text):
        if boe_id == 'BOE-A-2015-10565' and unit_text == 'art. 14.2':
            return [
                BOEUnitBlock(
                    unit='artículo 14',
                    block_id='a14',
                    title='Artículo 14. Derecho y obligación de relacionarse electrónicamente',
                    url='https://www.boe.es/buscar/act.php?id=BOE-A-2015-10565#a14',
                    text='Artículo 14. Derecho y obligación de relacionarse electrónicamente.',
                    source='fixture',
                )
            ]
        return []


BOE_DEEP_CASES = [
    (
        'sentencia_lec',
        'La parte actora invoca el art. 217 LEC.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2000-323', 'unit_text': 'art. 217'}],
    ),
    (
        'constitucion',
        'Se vulnera el articulo 24 de la Constitucion Espanola.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-1978-31229', 'unit_text': 'articulo 24'}],
    ),
    (
        'codigo_civil',
        'Rige el art. 9 del Código Civil.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-1889-4763', 'unit_text': 'art. 9'}],
    ),
    (
        'lecrim',
        'Conforme al art. 118 LECrim, procede informar derechos.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-1882-6036', 'unit_text': 'art. 118'}],
    ),
    (
        'ley_39_norma',
        'La Ley 39/2015 regula el procedimiento administrativo.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2015-10565', 'unit_text': None}],
    ),
    (
        'real_decreto_completo',
        'Se aplicó el Real Decreto 463/2020 durante el estado de alarma.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2020-3692', 'unit_text': None}],
    ),
    (
        'ley_2_2023_ambigua',
        'Véase el artículo 42 de la Ley 2/2023.',
        [{'status': 'ambiguous', 'boe_id': None, 'unit_text': 'artículo 42'}],
    ),
    (
        'ley_2_2023_con_fecha',
        'Véase el artículo 42 de la Ley 2/2023, de 20 de febrero.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2023-4513', 'unit_text': 'artículo 42'}],
    ),
    (
        'multiples_normas_ambiguas',
        'Los arts. 14 y 15 de las Leyes 39/2015 y 40/2015 son relevantes.',
        [{'status': 'ambiguous', 'boe_id': None, 'unit_text': 'arts. 14 y 15'}],
    ),
    (
        'rango_articulos_lpaca',
        'Los arts. 13 a 15 LPACAP son materia de examen.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2015-10565', 'unit_text': 'arts. 13 a 15'}],
    ),
    (
        'articulo_y_siguientes',
        'El art. 14 y ss. de la Ley 39/2015 debe repasarse.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2015-10565', 'unit_text': 'art. 14 y ss.'}],
    ),
    (
        'articulo_con_subletra',
        'El art. 14.2.a) de la Ley 39/2015 se cita literalmente.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2015-10565', 'unit_text': 'art. 14.2.a)'}],
    ),
    (
        'articulo_bis',
        'El artículo 14 bis de la Ley 39/2015 debería detectarse.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2015-10565', 'unit_text': 'artículo 14 bis'}],
    ),
    (
        'rgpd_sigla_no_boe',
        'La base jurídica es el art. 6 RGPD.',
        [{'status': 'resolved-eurlex', 'boe_id': '32016R0679', 'unit_text': 'art. 6'}],
    ),
    (
        'reglamento_ue_no_boe',
        'La base jurídica es el artículo 6 del Reglamento (UE) 2016/679.',
        [{'status': 'resolved-eurlex', 'boe_id': '32016R0679', 'unit_text': 'artículo 6'}],
    ),
    (
        'orden_anexo',
        'Debe cumplirse el anexo I de la Orden HFP/1030/2021.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2021-15860', 'unit_text': 'anexo I'}],
    ),
    (
        'disposicion_final_larga',
        'Se aplica la disposición final séptima de la Ley 2/2023, de 20 de febrero.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2023-4513', 'unit_text': 'disposición final séptima'}],
    ),
    (
        'disposicion_final_abreviada',
        'Se aplica la disp. final séptima de la Ley 2/2023, de 20 de febrero.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2023-4513', 'unit_text': 'disp. final séptima'}],
    ),
    (
        'real_decreto_abreviado',
        'El art. 3 del RD 203/2021 regula la actuación administrativa automatizada.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2021-5032', 'unit_text': 'art. 3'}],
    ),
    (
        'ley_organica_abreviada_mas_rgpd',
        'El art. 6.1 de la LO 3/2018 debe coordinarse con el RGPD.',
        [
            {'status': 'resolved-url-only', 'boe_id': 'BOE-A-2018-16673', 'unit_text': 'art. 6.1'},
            {'status': 'resolved-eurlex', 'boe_id': '32016R0679', 'unit_text': None, 'norm_text': 'RGPD'},
        ],
    ),
    (
        'inferencia_una_norma_mismo_parrafo',
        'La Ley 39/2015 regula la relación electrónica. En su art. 14 se establece la obligación.',
        [
            {'status': 'resolved-url-only', 'boe_id': 'BOE-A-2015-10565', 'unit_text': None},
            {'status': 'resolved-url-only', 'boe_id': 'BOE-A-2015-10565', 'unit_text': 'art. 14'},
        ],
    ),
    (
        'no_infiere_entre_parrafos',
        'La Ley 39/2015 regula la relación electrónica.\n\nEl art. 14 se cita después.',
        [
            {'status': 'resolved-url-only', 'boe_id': 'BOE-A-2015-10565', 'unit_text': None},
            {'status': 'not-found', 'boe_id': None, 'unit_text': 'art. 14'},
        ],
    ),
    (
        'protege_url_y_codigo',
        'No tocar https://www.boe.es/buscar/act.php?id=BOE-A-2015-10565 ni `art. 14 Ley 39/2015`.',
        [],
    ),
    (
        'no_captura_stc_ni_procedimiento',
        'La STC 39/2015 no debe capturarse. Tampoco el procedimiento 39/2015.',
        [],
    ),
    (
        'boe_id_directo',
        'Referencia oficial BOE-A-2015-10565.',
        [{'status': 'resolved-url-only', 'boe_id': 'BOE-A-2015-10565', 'unit_text': None}],
    ),
]


def _assert_reference_expectations(references, expected):
    assert len(references) == len(expected)
    for reference, expected_item in zip(references, expected):
        assert reference.status == expected_item['status']
        expected_boe_id = expected_item.get('boe_id')
        actual_boe_id = reference.norm.boe_id if reference.norm else None
        assert actual_boe_id == expected_boe_id
        if 'unit_text' in expected_item:
            assert reference.unit_text == expected_item['unit_text']
        if 'norm_text' in expected_item:
            assert reference.norm_text == expected_item['norm_text']


@pytest.mark.parametrize(
    ('case_name', 'text', 'expected'),
    BOE_DEEP_CASES,
    ids=[case[0] for case in BOE_DEEP_CASES],
)
def test_boe_25_casos_de_uso_y_edge_cases(case_name, text, expected):
    resultado = detectar_referencias_boe(text)

    _assert_reference_expectations(resultado.references, expected)


def test_boe_detecta_sentencia_y_norma_completa_sin_meter_articulos():
    texto = (
        'La parte actora invoca el art. 217 de la LEC y el artículo 24 de la '
        'Constitución Española. Durante el estado de alarma se aplicó el '
        'Real Decreto 463/2020.'
    )

    resultado = detectar_referencias_boe(texto)

    assert resultado.stats.total_detected == 3
    assert resultado.references[0].unit_text == 'art. 217'
    assert resultado.references[0].norm.boe_id == 'BOE-A-2000-323'
    assert resultado.references[1].norm.boe_id == 'BOE-A-1978-31229'
    assert resultado.references[2].kind == 'norm'
    assert resultado.references[2].status == 'resolved-url-only'
    assert resultado.references[2].unit_text is None


def test_boe_detecta_oposicion_disposiciones_anexos_y_ue_a_eurlex():
    texto = (
        'Tema 3: Ley 39/2015, Ley 40/2015 y Real Decreto 203/2021. '
        'Estudiar arts. 13 y 14 de la Ley 39/2015; art. 6.1 LOPDGDD; '
        'anexo II del Real Decreto 311/2022 y Reglamento (UE) 2016/679.'
    )

    resultado = detectar_referencias_boe(texto)
    textos = [item.original_text for item in resultado.references]

    assert 'Ley 39/2015' in textos
    assert 'arts. 13 y 14 de la Ley 39/2015' in textos
    assert 'art. 6.1 LOPDGDD' in textos
    assert 'anexo II del Real Decreto 311/2022' in textos
    # El Reglamento (UE) 2016/679 se resuelve a su página en EUR-Lex.
    eu = [item for item in resultado.references if item.status == 'resolved-eurlex']
    assert eu and eu[0].norm is not None
    assert 'eur-lex.europa.eu' in eu[0].norm.url


def test_boe_marca_ley_2_2023_sola_como_ambigua_pero_fecha_exacta_resuelve():
    ambiguo = detectar_referencias_boe('Véase el artículo 42 de la Ley 2/2023.')
    exacto = detectar_referencias_boe('Véase el artículo 42 de la Ley 2/2023, de 20 de febrero.')

    assert ambiguo.references[0].status == 'ambiguous'
    assert ambiguo.references[0].reason == 'bare-number-year-known-ambiguous'
    assert exacto.references[0].status == 'resolved-url-only'
    assert exacto.references[0].norm.boe_id == 'BOE-A-2023-4513'


def test_boe_respeta_contextos_protegidos():
    texto = (
        'No tocar https://www.boe.es/buscar/act.php?id=BOE-A-2015-10565 '
        'ni `art. 14 de la Ley 39/2015` en código.'
    )

    resultado = detectar_referencias_boe(texto)

    assert resultado.references == []


def test_boe_infiere_solo_una_norma_activa_en_el_mismo_parrafo():
    claro = detectar_referencias_boe(
        'La Ley 39/2015 regula la relación electrónica. En su art. 14 se establece la obligación.'
    )
    ambiguo = detectar_referencias_boe(
        'La Ley 39/2015 y la Ley 40/2015 forman el marco básico. El art. 14 resulta relevante.'
    )

    assert claro.references[-1].unit_text == 'art. 14'
    assert claro.references[-1].norm.boe_id == 'BOE-A-2015-10565'
    assert ambiguo.references[-1].status == 'not-found'
    assert ambiguo.references[-1].reason == 'unit-without-norm'


def test_boe_overrides_permiten_referencia_manual_no_detectada():
    overrides = {
        'references': [
            {
                'text': 'la norma especial de informantes',
                'boe_id': 'BOE-A-2023-4513',
                'title': 'Ley 2/2023, de 20 de febrero',
                'unit': 'artículo 42',
            }
        ]
    }

    resultado = detectar_referencias_boe(
        'Debe revisarse la norma especial de informantes antes de cerrar el informe.',
        overrides=overrides,
    )

    assert resultado.stats.total_manual == 1
    assert resultado.references[0].status == 'manual'
    assert resultado.references[0].unit_text == 'artículo 42'
    assert resultado.references[0].norm.boe_id == 'BOE-A-2023-4513'
    assert 'Referencias manuales' in boe_report_to_html(resultado)


def test_boe_overrides_pueden_confirmar_referencia_detectada():
    overrides = {
        'references': [
            {
                'text': 'artículo 42 de la Ley 2/2023',
                'boe_id': 'BOE-A-2023-4513',
                'title': 'Ley 2/2023, de 20 de febrero',
                'unit': 'artículo 42',
            }
        ]
    }

    resultado = detectar_referencias_boe(
        'Véase el artículo 42 de la Ley 2/2023.',
        overrides=overrides,
    )

    referencia = resultado.references[0]
    assert referencia.status == 'manual'
    assert referencia.reason == 'manual-reference-override'
    assert referencia.kind == 'unit'
    assert referencia.norm.boe_id == 'BOE-A-2023-4513'


def test_boe_online_con_cliente_fixture_resuelve_bloque_de_articulo():
    resultado = enriquecer_boe(
        'La notificación se rige por el art. 14.2 de la Ley 39/2015.',
        BOEOptions(mode='online'),
        client=FakeBOEClient(),
    )

    referencia = resultado.references[0]
    assert referencia.status == 'resolved'
    assert referencia.unit_blocks[0].block_id == 'a14'
    assert 'Derecho y obligación' in referencia.unit_blocks[0].title
    assert 'Artículo 14' in referencia.unit_blocks[0].text
    markdown = boe_report_to_markdown(resultado)
    assert '### Artículo 14. Derecho y obligación de relacionarse electrónicamente' in markdown
    assert '#a14' in boe_report_by_paragraph_markdown(resultado)


def test_boe_online_marca_unidad_no_encontrada():
    resultado = enriquecer_boe(
        'La notificación cita el art. 999 de la Ley 39/2015.',
        BOEOptions(mode='online'),
        client=FakeBOEClient(),
    )

    referencia = resultado.references[0]
    assert referencia.status == 'not-found'
    assert referencia.reason == 'boe-unit-block-not-found'
    assert 'no se encontró esa unidad' in explicar_referencia_boe(referencia).lower()


def test_boe_online_con_cliente_fixture_no_elije_candidatos_ambiguos():
    resultado = enriquecer_boe(
        'La ayuda se regula por el Decreto 8/2021.',
        BOEOptions(mode='online'),
        client=FakeBOEClient(),
    )

    referencia = resultado.references[0]
    assert referencia.status == 'ambiguous'
    assert len(referencia.candidates) == 2
    template = boe_overrides_template(resultado)
    assert template['references'][0]['candidates'][0]['boe_id'] == 'BOE-A-2021-111'
    assert 'varios candidatos' in revisar_boe(resultado).items[0].explanation


def test_boe_online_ignora_referencias_no_soportadas_sin_consultar_boe():
    resultado = enriquecer_boe(
        'La base jurídica es el art. 6 RGPD.',
        BOEOptions(mode='online', include_unit_text=False),
        client=FakeBOEClient(),
    )

    # Resuelto a EUR-Lex: no se consulta la API del BOE para esta referencia.
    assert resultado.references[0].status == 'resolved-eurlex'


def test_boe_unit_targets_rangos_sufijos_y_disposiciones():
    assert _unit_targets('arts. 13 a 15') == ['artículo 13', 'artículo 14', 'artículo 15']
    assert _unit_targets('artículo 14 bis') == ['artículo 14 bis']
    assert _unit_targets('disp. final septima') == ['disposición final séptima']
    assert _unit_targets('arts. 1 a 80') == ['artículo 1', 'artículo 80']


def test_boe_markdown_y_cli_json(capsys, tmp_path):
    texto = 'La notificación se rige por el art. 14.2 de la Ley 39/2015.'
    resultado = detectar_referencias_boe(texto)
    markdown = boe_report_to_markdown(resultado)

    assert '# legal-expand BOE' in markdown
    assert 'Ley 39/2015' in markdown
    assert 'carácter meramente informativo' in markdown

    input_file = tmp_path / 'doc.txt'
    input_file.write_text(texto, encoding='utf-8')

    assert cli_main(['boe', str(input_file), '--report-format', 'json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['stats']['total_detected'] == 1
    assert data['references'][0]['norm']['boe_id'] == 'BOE-A-2015-10565'


def test_boe_review_explica_y_agrupa_referencias():
    resultado = detectar_referencias_boe(
        'El art. 24 de la Constitución Española se cita junto al art. 6 RGPD. '
        'Véase también el artículo 42 de la Ley 2/2023.'
    )

    review = revisar_boe(resultado)
    sections = [item.section for item in review.items]

    assert review.summary.total_references == 3
    # Constitución (BOE) y RGPD (EUR-Lex) quedan resueltas; la Ley 2/2023 ambigua.
    assert review.summary.resolved == 2
    assert review.summary.review_required == 1
    assert review.summary.unsupported == 0
    assert sections == ['resolved', 'resolved', 'review-required']
    assert 'norma se identificó' in review.items[0].explanation.lower()
    assert 'eur-lex' in review.items[1].explanation.lower()
    assert 'número y año' in review.items[2].explanation.lower()
    assert explicar_referencia_boe(resultado.references[2]) == review.items[2].explanation
    markdown = boe_report_to_markdown(resultado)
    assert '## Requieren revisión' in markdown
    # El RGPD queda resuelto con su enlace de EUR-Lex.
    assert 'eur-lex.europa.eu' in markdown


def test_boe_overrides_template_solo_incluye_pendientes():
    resultado = detectar_referencias_boe(
        'El art. 24 de la Constitución Española se cita junto al artículo 42 de la Ley 2/2023.'
    )

    template = boe_overrides_template(resultado)

    assert template['aliases'] == {}
    assert len(template['references']) == 1
    assert template['references'][0]['text'] == 'artículo 42 de la Ley 2/2023'
    assert template['references'][0]['unit'] == 'artículo 42'
    assert template['references'][0]['boe_id'] == ''
    assert 'review_note' in template['references'][0]


def test_boe_html_y_paragraph_report():
    texto = (
        'Primero, el art. 24 de la Constitución Española.\n\n'
        'Después, el artículo 42 de la Ley 2/2023.'
    )
    resultado = detectar_referencias_boe(texto)

    html = boe_report_to_html(resultado)
    paragraphs = boe_report_by_paragraph_markdown(resultado)

    assert '<section class="legal-expand-boe">' in html
    assert 'https://www.boe.es/buscar/act.php?id=BOE-A-1978-31229' in html
    assert 'Requieren revisión' in html
    assert '> Referencias BOE sugeridas:' in paragraphs
    assert 'art. 24' in paragraphs
    assert 'artículo 42' in paragraphs


def test_plain_text_ignora_status_boe():
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<response><status><code>200</code><text>ok</text></status>'
        '<data>Artículo 14. Contenido íntegro del artículo.</data></response>'
    )
    assert _plain_text(body) == 'Artículo 14. Contenido íntegro del artículo.'


def test_get_block_text_pide_xml_y_trae_texto(monkeypatch, tmp_path):
    import urllib.request

    captured = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return (
                b'<response><status><code>200</code><text>ok</text></status>'
                b'<data>Texto integro del bloque.</data></response>'
            )

    def _fake_urlopen(request, timeout=None):
        captured['accept'] = request.get_header('Accept')
        captured['url'] = request.full_url
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, 'urlopen', _fake_urlopen)
    client = BOEClient(BOEOptions(mode='online', cache_path=str(tmp_path)))
    text = client.get_block_text('BOE-A-2015-10565', 'a14')

    assert captured['accept'] == 'application/xml'
    assert 'texto/bloque/a14' in captured['url']
    assert text == 'Texto integro del bloque.'


def test_boe_client_transport_inyectable(tmp_path):
    calls = []

    def transport(url, accept):
        calls.append((url, accept))
        return (
            '<response><status><code>200</code><text>ok</text></status>'
            '<data>Artículo 14. Texto real del artículo.</data></response>'
        )

    client = BOEClient(
        BOEOptions(mode='online', cache_path=str(tmp_path)),
        base_url='https://proxy.example',
        transport=transport,
    )
    text = client.get_block_text('BOE-A-2015-10565', 'a14')

    assert text == 'Artículo 14. Texto real del artículo.'
    assert calls[0][0].startswith('https://proxy.example/datosabiertos/api/')
    assert calls[0][0].endswith('/texto/bloque/a14')
    assert calls[0][1] == 'application/xml'


def test_fetch_eurlex_html_usa_host_correcto(monkeypatch):
    import urllib.request

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'<html></html>'

    urls: list[str] = []
    monkeypatch.setattr(urllib.request, 'urlopen', lambda req, timeout=None: (urls.append(req.full_url), _Resp())[1])

    # base_url oficial del BOE -> EUR-Lex se pide a su host oficial, no al BOE.
    BOEClient(BOEOptions(mode='online')).fetch_eurlex_html('32016R0679')
    assert urls[-1].startswith('https://eur-lex.europa.eu/legal-content/')
    assert 'www.boe.es' not in urls[-1]

    # Con transporte y base_url de proxy -> se enruta por el proxy.
    got: list[str] = []
    client = BOEClient(
        BOEOptions(mode='online'),
        base_url='https://proxy.example',
        transport=lambda url, accept: (got.append(url), '<html></html>')[1],
    )
    client.fetch_eurlex_html('32016R0679')
    assert got[-1].startswith('https://proxy.example/legal-content/')


def test_is_safe_http_url_allowlist():
    assert _is_safe_http_url('https://www.boe.es/buscar/act.php?id=BOE-A-1')
    assert _is_safe_http_url('http://example.com')
    assert _is_safe_http_url('/ruta/relativa')
    assert not _is_safe_http_url('javascript:alert(1)')
    assert not _is_safe_http_url('  javascript:alert(1)')
    assert not _is_safe_http_url('data:text/html,<script>alert(1)</script>')
    assert not _is_safe_http_url('java\tscript:alert(1)')
    assert not _is_safe_http_url('java\nscript:alert(1)')


def test_boe_html_report_neutraliza_esquema_peligroso():
    overrides = {
        'references': [
            {
                'text': 'PELIGRO',
                'boe_id': 'BOE-A-9999',
                'title': 'Referencia manipulada',
                'url': 'javascript:alert(document.cookie)',
            }
        ]
    }
    resultado = detectar_referencias_boe('Véase PELIGRO en el expediente.', overrides=overrides)
    html = boe_report_to_html(resultado)

    assert 'href="javascript:' not in html
    assert 'javascript:alert(document.cookie)' in html


def test_boe_cli_review_html_paragraphs_y_overrides_template(capsys, tmp_path):
    texto = 'Véase el art. 24 de la Constitución Española y el artículo 42 de la Ley 2/2023.'
    input_file = tmp_path / 'doc.txt'
    input_file.write_text(texto, encoding='utf-8')

    assert cli_main(['boe', str(input_file), '--report-format', 'review-json']) == 0
    review = json.loads(capsys.readouterr().out)
    assert review['summary']['review_required'] == 1

    assert cli_main(['boe', str(input_file), '--report-format', 'html']) == 0
    assert '<section class="legal-expand-boe">' in capsys.readouterr().out

    assert cli_main(['boe', str(input_file), '--report-format', 'paragraphs']) == 0
    assert '> Referencias BOE sugeridas:' in capsys.readouterr().out

    assert cli_main(['boe', str(input_file), '--overrides-template']) == 0
    template = json.loads(capsys.readouterr().out)
    assert template['references'][0]['text'] == 'artículo 42 de la Ley 2/2023'


def test_boe_client_solo_permite_base_url_oficial():
    with pytest.raises(ValueError):
        BOEClient(base_url='file:///tmp/fake')

    with pytest.raises(ValueError):
        BOEClient(base_url='https://example.com')


def test_boe_xml_rechaza_doctype_y_entity():
    xml = """<?xml version="1.0"?>
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
<response><identificador>&xxe;</identificador></response>
"""

    assert _parse_norms(xml) == []
