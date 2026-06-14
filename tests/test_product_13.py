"""
Tests de funcionalidades de producto añadidas en 1.3.0.
"""

import json

from legal_expand import (
    ExpansionOptions,
    auditar_texto,
    exportar_glosario,
    extraer_siglas,
    expandir_documento,
    expandir_siglas,
    generar_glosario,
    obtener_info_diccionario,
    procesar_directorio,
)
from legal_expand.cli import main as cli_main


def test_structured_output_to_dict_and_json():
    resultado = expandir_siglas('AEAT y BOE', ExpansionOptions(format='structured'))

    data = resultado.to_dict()
    assert data['stats']['total_expanded'] == 2

    parsed = json.loads(resultado.to_json())
    assert parsed['acronyms'][0]['acronym'] == 'AEAT'


def test_extraer_siglas_con_desconocidas_y_repetidas():
    resultado = extraer_siglas('AEAT y XYZ. AEAT repite.')
    acronyms = {item.acronym: item for item in resultado.acronyms}

    assert acronyms['AEAT'].known is True
    assert acronyms['AEAT'].repeated is True
    assert acronyms['XYZ'].known is False
    assert acronyms['XYZ'].omitted_reason == 'not-found'


def test_glosario_markdown_csv_json():
    texto = 'AEAT y BOE. AEAT otra vez.'
    glosario = generar_glosario(texto)
    assert len(glosario) == 2
    assert glosario[0].count == 2

    markdown = exportar_glosario(texto, 'markdown')
    assert '| AEAT | Agencia Estatal de Administración Tributaria | 2 |' in markdown

    csv_output = exportar_glosario(texto, 'csv')
    assert 'acronym,expansion,count' in csv_output

    json_output = json.loads(exportar_glosario(texto, 'json'))
    assert json_output[0]['acronym'] == 'AEAT'


def test_auditar_texto_resume_conocidas_desconocidas_y_glosario():
    report = auditar_texto('AEAT y XYZ. Visita https://boe.es y BOE')

    assert report.stats.total_known >= 2
    assert report.stats.total_unknown == 1
    assert report.unknown_acronyms[0].acronym == 'XYZ'
    assert any(item.acronym == 'AEAT' for item in report.glossary)


def test_diccionario_personalizado_json(tmp_path):
    custom = tmp_path / 'custom.json'
    custom.write_text(json.dumps([
        {
            'acronym': 'LXP',
            'expansion': 'Legal Expand Personalizado',
            'variants': ['LXP'],
            'source': 'test'
        }
    ]), encoding='utf-8')

    opciones = ExpansionOptions(custom_dictionaries=[str(custom)])
    resultado = expandir_siglas('Usa LXP', opciones)
    assert 'Legal Expand Personalizado' in resultado

    info = obtener_info_diccionario([str(custom)])
    assert str(custom) in info.custom_dictionaries
    assert 'test' in info.sources


def test_diccionario_personalizado_csv(tmp_path):
    custom = tmp_path / 'custom.csv'
    custom.write_text(
        'acronym,expansion,variants,source\n'
        'CSVX,Entrada CSV,CSVX,csv-test\n',
        encoding='utf-8'
    )

    opciones = ExpansionOptions(custom_dictionaries=[str(custom)])
    resultado = expandir_siglas('Usa CSVX', opciones)

    assert 'Entrada CSV' in resultado


def test_resuelve_diccionario_personalizado_por_contexto(tmp_path):
    custom = tmp_path / 'custom.json'
    custom.write_text(json.dumps([
        {
            'acronym': 'ABC',
            'expansion': 'Autoridad Bancaria Contextual',
            'keywords': ['banco', 'bancaria'],
            'priority': 100
        },
        {
            'acronym': 'ABC',
            'expansion': 'Asociación Base Civil',
            'keywords': ['asociación'],
            'priority': 100
        }
    ]), encoding='utf-8')

    opciones = ExpansionOptions(
        auto_resolve_duplicates=True,
        custom_dictionaries=[str(custom)]
    )
    resultado = expandir_siglas('El banco consulta a ABC', opciones)

    assert 'Autoridad Bancaria Contextual' in resultado


def test_expandir_documento_html_preserva_etiquetas():
    html = '<p>La AEAT notifica</p><a href="https://boe.es">BOE</a>'
    resultado = expandir_documento(html, ExpansionOptions(format='html'), 'html')

    assert '<p>' in resultado
    assert 'href="https://boe.es"' in resultado
    assert '<abbr title="Agencia Estatal de Administración Tributaria">AEAT</abbr>' in resultado


def test_procesar_directorio_batch(tmp_path):
    source = tmp_path / 'in'
    target = tmp_path / 'out'
    source.mkdir()
    (source / 'doc.txt').write_text('La AEAT', encoding='utf-8')

    results = procesar_directorio(str(source), str(target))

    assert results[0].processed is True
    assert 'Agencia Estatal de Administración Tributaria' in (target / 'doc.txt').read_text(encoding='utf-8')


def test_cli_expand_glossary_info_and_audit(capsys, tmp_path):
    input_file = tmp_path / 'doc.txt'
    input_file.write_text('AEAT y BOE', encoding='utf-8')

    assert cli_main(['expand', str(input_file), '--format', 'plain']) == 0
    expand_output = capsys.readouterr().out
    assert 'Agencia Estatal de Administración Tributaria' in expand_output

    assert cli_main([str(input_file), '--format', 'plain']) == 0
    shorthand_output = capsys.readouterr().out
    assert 'Boletín Oficial del Estado' in shorthand_output

    assert cli_main(['info']) == 0
    info_output = capsys.readouterr().out
    assert '"total_acronyms"' in info_output

    assert cli_main(['glossary', str(input_file), '--glossary-format', 'markdown']) == 0
    glossary_output = capsys.readouterr().out
    assert '| AEAT |' in glossary_output

    assert cli_main(['audit', str(input_file), '--report-format', 'json']) == 0
    audit_output = capsys.readouterr().out
    assert '"total_detected"' in audit_output
