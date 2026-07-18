"""
Tests dirigidos para completar la cobertura al 100% (statements y branches).

Cubren ramas defensivas y de error que el resto de la batería no ejerce:
errores de red/transporte BOE, parsing XML/JSON defensivo, resolución de
conflictos del diccionario en caja blanca, y ramas de informe.

Ningún test requiere red: todo transporte BOE/EUR-Lex se inyecta o se
construye a mano. Los singletons se resetean en un fixture autouse.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from legal_expand import boe as boe_mod
from legal_expand import boe_catalog
from legal_expand.boe import (
    BOEClient,
    BOENetworkError,
)
from legal_expand.config import GlobalConfigManager
from legal_expand.core import engine as engine_mod
from legal_expand.core.engine import (
    benchmark_texto,
    exportar_glosario,
    extraer_siglas,
    generar_glosario,
)
from legal_expand.core.matcher import (
    DictionaryIndex,
    DictionaryIndexMetadata,
    SiglasMatcher,
    get_matcher,
)
from legal_expand.core import normalizer
from legal_expand.core.engine import auditar_texto
from legal_expand import cli
from legal_expand import eurlex
from legal_expand.documents import expandir_documento
from legal_expand.types import (
    BOENorm,
    BOEOptions,
    BOEUnitBlock,
    DictionaryEntry,
    ExpansionOptions,
    GlobalConfig,
    InternalOptions,
)


@pytest.fixture(autouse=True)
def _reset_singletons():
    SiglasMatcher.reset_instance()
    GlobalConfigManager.reset_instance()
    yield
    SiglasMatcher.reset_instance()
    GlobalConfigManager.reset_instance()


# ============================================================================
# config.py
# ============================================================================

def test_config_reset_instance_clears_singleton():
    first = GlobalConfigManager.get_instance()
    GlobalConfigManager.reset_instance()  # cubre 114-115
    second = GlobalConfigManager.get_instance()
    assert first is not second


def test_config_resolve_include_uses_default_list():
    resolved = GlobalConfigManager._resolve_include(None, ['AEAT'])  # cubre 162
    assert resolved == ['AEAT']
    # copia, no la misma lista
    assert resolved is not None


def test_config_set_config_with_enabled_none_keeps_enabled():
    manager = GlobalConfigManager.get_instance()
    manager.set_config(GlobalConfig(enabled=None, default_options=ExpansionOptions(format='html')))  # 178->181
    config = manager.get_config()
    assert config.enabled is True
    assert config.default_options is not None
    assert config.default_options.format == 'html'


def test_config_double_check_locking_inner_instance_set(monkeypatch):
    GlobalConfigManager.reset_instance()
    sentinel = GlobalConfigManager()  # instancia real de reserva
    GlobalConfigManager.reset_instance()

    class _FakeLock:
        def __enter__(self):
            GlobalConfigManager._instance = sentinel
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(GlobalConfigManager, '_lock', _FakeLock())
    result = GlobalConfigManager()  # 91->94: el check interno ve la instancia ya puesta
    assert result is sentinel


# ============================================================================
# core/engine.py
# ============================================================================

def test_exportar_glosario_unsupported_format_raises():
    with pytest.raises(ValueError):
        exportar_glosario('La AEAT actua', 'xml')  # cubre 423


def test_benchmark_texto_non_positive_iterations_raises():
    with pytest.raises(ValueError):
        benchmark_texto('La AEAT', iterations=0)  # cubre 466


def test_extraer_siglas_skips_known_dotted_short_acronym():
    # 'C.E.' no está en el patrón (2 letras no generan forma con puntos) pero
    # sí lo resuelve buscar_sigla: el candidato desconocido se descarta (282).
    output = extraer_siglas('El C.E. dice algo')
    assert output.acronyms == []


def test_generar_glosario_skips_unknown_omitted(monkeypatch):
    # Matcher en caja blanca que produce un omitido 'not-found' cuyo buscar_sigla
    # es None: el glosario lo salta (engine 350).
    index = DictionaryIndex(entries=[], exact_index={}, normalized_index={})
    fake = object.__new__(SiglasMatcher)
    fake._index = index
    fake._pattern = re.compile(r'(?<![a-zA-Z0-9])(ZZZ)(?![a-zA-Z0-9])')
    monkeypatch.setattr(engine_mod, 'get_matcher', lambda *a, **k: fake)
    assert generar_glosario('hay ZZZ aqui') == []


# ============================================================================
# documents.py
# ============================================================================

def test_expandir_documento_text_structured_returns_expanded_text():
    result = expandir_documento('La AEAT actua', ExpansionOptions(format='structured'), 'text')  # 87
    assert isinstance(result, str)
    assert 'Agencia Estatal de Administración Tributaria' in result


def test_expandir_documento_html_structured_returns_expanded_text():
    result = expandir_documento('<p>La AEAT</p>', ExpansionOptions(format='structured'), 'html')  # 47
    assert '<p>' in result
    assert 'Agencia Estatal de Administración Tributaria' in result


# ============================================================================
# eurlex.py
# ============================================================================

def test_article_extractor_ignores_whitespace_only_data():
    parser = eurlex._ArticleTextExtractor()
    parser.feed('<p>   </p>')  # 48->exit: data.strip() vacío
    assert parser.text() == ''


def test_fragment_text_next_match_none_uses_end_of_doc():
    assert eurlex._fragment_text('<b>hola</b>', 0, 3, None) == 'hola'  # 68-69


def test_fragment_text_end_leq_start_falls_back():
    result = eurlex._fragment_text('nodelims', 4, 5, re.search(r'e', 'xe'))  # 66-67
    assert result == 'li'


def test_anio_y_numero_ambiguous_returns_none():
    assert eurlex._anio_y_numero('1999', '2000') is None  # ambos años -> 149
    assert eurlex._anio_y_numero('10', '20') is None  # ninguno año -> 149


def test_resolve_eu_norm_sector_but_unresolvable_number():
    assert eurlex.resolve_eu_norm('Directiva 1999/2000') is None  # 176


# ============================================================================
# core/normalizer.py
# ============================================================================

def test_is_inside_url_domain_like_without_typical_extension():
    text = 'prefix.longextension' + 'AEAT' + 'suffix'
    # 'before' parece dominio y 'after' empieza en no-espacio, pero la extensión
    # no casa el patrón típico -> False (228->231).
    assert normalizer.is_inside_url(text, 20, 24) is False


# ============================================================================
# core/matcher.py  (índice en caja blanca)
# ============================================================================

def _white_box_index() -> DictionaryIndex:
    entries = [
        DictionaryEntry(id='aa1', original='AA', significado='Alfa', variants=['AA']),
        DictionaryEntry(id='pp1', original='PP', significado='Partido Popular', variants=['PP'], priority=50),
        DictionaryEntry(
            id='pp2', original='PP', significado='Procedimiento Penal',
            variants=['PP'], priority=90, context_keywords=['penal'],
        ),
        DictionaryEntry(id='zz1', original='ZZ', significado='Zeta Uno', variants=['ZZ'], priority=10),
        DictionaryEntry(id='zz2', original='ZZ', significado='Zeta Dos', variants=['ZZ'], priority=20),
        DictionaryEntry(id='dup1', original='DUP', significado='Mismo', variants=['DUP']),
        DictionaryEntry(id='dup2', original='DUP', significado='Mismo', variants=['DUP']),
        DictionaryEntry(id='xy1', original='XY', significado='Equis Ye', variants=['XY']),
    ]
    exact_index = {
        'AA': ['aa1'],
        'PP': ['pp1', 'pp2'],
        'ZZ': ['zz1', 'zz2'],
        'DUP': ['dup1', 'dup2'],
        'XY': ['xy1'],
    }
    # 'xy' se omite adrede del índice normalizado para forzar la rama 914.
    normalized_index = {
        'aa': ['aa1'],
        'pp': ['pp1', 'pp2'],
        'zz': ['zz1', 'zz2'],
        'dup': ['dup1', 'dup2'],
    }
    metadata = DictionaryIndexMetadata(
        conflicts=[{
            'sigla': 'PP',
            'defaultId': 'pp1',
            'variants': [
                {'significado': 'Partido Popular'},
                {'significado': 'Procedimiento Penal'},
            ],
        }],
        version='test',
        build_date='2026-01-01',
        custom_dictionaries=[],
    )
    return DictionaryIndex(entries, exact_index, normalized_index, metadata)


def test_index_lookup_single_id():
    index = _white_box_index()
    entry = index.lookup('AA')
    assert entry is not None and entry.significado == 'Alfa'


def test_index_lookup_case_sensitive_miss_returns_none():
    index = _white_box_index()
    assert index.lookup('NOPE', case_sensitive=True) is None  # 171->177


def test_index_lookup_conflict_default_without_context():
    index = _white_box_index()
    entry = index.lookup('PP')  # context None -> 193; conflicto -> pp1 (208-212, 249-251)
    assert entry is not None and entry.significado == 'Partido Popular'


def test_index_lookup_context_keyword_wins():
    index = _white_box_index()
    entry = index.lookup('PP', case_sensitive=False, context_text='asunto penal grave')
    assert entry is not None and entry.significado == 'Procedimiento Penal'


def test_index_lookup_no_conflict_falls_back_to_priority():
    index = _white_box_index()
    entry = index.lookup('ZZ')  # sin conflicto -> 213 -> max prioridad (253-254)
    assert entry is not None and entry.significado == 'Zeta Dos'


def test_index_resolve_ids_empty():
    index = _white_box_index()
    assert index._resolve_ids([], 'x') is None  # 234-235


def test_index_resolve_ids_all_ghost():
    index = _white_box_index()
    assert index._resolve_ids(['ghost1', 'ghost2'], 'x') is None  # 242-243 y 183->181


def test_index_has_multiple_meanings_via_conflict():
    index = _white_box_index()
    assert index.has_multiple_meanings('PP') is True  # 267-269


def test_index_has_multiple_meanings_via_exact_index():
    index = _white_box_index()
    assert index.has_multiple_meanings('ZZ') is True  # 271-273


def test_index_has_multiple_meanings_single():
    index = _white_box_index()
    assert index.has_multiple_meanings('AA') is False  # 275-276


def test_index_get_all_meanings_conflict():
    index = _white_box_index()
    assert index.get_all_meanings('PP') == ['Partido Popular', 'Procedimiento Penal']  # 289-295


def test_index_get_all_meanings_dedupes_repeated():
    index = _white_box_index()
    assert index.get_all_meanings('DUP') == ['Mismo']  # 304->302 (duplicado se salta)


def test_index_get_all_meanings_unknown_empty():
    index = _white_box_index()
    assert index.get_all_meanings('NOPE') == []  # 298-299, 307


def test_matcher_buscar_sigla_empty_meanings_fallback():
    index = _white_box_index()
    matcher = object.__new__(SiglasMatcher)
    matcher._index = index
    # 'X.Y' resuelve por match flexible pero get_all_meanings devuelve [] -> 914
    result = matcher.buscar_sigla('X.Y')
    assert result is not None and result.meanings == ['Equis Ye']


def test_matcher_listar_siglas_dedupes_originals():
    index = _white_box_index()
    matcher = object.__new__(SiglasMatcher)
    matcher._index = index
    assert matcher.listar_siglas() == ['AA', 'DUP', 'PP', 'XY', 'ZZ']  # 933->932


def test_matcher_find_matches_wrapper():
    matcher = get_matcher()
    result = matcher.find_matches('La AEAT informa', InternalOptions())  # 655
    assert any(m.original == 'AEAT' for m in result)


def test_matcher_find_matches_not_found_omitted():
    index = DictionaryIndex(entries=[], exact_index={}, normalized_index={})
    matcher = object.__new__(SiglasMatcher)
    matcher._index = index
    matcher._pattern = re.compile(r'(?<![a-zA-Z0-9])(ZZZ)(?![a-zA-Z0-9])')
    result = matcher.find_matches_detailed('hay ZZZ aqui', InternalOptions())  # 861-866
    assert result.matches == []
    assert result.omitted_matches[0].reason == 'not-found'


def test_matcher_find_matches_part_of_larger_word():
    index = DictionaryIndex(entries=[], exact_index={}, normalized_index={})
    matcher = object.__new__(SiglasMatcher)
    matcher._index = index
    matcher._pattern = re.compile(r'(AEAT)')  # sin límites de palabra
    result = matcher.find_matches_detailed('XAEATX', InternalOptions())  # 828
    assert result.matches == []
    assert result.omitted_matches == []


def test_matcher_manual_duplicate_resolution():
    matcher = get_matcher()
    options = InternalOptions(duplicate_resolution={'LBRL': 'MI RESOLUCION'})
    result = matcher.find_matches_detailed('Segun la LBRL local', options)  # 744-745, 764
    assert any(m.expansion == 'MI RESOLUCION' for m in result.matches)


def test_matcher_manual_duplicate_resolution_no_match():
    # Clave que no casa: se agota el bucle sin resolver (744->743).
    options = InternalOptions(duplicate_resolution={'OTRA': 'x'})
    assert SiglasMatcher._manual_duplicate_resolution(options, 'lbrl') is None


def test_matcher_ambiguous_unresolved_omitted():
    matcher = get_matcher()
    result = matcher.find_matches_detailed('Segun la LBRL local', InternalOptions())  # 769, 872-880
    assert any(o.reason == 'ambiguous-unresolved' for o in result.omitted_matches)


def test_matcher_split_list_value_variants():
    assert SiglasMatcher._split_list_value(None) == []  # 513-514
    assert SiglasMatcher._split_list_value(['a', '', 'b']) == ['a', 'b']  # 515-516
    assert SiglasMatcher._split_list_value('   ') == []  # 519


def test_matcher_custom_entry_not_a_dict():
    matcher = get_matcher()
    with pytest.raises(ValueError):
        matcher._custom_entry_from_mapping('no-dict', Path('x.json'), 1)  # 533


def test_matcher_custom_entry_missing_fields():
    matcher = get_matcher()
    with pytest.raises(ValueError):
        matcher._custom_entry_from_mapping({'original': 'X'}, Path('x.json'), 1)  # 547


def test_matcher_custom_dictionary_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        SiglasMatcher(custom_dictionaries=[str(tmp_path / 'nope.json')])  # 476


def test_matcher_custom_dictionary_unsupported_format(tmp_path):
    bad = tmp_path / 'dict.txt'
    bad.write_text('nada', encoding='utf-8')
    with pytest.raises(ValueError):
        SiglasMatcher(custom_dictionaries=[str(bad)])  # 483


def test_matcher_custom_json_not_a_list(tmp_path):
    bad = tmp_path / 'dict.json'
    bad.write_text('{"foo": 1}', encoding='utf-8')
    with pytest.raises(ValueError):
        SiglasMatcher(custom_dictionaries=[str(bad)])  # 496


def test_matcher_base_double_check_locking(monkeypatch):
    SiglasMatcher.reset_instance()
    sentinel = SiglasMatcher.get_instance()
    SiglasMatcher.reset_instance()

    class _FakeLock:
        def __enter__(self):
            SiglasMatcher._instance = sentinel
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(SiglasMatcher, '_lock', _FakeLock())
    result = SiglasMatcher()  # 392->395
    assert result is sentinel


def test_matcher_custom_double_check_locking(monkeypatch):
    SiglasMatcher.reset_instance()
    sentinel = SiglasMatcher.get_instance()
    key = ('phantom.json',)

    class _FakeLock:
        def __enter__(self):
            SiglasMatcher._custom_instances[key] = sentinel
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(SiglasMatcher, '_lock', _FakeLock())
    result = SiglasMatcher(custom_dictionaries=['phantom.json'])  # 384->388
    assert result is sentinel


# ============================================================================
# boe_catalog.py
# ============================================================================

def test_boe_catalog_load_index_error(monkeypatch):
    monkeypatch.setattr(boe_catalog, '_INDEX_PATH', Path('/nonexistent/boe_index.json'))
    boe_catalog._load_index.cache_clear()
    try:
        assert boe_catalog._load_index() == {'index': {}}  # 87-91
    finally:
        boe_catalog._load_index.cache_clear()


def test_boe_catalog_candidate_rangos_no_match():
    assert boe_catalog._candidate_rangos('texto sin rango legal') == ()  # 131


def test_boe_catalog_resolve_bare_number_single_estatal():
    norm = boe_catalog.resolve_norm_from_catalog('3/2018')  # 171 (matches=list(entries))
    assert norm is not None and norm.boe_id == 'BOE-A-2018-16673'


def test_boe_catalog_resolve_bare_number_ambiguous():
    assert boe_catalog.resolve_norm_from_catalog('1/2020') is None  # 179


# ============================================================================
# boe.py
# ============================================================================

def test_boe_fetch_via_transport_reraises_network_error():
    def transport(url, accept):
        raise BOENetworkError('boom')

    client = BOEClient(BOEOptions(mode='online'), transport=transport)
    with pytest.raises(BOENetworkError):
        client._fetch_via_transport('https://www.boe.es/x', 'application/json')  # 328-329


def test_boe_fetch_via_transport_wraps_other_error():
    def transport(url, accept):
        raise ValueError('bad')

    client = BOEClient(BOEOptions(mode='online'), transport=transport)
    with pytest.raises(BOENetworkError):
        client._fetch_via_transport('https://www.boe.es/x', 'application/json')  # 330-331


def test_boe_resolve_norm_single_exact(tmp_path):
    import json

    body = json.dumps([
        {'identificador': 'BOE-A-1', 'titulo': 'Ley 39/2015', 'numero_oficial': '39/2015'},
        {'identificador': 'BOE-A-2', 'titulo': 'Ley 40/2015', 'numero_oficial': '40/2015'},
    ])
    client = BOEClient(
        BOEOptions(mode='online', cache_path=str(tmp_path)),
        transport=lambda url, accept: body,
    )
    norm, candidates = client.resolve_norm('Ley 39/2015')  # 400
    assert norm is not None and norm.boe_id == 'BOE-A-1'
    assert len(candidates) == 2


def test_boe_find_unit_blocks_skips_missing_block_id():
    client = BOEClient(BOEOptions(mode='offline'))
    client.get_index = lambda boe_id: [{'id': '', 'title': 'artículo 1'}]  # type: ignore[method-assign]
    assert client.find_unit_blocks('BOE-A-1', 'art. 1') == []  # 424


def test_boe_plain_text_uses_last_version():
    xml = '<response><data><version>uno</version><version>dos</version></data></response>'
    assert boe_mod._plain_text(xml) == 'dos'  # 556-559 (558)


def test_boe_iter_strings_scalar_returns_empty():
    assert boe_mod._iter_strings(123) == []  # 597


def test_boe_manual_alias_loop_without_match():
    assert boe_mod._manual_alias('BAR', {'aliases': {'FOO': 'BOE-A-1'}}) is None  # 674->673


def test_boe_norm_from_override_non_dict_returns_none():
    assert boe_mod._norm_from_override(123) is None  # 684


def test_boe_build_norm_reference_known_ambiguous():
    output = boe_mod.detectar_referencias_boe('Se aplica la Ley 2/2023 hoy.', BOEOptions(mode='offline'))
    norm_refs = [ref for ref in output.references if ref.norm_text and '2/2023' in ref.norm_text]
    assert norm_refs and norm_refs[0].status == 'ambiguous'  # 721
    assert norm_refs[0].reason == 'bare-number-year-known-ambiguous'


def test_boe_build_unit_reference_needs_search():
    output = boe_mod.detectar_referencias_boe(
        'Ver el artículo 5 de la Ley 99/2099 aqui.', BOEOptions(mode='offline')
    )
    unit_refs = [ref for ref in output.references if ref.kind == 'unit']
    assert unit_refs and unit_refs[0].status == 'needs-boe-search'  # 758


def _norm_ref(status='needs-boe-search'):
    return boe_mod._reference('MATCH', 0, 5, 'norm', status, norm_text='MATCH')


def test_boe_apply_reference_override_item_text_not_str():
    ref = _norm_ref()
    boe_mod._apply_reference_override(ref, {'references': [{'text': 123, 'boe_id': 'BOE-A-1'}]})  # 788
    assert ref.status == 'needs-boe-search'


def test_boe_apply_reference_override_text_mismatch():
    ref = _norm_ref()
    boe_mod._apply_reference_override(ref, {'references': [{'text': 'OTHER', 'boe_id': 'BOE-A-1'}]})  # 790
    assert ref.status == 'needs-boe-search'


def test_boe_apply_reference_override_norm_none():
    ref = _norm_ref()
    boe_mod._apply_reference_override(ref, {'references': [{'text': 'MATCH'}]})  # 793
    assert ref.status == 'needs-boe-search'


def test_boe_apply_reference_override_matches_without_unit():
    ref = _norm_ref()
    out = boe_mod._apply_reference_override(
        ref, {'references': [{'text': 'MATCH', 'boe_id': 'BOE-A-9', 'title': 'T'}]}
    )  # 794-798, 799->802
    assert out.status == 'manual'
    assert out.norm is not None and out.norm.boe_id == 'BOE-A-9'
    assert out.kind == 'norm'


def test_boe_eu_reference_unsupported_and_report():
    output = boe_mod.detectar_referencias_boe(
        'Segun la Directiva 1999/2000 europea.', BOEOptions(mode='offline')
    )
    unsupported = [ref for ref in output.references if ref.status == 'unsupported']
    assert unsupported  # 947

    review = boe_mod.revisar_boe(output)
    assert any(item.section == 'unsupported' for item in review.items)  # 1215

    markdown = boe_mod.boe_report_to_markdown(output)  # 1446-1453, 1457
    assert 'No soportadas' in markdown


def test_boe_detect_unit_then_eu_overlap_skips():
    text = 'el artículo 5 del Reglamento (UE) 2016/679'
    added = []
    boe_mod._detect_unit_then_eu_references(text, [(0, len(text))], added.append)  # 963
    assert added == []


def test_boe_detect_unit_then_norm_overlap_skips():
    text = 'el artículo 5 de la Ley 39/2015'
    added = []
    boe_mod._detect_unit_then_norm_references(text, BOEOptions(), {}, [(0, len(text))], added.append)  # 975->974
    assert added == []


def test_boe_enrich_reference_skip_status():
    ref = boe_mod._reference('X', 0, 1, 'unsupported', 'not-found', norm_text='X')
    client = BOEClient(BOEOptions(mode='online'), transport=lambda u, a: '')
    assert boe_mod._enrich_reference(ref, BOEOptions(mode='online'), client) is ref  # 1099


def test_boe_enrich_eurlex_reference_full():
    html_doc = (
        '<p id="art_6">Artículo 6. Licitud del tratamiento aqui.</p>'
        '<p id="art_7">Siguiente</p>'
    )
    client = BOEClient(BOEOptions(mode='online'), transport=lambda url, accept: html_doc)
    norm = BOENorm(boe_id='32016R0679', title='RGPD', url='https://eur-lex.europa.eu/x', source='eur-lex')
    ref = boe_mod._reference(
        'artículo 6 del RGPD', 0, 10, 'eu', 'resolved-eurlex',
        norm=norm, unit_text='artículo 6',
    )
    out = boe_mod._enrich_eurlex_reference(ref, BOEOptions(mode='online', include_unit_text=True), client)
    assert out.unit_blocks and out.unit_blocks[0].text  # 1118-1133
    assert out.reason == 'eurlex-unit-block-resolved'


def test_boe_enrich_eurlex_reference_article_not_found():
    client = BOEClient(BOEOptions(mode='online'), transport=lambda url, accept: '<p>nada relevante</p>')
    norm = BOENorm(boe_id='32016R0679', title='RGPD', url='https://x', source='eur-lex')
    ref = boe_mod._reference('artículo 6 del RGPD', 0, 5, 'eu', 'resolved-eurlex', norm=norm, unit_text='artículo 6')
    out = boe_mod._enrich_eurlex_reference(ref, BOEOptions(include_unit_text=True), client)  # 1123->1133
    assert out.unit_blocks == []


def test_boe_enrich_eurlex_reference_no_unit_number():
    client = BOEClient(BOEOptions(mode='online'), transport=lambda url, accept: '')
    norm = BOENorm(boe_id='32016R0679', title='RGPD', url='https://x', source='eur-lex')
    ref = boe_mod._reference('anexo del RGPD', 0, 5, 'eu', 'resolved-eurlex', norm=norm, unit_text='anexo')
    out = boe_mod._enrich_eurlex_reference(ref, BOEOptions(include_unit_text=True), client)  # 1119-1120
    assert out.unit_blocks == []


def test_boe_enrich_eurlex_reference_early_return():
    client = BOEClient(BOEOptions(mode='online'), transport=lambda url, accept: '')
    norm = BOENorm(boe_id='32016R0679', title='RGPD', url='https://x', source='eur-lex')
    ref = boe_mod._reference('artículo 6', 0, 5, 'eu', 'resolved-eurlex', norm=norm, unit_text='artículo 6')
    out = boe_mod._enrich_eurlex_reference(ref, BOEOptions(include_unit_text=False), client)  # 1116-1117
    assert out.unit_blocks == []


def test_boe_enrich_unit_blocks_norm_none():
    client = BOEClient(BOEOptions(mode='offline'))
    ref = boe_mod._reference('x', 0, 1, 'unit', 'resolved-url-only', unit_text='art 5')
    assert boe_mod._enrich_unit_blocks(ref, client) is ref  # 1164


def test_boe_enrich_unit_blocks_manual_keeps_status():
    client = BOEClient(BOEOptions(mode='offline'))
    client.find_unit_blocks = lambda boe_id, unit: []  # type: ignore[method-assign]
    norm = BOENorm(boe_id='BOE-A-1', title='t', url='u')
    ref = boe_mod._reference('x', 0, 1, 'unit', 'manual', norm=norm, unit_text='art 5')
    out = boe_mod._enrich_unit_blocks(ref, client)  # 1171->1174
    assert out.status == 'manual'


def test_boe_overrides_template_without_norm_text():
    output = boe_mod.enriquecer_boe('Ver el artículo 5 aqui.', BOEOptions(mode='offline'))
    template = boe_mod.boe_overrides_template(output)
    assert template['references']  # 1267->1269
    entry = template['references'][0]
    assert 'norm' not in entry
    assert entry['unit']


def test_boe_dedupe_article_targets_skips_duplicate():
    assert boe_mod._dedupe_article_targets([('5', ''), ('5', '')]) == ['artículo 5']  # 1330->1326


def test_boe_append_unit_blocks_markdown_skips_empty_text():
    lines: list[str] = []
    ref = boe_mod._reference('x', 0, 1, 'unit', 'resolved', unit_text='a')
    ref.unit_blocks = [
        BOEUnitBlock(unit='a', block_id='b', title='T1', url='u', text=None),
        BOEUnitBlock(unit='a', block_id='c', title='T2', url='u', text='contenido'),
    ]
    boe_mod._append_unit_blocks_markdown(lines, ref)  # 1419->1418 y 1420
    assert any('contenido' in line for line in lines)
    assert not any('T1' in line for line in lines)


def test_boe_append_warning_markdown_empty():
    lines = ['x']
    boe_mod._append_warning_markdown(lines, [])  # 1464->exit
    assert lines == ['x']


def test_boe_report_html_unit_blocks_and_no_warnings():
    norm = BOENorm(boe_id='32016R0679', title='RGPD', url='https://eur-lex.europa.eu/x', source='eur-lex')
    ref = boe_mod._reference(
        'artículo 6 del RGPD', 0, 5, 'eu', 'resolved-eurlex', norm=norm, unit_text='artículo 6'
    )
    ref.unit_blocks = [
        BOEUnitBlock(unit='artículo 6', block_id='art_6', title='Artículo 6', url='https://x', text='Texto art'),
        BOEUnitBlock(unit='artículo 6', block_id='art_7', title='Artículo 7', url='https://x', text=None),
    ]
    output = boe_mod._output('texto', [ref])
    output.warnings = []
    html_out = boe_mod.boe_report_to_html(output)
    assert 'Texto art' in html_out  # 1472-1474
    assert 'Artículo 7' not in html_out  # bloque sin texto se salta
    assert html_out.strip().endswith('</section>')  # 1537->1542


def test_boe_report_by_paragraph_empty_refs_and_no_warnings():
    output = boe_mod._output('Hola mundo sin referencias.', [])
    output.warnings = []
    markdown = boe_mod.boe_report_by_paragraph_markdown(output)  # 1558->1572, 1573->1576
    assert 'Hola mundo sin referencias.' in markdown
    assert 'Aviso BOE' not in markdown


def test_boe_paragraph_spans_ignores_empty_paragraphs():
    spans = boe_mod._paragraph_spans('\n\nHola\n\n')  # 1584->1586, 1588->1590
    assert len(spans) == 1
    assert spans[0][2] == 'Hola'


# ============================================================================
# cli.py
# ============================================================================

def test_cli_audit_to_markdown_without_unknown_or_omitted():
    report = auditar_texto('La AEAT informa')  # sin desconocidas ni omitidas
    markdown = cli._audit_to_markdown(report)  # 97->102, 102->110
    assert '## Glosario' in markdown
    assert '## Desconocidas' not in markdown
    assert '## Omitidas' not in markdown


def test_cli_run_benchmark_reads_input_file(tmp_path, capsys):
    source = tmp_path / 'entrada.txt'
    source.write_text('La AEAT gestiona el IVA.', encoding='utf-8')
    exit_code = cli.main(['benchmark', str(source), '--iterations', '1'])  # 276
    assert exit_code == 0
    assert capsys.readouterr().out.strip() != ''


def test_cli_main_reports_error_on_exception(tmp_path, capsys):
    missing = tmp_path / 'no_existe.txt'
    exit_code = cli.main(['expand', str(missing)])  # 338-340
    assert exit_code == 1
    assert 'legal-expand: error' in capsys.readouterr().err


def test_cli_main_prints_help_when_no_runner(monkeypatch, capsys):
    # Sin runner registrado para el comando, main imprime la ayuda y devuelve 0.
    monkeypatch.setattr(cli, 'COMMAND_RUNNERS', {})
    exit_code = cli.main(['info'])  # 342-343
    assert exit_code == 0
    assert capsys.readouterr().out != ''
