"""
Cobertura de cliente BOE, parsers y ramas defensivas deterministas.
"""

import json
import time
from pathlib import Path

import pytest

from legal_expand import BOENorm, BOEOptions, detectar_referencias_boe, enriquecer_boe
from legal_expand.boe import (
    BOEClient,
    BOENetworkError,
    _find_index_block,
    _parse_index,
    _parse_norms,
    _plain_text,
)


class _FakeHTTPResponse:
    def __init__(self, body: str):
        self.body = body.encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


def test_boe_client_cache_and_offline_mode(tmp_path):
    options = BOEOptions(mode='offline', cache_path=str(tmp_path), cache_ttl_days=1)
    client = BOEClient(options)
    path = '/datosabiertos/api/legislacion-consolidada?query=Ley'

    assert client._read_cache(path) is None
    client._write_cache(path, '{"ok": true}')
    assert client._read_cache(path) == '{"ok": true}'
    assert client._get(path) == '{"ok": true}'

    malformed_cache = tmp_path / client._cache_key('/malformed')
    malformed_cache.write_text('{bad json', encoding='utf-8')
    assert client._read_cache('/malformed') is None

    stale_cache = tmp_path / client._cache_key('/stale')
    stale_cache.write_text(
        json.dumps({'timestamp': time.time() - 99_999_999, 'body': 'old'}),
        encoding='utf-8',
    )
    assert client._read_cache('/stale') is None

    non_string_cache = tmp_path / client._cache_key('/non-string')
    non_string_cache.write_text(
        json.dumps({'timestamp': time.time(), 'body': {'unexpected': True}}),
        encoding='utf-8',
    )
    assert client._read_cache('/non-string') is None

    default_client = BOEClient(BOEOptions())
    assert default_client._cache_dir().as_posix().endswith('/.cache/legal-expand/boe')

    with pytest.raises(BOENetworkError, match='boe-offline-mode'):
        client._get('/missing')


def test_boe_client_get_fetches_and_caches_without_real_network(monkeypatch, tmp_path):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, timeout, request.headers.get('User-agent')))
        return _FakeHTTPResponse('{"fixture": true}')

    monkeypatch.setattr('legal_expand.boe.urllib.request.urlopen', fake_urlopen)
    client = BOEClient(BOEOptions(mode='online', cache_path=str(tmp_path), timeout_seconds=1.5))

    body = client._get('/datosabiertos/api/legislacion-consolidada?query=Ley&limit=5')

    assert body == '{"fixture": true}'
    assert calls == [(
        'https://www.boe.es/datosabiertos/api/legislacion-consolidada?query=Ley&limit=5',
        1.5,
        'legal-expand/1.5 (+https://github.com/686f6c61/pypi-legal-expand)',
    )]
    assert client._get('/datosabiertos/api/legislacion-consolidada?query=Ley&limit=5') == body
    assert len(calls) == 1


def test_boe_client_search_resolve_index_and_unit_blocks(monkeypatch, tmp_path):
    client = BOEClient(BOEOptions(mode='online', cache_path=str(tmp_path)))

    def fake_get(path):
        if path.startswith('/datosabiertos/api/legislacion-consolidada?'):
            return json.dumps({
                'items': [
                    {
                        'identificador': 'BOE-A-2099-1',
                        'titulo': 'Ley 99/2099, de pruebas',
                        'url_html_consolidada': 'https://www.boe.es/fixture',
                        'numero_oficial': '99/2099',
                        'rango': 'Ley',
                    },
                    {'identificador': 'BOE-A-2099-1', 'titulo': 'Duplicada'},
                ]
            })
        if path.endswith('/texto/indice'):
            return json.dumps({
                'bloques': [
                    {'id_bloque': 'a1', 'titulo': 'Artículo 1. Objeto'},
                    {'titulo': 'Artículo 2. Sin identificador'},
                    {'id': '', 'title': 'Artículo 3. Vacío'},
                ]
            })
        if path.endswith('/texto/bloque/a1'):
            return json.dumps({'bloque': {'texto': [' Artículo 1. ', 'Objeto. ']}})
        raise AssertionError(path)

    monkeypatch.setattr(client, '_get', fake_get)

    norms = client.search('Ley 99/2099')
    assert len(norms) == 1
    assert norms[0].official_number == '99/2099'
    assert client.resolve_norm('Ley 99/2099')[0].boe_id == 'BOE-A-2099-1'

    index = client.get_index('BOE-A-2099-1')
    assert index[0] == {'id': 'a1', 'title': 'Artículo 1. Objeto'}
    assert client.get_block_text('BOE-A-2099-1', 'a1') == 'Artículo 1. Objeto.'

    blocks = client.find_unit_blocks('BOE-A-2099-1', 'arts. 1 y 2')
    assert len(blocks) == 1
    assert blocks[0].block_id == 'a1'
    assert blocks[0].text == 'Artículo 1. Objeto.'


def test_boe_client_resolve_norm_keeps_ambiguous_candidates(monkeypatch, tmp_path):
    client = BOEClient(BOEOptions(mode='online', cache_path=str(tmp_path)))
    candidates = [
        BOENorm('BOE-A-2099-1', 'Ley candidata A', 'https://www.boe.es/a', official_number='1/2099'),
        BOENorm('BOE-A-2099-2', 'Ley candidata B', 'https://www.boe.es/b', official_number='2/2099'),
    ]
    monkeypatch.setattr(client, 'search', lambda query: candidates)

    norm, returned_candidates = client.resolve_norm('Ley autonómica 3/2099')

    assert norm is None
    assert returned_candidates == candidates


