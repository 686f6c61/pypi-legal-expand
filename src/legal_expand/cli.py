"""
CLI oficial de legal-expand.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .boe import boe_report_to_markdown, enriquecer_boe
from .core.engine import (
    auditar_texto,
    benchmark_texto,
    exportar_glosario,
    expandir_siglas,
    expandir_siglas_detallado,
    obtener_info_diccionario,
)
from .documents import expandir_documento, procesar_archivo, procesar_directorio
from .types import AuditReport, BOEOptions, ExpansionOptions, StructuredOutput


COMMANDS = {'expand', 'audit', 'glossary', 'batch', 'info', 'benchmark', 'boe'}
STDIN_INPUT_HELP = 'Archivo de entrada o - para stdin'


def _split_values(values: Optional[list[str]]) -> list[str]:
    result: list[str] = []
    for value in values or []:
        result.extend(item.strip() for item in value.split(',') if item.strip())
    return result


def _build_options(args: argparse.Namespace) -> ExpansionOptions:
    return ExpansionOptions(
        format=getattr(args, 'format', 'plain'),
        preserve_case=not getattr(args, 'canonical_case', False),
        auto_resolve_duplicates=getattr(args, 'auto_resolve_duplicates', False),
        expand_only_first=getattr(args, 'expand_only_first', False),
        exclude=_split_values(getattr(args, 'exclude', None)),
        include=(
            _split_values(getattr(args, 'include', None))
            if getattr(args, 'include', None)
            else None
        ),
        custom_dictionaries=getattr(args, 'dictionary', None) or []
    )


def _read_input(path: Optional[str], encoding: str = 'utf-8') -> str:
    if not path or path == '-':
        return sys.stdin.read()
    return Path(path).read_text(encoding=encoding)


def _write_output(text: str, output: Optional[str], encoding: str = 'utf-8') -> None:
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding=encoding)
    else:
        sys.stdout.write(text)
        if text and not text.endswith('\n'):
            sys.stdout.write('\n')


def _audit_to_markdown(report: AuditReport) -> str:
    lines = [
        '# legal-expand audit',
        '',
        f"- Detectadas: {report.stats.total_detected}",
        f"- Conocidas: {report.stats.total_known}",
        f"- Desconocidas: {report.stats.total_unknown}",
        f"- Expandidas: {report.stats.total_expanded}",
        f"- Omitidas: {report.stats.total_omitted}",
        f"- Repetidas: {report.stats.total_repeated}",
        '',
        '## Glosario',
        '',
        '| Sigla | Significado | Apariciones |',
        '| --- | --- | ---: |',
    ]
    for entry in report.glossary:
        lines.append(f"| {entry.acronym} | {entry.expansion} | {entry.count} |")

    if report.unknown_acronyms:
        lines.extend(['', '## Desconocidas', '', '| Sigla | Posición |', '| --- | ---: |'])
        for unknown_item in report.unknown_acronyms:
            lines.append(f"| {unknown_item.acronym} | {unknown_item.position.start} |")

    if report.omitted_acronyms:
        lines.extend(['', '## Omitidas', '', '| Sigla | Razón | Posición |', '| --- | --- | ---: |'])
        for omitted_item in report.omitted_acronyms:
            lines.append(
                f"| {omitted_item.acronym} | {omitted_item.reason} | "
                f"{omitted_item.position.start} |"
            )

    return '\n'.join(lines)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--format', choices=['plain', 'html', 'structured'], default='plain')
    parser.add_argument('--expand-only-first', action='store_true')
    parser.add_argument('--canonical-case', action='store_true', help='Usa siglas canónicas en la salida')
    parser.add_argument('--auto-resolve-duplicates', action='store_true')
    parser.add_argument('--include', action='append', help='Lista separada por comas; se puede repetir')
    parser.add_argument('--exclude', action='append', help='Lista separada por comas; se puede repetir')
    parser.add_argument('--dictionary', action='append', help='Diccionario personalizado JSON o CSV')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='legal-expand',
        description='Expande y audita siglas legales españolas.'
    )
    subparsers = parser.add_subparsers(dest='command')

    expand = subparsers.add_parser('expand', help='Expande un archivo o stdin')
    expand.add_argument('input', nargs='?', help=STDIN_INPUT_HELP)
    expand.add_argument('-o', '--output')
    expand.add_argument('--diagnostics', action='store_true')
    expand.add_argument('--document-format', choices=['auto', 'text', 'markdown', 'html'], default='auto')
    expand.add_argument('--encoding', default='utf-8')
    _add_common_options(expand)

    audit = subparsers.add_parser('audit', help='Audita sin modificar el texto')
    audit.add_argument('input', nargs='?', help=STDIN_INPUT_HELP)
    audit.add_argument('-o', '--output')
    audit.add_argument('--report-format', choices=['json', 'markdown'], default='json')
    audit.add_argument('--encoding', default='utf-8')
    _add_common_options(audit)

    glossary = subparsers.add_parser('glossary', help='Exporta glosario único')
    glossary.add_argument('input', nargs='?', help=STDIN_INPUT_HELP)
    glossary.add_argument('-o', '--output')
    glossary.add_argument('--glossary-format', choices=['json', 'csv', 'markdown'], default='markdown')
    glossary.add_argument('--encoding', default='utf-8')
    _add_common_options(glossary)

    batch = subparsers.add_parser('batch', help='Procesa una carpeta recursivamente')
    batch.add_argument('input_dir')
    batch.add_argument('output_dir')
    batch.add_argument('--document-format', choices=['auto', 'text', 'markdown', 'html'], default='auto')
    batch.add_argument('--encoding', default='utf-8')
    _add_common_options(batch)

    info = subparsers.add_parser('info', help='Muestra metadata del diccionario')
    info.add_argument('--dictionary', action='append', help='Diccionario personalizado JSON o CSV')

    benchmark = subparsers.add_parser('benchmark', help='Mide rendimiento')
    benchmark.add_argument('input', nargs='?', help=STDIN_INPUT_HELP)
    benchmark.add_argument('--iterations', type=int, default=100)
    benchmark.add_argument('--encoding', default='utf-8')
    _add_common_options(benchmark)

    boe = subparsers.add_parser('boe', help='Detecta y enlaza referencias BOE')
    boe.add_argument('input', nargs='?', help=STDIN_INPUT_HELP)
    boe.add_argument('-o', '--output')
    boe.add_argument('--report-format', choices=['json', 'markdown'], default='markdown')
    boe.add_argument('--mode', choices=['offline', 'cache-first', 'online'], default='offline')
    boe.add_argument('--timeout', type=float, default=4.0)
    boe.add_argument('--max-results', type=int, default=5)
    boe.add_argument('--overrides', help='JSON con aliases y referencias manuales')
    boe.add_argument('--cache-path', help='Carpeta de caché para respuestas BOE')
    boe.add_argument('--no-curated-aliases', action='store_true')
    boe.add_argument('--no-infer-single-active-norm', action='store_true')
    boe.add_argument('--no-unit-text', action='store_true')
    boe.add_argument('--encoding', default='utf-8')

    return parser


def _run_expand(args: argparse.Namespace) -> None:
    options = _build_options(args)
    if args.diagnostics:
        text = _read_input(args.input, args.encoding)
        result = expandir_siglas_detallado(text, options)
        _write_output(result.to_json(indent=2), args.output, args.encoding)
        return

    if args.input and args.input != '-' and args.output and args.format != 'structured':
        procesar_archivo(
            args.input,
            args.output,
            options,
            args.document_format,
            args.encoding
        )
        return

    text = _read_input(args.input, args.encoding)
    if args.format == 'structured':
        structured_result = expandir_siglas(text, options)
        if isinstance(structured_result, StructuredOutput):
            _write_output(structured_result.to_json(indent=2), args.output, args.encoding)
        else:
            _write_output(structured_result, args.output, args.encoding)
        return

    expanded = expandir_documento(text, options, args.document_format)
    _write_output(expanded, args.output, args.encoding)


def run_expand(args: argparse.Namespace) -> int:
    _run_expand(args)
    return 0


def run_audit(args: argparse.Namespace) -> int:
    options = _build_options(args)
    text = _read_input(args.input, args.encoding)
    report = auditar_texto(text, options)
    output = report.to_json(indent=2) if args.report_format == 'json' else _audit_to_markdown(report)
    _write_output(output, args.output, args.encoding)
    return 0


def run_glossary(args: argparse.Namespace) -> int:
    options = _build_options(args)
    text = _read_input(args.input, args.encoding)
    output = exportar_glosario(text, args.glossary_format, options)
    _write_output(output, args.output, args.encoding)
    return 0


def run_batch(args: argparse.Namespace) -> int:
    options = _build_options(args)
    results = procesar_directorio(
        args.input_dir,
        args.output_dir,
        options,
        args.document_format,
        args.encoding
    )
    failed = [result for result in results if not result.processed]
    for result in results:
        status = 'OK' if result.processed else f"ERROR: {result.error}"
        sys.stdout.write(f"{status} {result.input_path} -> {result.output_path}\n")
    return 1 if failed else 0


def run_info(args: argparse.Namespace) -> int:
    from . import __version__

    info = obtener_info_diccionario(args.dictionary or [])
    data = info.to_dict()
    data['package_version'] = __version__
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return 0


def run_benchmark(args: argparse.Namespace) -> int:
    options = _build_options(args)
    if args.input:
        text = _read_input(args.input, args.encoding)
    else:
        text = 'La AEAT gestiona el IVA según el BOE y el art. 123 del CC.'
    result = benchmark_texto(text, options, args.iterations)
    sys.stdout.write(result.to_json(indent=2) + '\n')
    return 0


def run_boe(args: argparse.Namespace) -> int:
    text = _read_input(args.input, args.encoding)
    options = BOEOptions(
        mode=args.mode,
        timeout_seconds=args.timeout,
        max_results=args.max_results,
        include_unit_text=not args.no_unit_text,
        infer_single_active_norm=not args.no_infer_single_active_norm,
        use_curated_aliases=not args.no_curated_aliases,
        cache_path=args.cache_path,
        overrides_path=args.overrides,
    )
    result = enriquecer_boe(text, options)
    output = (
        result.to_json(indent=2)
        if args.report_format == 'json'
        else boe_report_to_markdown(result)
    )
    _write_output(output, args.output, args.encoding)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        args_list = ['expand', '-']
    elif args_list[0] not in COMMANDS and args_list[0] not in {'-h', '--help'}:
        args_list.insert(0, 'expand')

    parser = build_parser()
    args = parser.parse_args(args_list)

    try:
        if args.command == 'expand':
            return run_expand(args)
        if args.command == 'audit':
            return run_audit(args)
        if args.command == 'glossary':
            return run_glossary(args)
        if args.command == 'batch':
            return run_batch(args)
        if args.command == 'info':
            return run_info(args)
        if args.command == 'benchmark':
            return run_benchmark(args)
        if args.command == 'boe':
            return run_boe(args)
    except Exception as exc:
        sys.stderr.write(f"legal-expand: error: {exc}\n")
        return 1

    parser.print_help()
    return 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
