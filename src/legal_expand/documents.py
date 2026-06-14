"""
Procesamiento de documentos y lotes para legal-expand.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

from .core.engine import expandir_siglas
from .types import BatchResult, ExpansionOptions, StructuredOutput


SUPPORTED_EXTENSIONS = {'.txt', '.md', '.markdown', '.html', '.htm'}


def _detect_document_format(path: Optional[Path], document_format: str) -> str:
    if document_format != 'auto':
        return document_format

    if path and path.suffix.lower() in {'.html', '.htm'}:
        return 'html'
    if path and path.suffix.lower() in {'.md', '.markdown'}:
        return 'markdown'
    return 'text'


class _HtmlExpansionParser(HTMLParser):
    def __init__(self, opciones: Optional[ExpansionOptions]):
        super().__init__(convert_charrefs=False)
        self.opciones = opciones
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self.parts.append(self.get_starttag_text() or f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self.parts.append(self.get_starttag_text() or f"<{tag} />")

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        expanded = expandir_siglas(data, self.opciones)
        if isinstance(expanded, StructuredOutput):
            self.parts.append(expanded.expanded_text)
        else:
            self.parts.append(expanded)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")

    def output(self) -> str:
        return ''.join(self.parts)


def expandir_documento(
    texto: str,
    opciones: Optional[ExpansionOptions] = None,
    document_format: str = 'text'
) -> str:
    """
    Expande siglas preservando formato básico de txt, markdown o html.
    """
    normalized_format = document_format.lower()
    if normalized_format == 'html':
        parser = _HtmlExpansionParser(opciones)
        parser.feed(texto)
        parser.close()
        return parser.output()

    expanded = expandir_siglas(texto, opciones)
    if isinstance(expanded, StructuredOutput):
        return expanded.expanded_text
    return expanded


def procesar_archivo(
    input_path: str,
    output_path: Optional[str] = None,
    opciones: Optional[ExpansionOptions] = None,
    document_format: str = 'auto',
    encoding: str = 'utf-8'
) -> str:
    """
    Procesa un archivo y opcionalmente escribe el resultado.
    """
    source = Path(input_path)
    detected_format = _detect_document_format(source, document_format)
    text = source.read_text(encoding=encoding)
    expanded = expandir_documento(text, opciones, detected_format)

    if output_path:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expanded, encoding=encoding)

    return expanded


def procesar_directorio(
    input_dir: str,
    output_dir: str,
    opciones: Optional[ExpansionOptions] = None,
    document_format: str = 'auto',
    encoding: str = 'utf-8'
) -> list[BatchResult]:
    """
    Procesa recursivamente .txt, .md y .html manteniendo rutas relativas.
    """
    source_root = Path(input_dir)
    target_root = Path(output_dir)
    results: list[BatchResult] = []

    for source in sorted(source_root.rglob('*')):
        if not source.is_file() or source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        target = target_root / source.relative_to(source_root)
        try:
            procesar_archivo(
                str(source),
                str(target),
                opciones,
                document_format,
                encoding
            )
            results.append(BatchResult(
                input_path=str(source),
                output_path=str(target),
                processed=True
            ))
        except Exception as exc:  # pragma: no cover - defensive batch reporting
            results.append(BatchResult(
                input_path=str(source),
                output_path=str(target),
                processed=False,
                error=str(exc)
            ))

    return results