def test_boe_parsers_handle_json_xml_and_malformed_payloads():
    json_norms = json.dumps({
        'resultados': [
            {
                'identificador': 'BOE-A-2099-7',
                'titulo': 'Ley 7/2099',
                'url': 'https://www.boe.es/ley-7',
                'numero_oficial': '7/2099',
                'rango': 'Ley',
            },
            {'id': 'NO-BOE'},
            {'identificador': 'BOE-A-2099-7', 'titulo': 'Duplicada'},
        ]
    })
    norms = _parse_norms(json_norms)
    assert len(norms) == 1
    assert norms[0].rank == 'Ley'

    xml_norms = """
    <respuesta>
      <item>
        <identificador>BOE-A-2099-8</identificador>
        <titulo>Ley 8/2099</titulo>
        <url_html_consolidada>https://www.boe.es/ley-8</url_html_consolidada>
        <numero_oficial>8/2099</numero_oficial>
      </item>
    </respuesta>
    """
    assert _parse_norms(xml_norms)[0].boe_id == 'BOE-A-2099-8'
    assert _parse_norms('<xml roto') == []

    xml_index = """
    <indice>
      <bloque id="a1" titulo="Artículo 1. Objeto" />
      <bloque id_bloque="a2"><titulo>Artículo 2. Ámbito</titulo></bloque>
      <bloque titulo="Sin id" />
    </indice>
    """
    assert _parse_index(xml_index) == [
        {'id': 'a1', 'title': 'Artículo 1. Objeto'},
        {'id': 'a2', 'title': 'Artículo 2. Ámbito'},
    ]
    assert _parse_index('<indice roto') == []
    assert _plain_text(json.dumps({'bloque': {'texto': [' Uno ', 'Dos']}})) == 'Uno Dos'
    assert _plain_text('{json roto') == ''
    assert _plain_text('<root><p>Uno </p><p>Dos</p></root>') == 'Uno Dos'
    assert _plain_text('texto   plano') == 'texto plano'
    assert _find_index_block([{'title': 'Artículo 9. Sin id'}], 'artículo 10') is None


def test_boe_overrides_aliases_invalidos_y_manual_protegido(tmp_path):
    overrides_path = tmp_path / 'overrides.json'
    overrides_path.write_text(
        json.dumps({
            'aliases': {'LEY 99/2099': 'BOE-A-2099-99'},
            'references': 'no-list',
        }),
        encoding='utf-8',
    )

    manual = detectar_referencias_boe(
        'El art. 1 de la Ley 99/2099 se cita.',
        BOEOptions(use_curated_aliases=False, overrides_path=str(overrides_path)),
    )
    assert manual.references[0].status == 'manual'
    assert manual.references[0].reason == 'manual-alias-override'
    assert manual.references[0].norm.boe_id == 'BOE-A-2099-99'

    no_curated = detectar_referencias_boe(
        'La Ley 39/2015 se cita sin aliases curados.',
        BOEOptions(use_curated_aliases=False),
        overrides={'aliases': []},
    )
    assert no_curated.references[0].status == 'needs-boe-search'

    invalid_alias = detectar_referencias_boe(
        'La Ley 99/2099 vuelve a citarse.',
        BOEOptions(use_curated_aliases=False),
        overrides={'aliases': {' ley 99/2099 ': {'title': 'Sin BOE'}}},
    )
    assert invalid_alias.references[0].status == 'needs-boe-search'

    protected_manual = detectar_referencias_boe(
        '`referencia manual` y texto ordinario.',
        overrides={
            'references': [
                {'text': 123, 'boe_id': 'BOE-A-2099-1'},
                {'text': 'referencia manual'},
                {'text': 'referencia manual', 'boe_id': 'BOE-A-2099-1'},
            ]
        },
    )
    assert protected_manual.references == []


class _NetworkFailClient:
    def resolve_norm(self, norm_text):
        raise BOENetworkError('timeout fixture')


class _ResolvingClient:
    def resolve_norm(self, norm_text):
        return BOENorm('BOE-A-2099-12', 'Ley 12/2099', 'https://www.boe.es/ley-12', source='fixture'), []

    def find_unit_blocks(self, boe_id, unit_text):
        return []


def test_boe_online_network_error_and_successful_lookup_paths():
    network_error = enriquecer_boe(
        'La Ley 99/2099 debe consultarse.',
        BOEOptions(mode='online', use_curated_aliases=False),
        client=_NetworkFailClient(),
    )
    assert network_error.references[0].status == 'network-error'
    assert network_error.references[0].reason == 'timeout fixture'

    resolved = enriquecer_boe(
        'La Ley 99/2099 debe consultarse.',
        BOEOptions(mode='online', use_curated_aliases=False),
        client=_ResolvingClient(),
    )
    assert resolved.references[0].status == 'resolved-url-only'
    assert resolved.references[0].source == 'fixture'
    assert resolved.references[0].reason == 'boe-search-resolved-url-only'

    no_unit_fetch = enriquecer_boe(
        'El art. 1 de la Ley 39/2015 se cita.',
        BOEOptions(mode='online', include_unit_text=False),
        client=_ResolvingClient(),
    )
    assert no_unit_fetch.references[0].status == 'resolved-url-only'
    assert no_unit_fetch.references[0].unit_blocks == []
