"""
Pruebas de CLI, documentos y normalizador orientadas a flujos reales.
"""

import io
import json

from legal_expand import ExpansionOptions, expandir_documento, procesar_archivo, procesar_directorio
from legal_expand.cli import main as cli_main
from legal_expand.core.normalizer import (
    SpecialContextOptions,
    is_in_special_context,
    is_inside_url,
    is_word_boundary,
)
from legal_expand.formatters import FormatterFactory
from legal_expand.formatters.base import Formatter
from legal_expand.types import BatchResult, MatchInfo


def test_cli_default_stdin_diagnostics_structured_and_output_file(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr('sys.stdin', io.StringIO('AEAT'))
    assert cli_main([]) == 0
    assert 'Agencia Estatal de Administración Tributaria' in capsys.readouterr().out

    input_file = tmp_path / 'doc.txt'
    input_file.write_text('AEAT e IVA. XYZ queda desconocida.', encoding='utf-8')

    assert cli_main(['expand', str(input_file), '--diagnostics']) == 0
    diagnostics = json.loads(capsys.readouterr().out)
    assert diagnostics['stats']['total_expanded'] >= 2

    assert cli_main(['expand', str(input_file), '--format', 'structured']) == 0
    structured = json.loads(capsys.readouterr().out)
    assert structured['original_text'].startswith('AEAT')

    audit_file = tmp_path / 'nested' / 'audit.md'
    assert cli_main([
        'audit',
        str(input_file),
        '--report-format',
        'markdown',
        '--include',
        'AEAT',
        '-o',
        str(audit_file),
    ]) == 0
    audit_markdown = audit_file.read_text(encoding='utf-8')
    assert '## Desconocidas' in audit_markdown
    assert '## Omitidas' in audit_markdown


def test_cli_expand_file_branch_batch_benchmark_boe_and_error(monkeypatch, capsys, tmp_path):
    input_file = tmp_path / 'doc.txt'
    input_file.write_text('AEAT y BOE', encoding='utf-8')
    output_file = tmp_path / 'out' / 'doc.txt'

    assert cli_main(['expand', str(input_file), '-o', str(output_file), '--format', 'plain']) == 0
    assert 'Agencia Estatal de Administración Tributaria' in output_file.read_text(encoding='utf-8')

    monkeypatch.setattr(
        'legal_expand.cli.procesar_directorio',
        lambda input_dir, output_dir, options, document_format, encoding: [
            BatchResult('ok.txt', 'out/ok.txt', True),
            BatchResult('bad.txt', 'out/bad.txt', False, 'permiso denegado'),
        ],
    )
    assert cli_main(['batch', str(tmp_path), str(tmp_path / 'batch-out')]) == 1
    batch_output = capsys.readouterr().out
    assert 'OK ok.txt -> out/ok.txt' in batch_output
    assert 'ERROR: permiso denegado bad.txt -> out/bad.txt' in batch_output

    assert cli_main(['benchmark']) == 0
    assert '"iterations"' in capsys.readouterr().out

    assert cli_main(['boe', str(input_file)]) == 0
    assert '# legal-expand BOE' in capsys.readouterr().out

    monkeypatch.setitem(
        __import__('legal_expand.cli').cli.COMMAND_RUNNERS,
        'info',
        lambda args: (_ for _ in ()).throw(RuntimeError('fallo controlado')),
    )
    assert cli_main(['info']) == 1
    assert 'fallo controlado' in capsys.readouterr().err


def test_cli_structured_fallback_when_formatter_returns_plain_text(monkeypatch, capsys, tmp_path):
    input_file = tmp_path / 'doc.txt'
    input_file.write_text('AEAT', encoding='utf-8')
    monkeypatch.setattr('legal_expand.cli.expandir_siglas', lambda text, options: 'texto plano')

    assert cli_main(['expand', str(input_file), '--format', 'structured']) == 0
    assert capsys.readouterr().out == 'texto plano\n'


def test_document_auto_formats_html_tokens_and_batch_skips_unsupported(tmp_path):
    html = '<!DOCTYPE html><?legal ok?><p>AEAT&nbsp;&#169;<br/></p><!--fin-->'
    expanded_html = expandir_documento(html, ExpansionOptions(format='html'), 'html')

    assert '<!DOCTYPE html>' in expanded_html
    assert '<?legal ok?>' in expanded_html
    assert '&nbsp;' in expanded_html
    assert '&#169;' in expanded_html
    assert '<br/>' in expanded_html
    assert '<!--fin-->' in expanded_html
    assert '<abbr title="Agencia Estatal de Administración Tributaria">AEAT</abbr>' in expanded_html

    markdown = tmp_path / 'doc.md'
    markdown.write_text('AEAT', encoding='utf-8')
    assert 'Agencia Estatal de Administración Tributaria' in procesar_archivo(str(markdown))

    forced_text = tmp_path / 'doc.custom'
    forced_text.write_text('BOE', encoding='utf-8')
    assert 'Boletín Oficial del Estado' in procesar_archivo(str(forced_text), document_format='text')

    source = tmp_path / 'in'
    target = tmp_path / 'out'
    (source / 'nested').mkdir(parents=True)
    (source / 'nested' / 'keep.html').write_text('<p>AEAT</p>', encoding='utf-8')
    (source / 'skip.bin').write_bytes(b'AEAT')

    results = procesar_directorio(str(source), str(target))

    assert len(results) == 1
    assert results[0].processed is True
    assert (target / 'nested' / 'keep.html').exists()
    assert not (target / 'skip.bin').exists()


def test_normalizer_boundaries_urls_and_disabled_context_options():
    assert is_word_boundary('AEAT', 0, 'before') is True
    assert is_word_boundary('xAEAT', 1, 'before') is False
    assert is_word_boundary('AEAT', 4, 'after') is True
    assert is_word_boundary('AEATx', 4, 'after') is False

    www_text = 'Consulta www.boe.es para normativa'
    start = www_text.index('boe')
    assert is_inside_url(www_text, start, start + 3) is True

    domain_text = 'Consulta portal.xaeat.es/tramites ahora'
    start = domain_text.index('aeat')
    assert is_inside_url(domain_text, start, start + 4) is True

    text = 'https://aeat.es y `BOE`'
    aeat_start = text.index('aeat')
    boe_start = text.index('BOE')
    assert is_in_special_context(text, aeat_start, aeat_start + 4) == 'url'
    assert is_in_special_context(
        text,
        aeat_start,
        aeat_start + 4,
        SpecialContextOptions(skip_urls=False),
    ) is None
    assert is_in_special_context(text, boe_start, boe_start + 3) == 'inline-code'


def test_formatter_base_contract_and_html_empty_matches():
    class CallsBaseFormatter(Formatter):
        def format(self, original_text, matches):
            return super().format(original_text, matches)

    assert CallsBaseFormatter().format('sin cambios', []) is None

    html_formatter = FormatterFactory.get_formatter('html')
    assert html_formatter.format('Texto sin siglas', []) == 'Texto sin siglas'

    match = MatchInfo(
        original='AEAT',
        expansion='Agencia Estatal',
        start_pos=0,
        end_pos=4,
        confidence=1.0,
        has_multiple_meanings=False,
    )
    assert '<abbr title="Agencia Estatal">AEAT</abbr>' in html_formatter.format('AEAT', [match])
