"""
legal-expand - Motor de detección de siglas

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Contiene el DictionaryIndex y SiglasMatcher para detectar y validar
siglas legales en texto. Implementa el corazón del sistema de matching.

ARQUITECTURA:
El sistema de matching se compone de dos clases principales:
1. DictionaryIndex: Índices O(1) para búsqueda de siglas
2. SiglasMatcher: Motor de regex y validación de contexto

RESPONSABILIDADES:
- Cargar y indexar el diccionario de 646 siglas
- Compilar regex optimizada para detección
- Validar word boundaries y contextos especiales
- Manejar variantes de siglas (con/sin puntos)
- Resolver siglas con múltiples significados

ALGORITMO DE BÚSQUEDA (3 NIVELES):
1. Exact match: Case-sensitive, con puntos (AEAT, A.E.A.T.)
2. Flexible match: Sin puntos ni espacios (AEAT ↔ A.E.A.T)
3. Normalized match: Case-insensitive, sin puntos (aeat)

CARACTERÍSTICAS DE LA REGEX:
- Variantes ordenadas por longitud DESCENDENTE (crítico)
- Lookahead/lookbehind para word boundaries
- Soporte para caracteres españoles (áéíóúñÑüÜ)
- Compilación única al inicializar (Singleton)

INTEGRACIÓN CON OTROS MÓDULOS:
- normalizer: Funciones de normalización y escape
- types: DictionaryEntry, MatchInfo, etc.
- data/dictionary.json: Fuente de datos de siglas
"""

from __future__ import annotations

import csv
import json
import re
import threading
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..types import (
    AcronymSearchResult,
    DictionaryEntry,
    DictionaryInfo,
    DictionaryStats,
    InternalOptions,
    MatchInfo,
    MatchRunResult,
    MatchRunStats,
    OmittedAcronymReason,
    OmittedMatchInfo,
)
from .normalizer import (
    SpecialContextOptions,
    escape_regex,
    is_in_special_context,
    is_part_of_larger_word,
    normalize,
)


# ============================================================================
# ÍNDICE DEL DICCIONARIO
# ============================================================================

@dataclass(frozen=True)
class DictionaryIndexMetadata:
    conflicts: list[dict]
    version: str
    build_date: str
    custom_dictionaries: list[str]


class DictionaryIndex:
    """
    Índice del diccionario de siglas para búsquedas O(1).

    Mantiene tres índices:
    - exact_index: Variantes exactas → IDs (case-sensitive, con puntos)
    - normalized_index: Variantes normalizadas → IDs (lowercase, sin puntos)
    - entries_by_id: ID → DictionaryEntry

    Example:
        >>> index = DictionaryIndex(entries, raw_index)
        >>> entry = index.lookup("AEAT")
        >>> entry.significado
        'Agencia Estatal de Administración Tributaria'
    """

    def __init__(
        self,
        entries: list[DictionaryEntry],
        exact_index: dict[str, list[str]],
        normalized_index: dict[str, list[str]],
        metadata: Optional[DictionaryIndexMetadata] = None
    ):
        """
        Inicializa el índice con datos del diccionario.

        Args:
            entries: Lista de entradas del diccionario
            exact_index: Índice de variantes exactas
            normalized_index: Índice de variantes normalizadas
        """
        self.entries_by_id: dict[str, DictionaryEntry] = {e.id: e for e in entries}
        self.exact_index = exact_index
        self.normalized_index = normalized_index
        self._entries = entries
        metadata = metadata or DictionaryIndexMetadata([], 'unknown', 'unknown', [])
        self.version = metadata.version
        self.build_date = metadata.build_date
        self.custom_dictionaries = metadata.custom_dictionaries
        self.conflict_map = {
            conflict['sigla']: {
                'default_id': conflict['defaultId'],
                'variants': conflict['variants']
            }
            for conflict in metadata.conflicts
        }

    def lookup(
        self,
        sigla: str,
        case_sensitive: bool = True,
        context_text: Optional[str] = None
    ) -> Optional[DictionaryEntry]:
        """
        Busca una sigla en el diccionario usando búsqueda de 3 niveles.

        Niveles de búsqueda:
        1. Exact match (case-sensitive, con puntos)
        2. Flexible match (sin puntos ni espacios)
        3. Normalized match (case-insensitive, sin puntos)

        Args:
            sigla: Sigla a buscar
            case_sensitive: Si es True, solo busca con case-sensitive

        Returns:
            DictionaryEntry si se encuentra, None en caso contrario
        """
        # NIVEL 1: Exact match
        ids = self.exact_index.get(sigla)
        if ids:
            return self._resolve_ids(ids, sigla, context_text)

        # NIVEL 2: Flexible match (sin puntos ni espacios)
        flexible = re.sub(r'\s+', '', sigla.replace('.', ''))
        ids = self.exact_index.get(flexible)
        if ids:
            return self._resolve_ids(ids, sigla, context_text)

        # NIVEL 3: Normalized match (solo si no es case-sensitive)
        if not case_sensitive:
            normalized_sigla = normalize(sigla)
            ids = self.normalized_index.get(normalized_sigla)
            if ids:
                return self._resolve_ids(ids, sigla, context_text)

        return None

    def _entries_for_ids(self, ids: list[str]) -> list[DictionaryEntry]:
        entries: list[DictionaryEntry] = []
        for id_ in ids:
            entry = self.entries_by_id.get(id_)
            if entry is not None:
                entries.append(entry)
        return entries

    @staticmethod
    def _best_context_entry(
        entries: list[DictionaryEntry],
        context_text: Optional[str]
    ) -> Optional[DictionaryEntry]:
        if not context_text:
            return None

        context = context_text.lower()
        scored_entries: list[tuple[int, int, DictionaryEntry]] = []
        for entry in entries:
            score = sum(
                1
                for keyword in entry.context_keywords
                if keyword.lower() in context
            )
            scored_entries.append((score, entry.priority, entry))

        best_score, _, best_entry = max(scored_entries, key=lambda item: (item[0], item[1]))
        return best_entry if best_score > 0 else None

    def _conflict_default_entry(self, original_sigla: str) -> Optional[DictionaryEntry]:
        normalized_original = normalize(original_sigla)
        for conflict_sigla, resolution in self.conflict_map.items():
            if normalize(conflict_sigla) == normalized_original:
                return self.entries_by_id.get(resolution['default_id'])
        return None

    def _resolve_ids(
        self,
        ids: list[str],
        original_sigla: str,
        context_text: Optional[str] = None
    ) -> Optional[DictionaryEntry]:
        """
        Resuelve una lista de IDs a una entrada del diccionario.

        Si hay múltiples IDs (sigla con múltiples significados),
        retorna el de mayor prioridad.

        Args:
            ids: Lista de IDs de entradas
            original_sigla: Sigla original para contexto

        Returns:
            DictionaryEntry con mayor prioridad
        """
        if not ids:
            return None

        if len(ids) == 1:
            return self.entries_by_id.get(ids[0])

        entries = self._entries_for_ids(ids)

        if not entries:
            return None

        context_entry = self._best_context_entry(entries, context_text)
        if context_entry is not None:
            return context_entry

        conflict_entry = self._conflict_default_entry(original_sigla)
        if conflict_entry is not None:
            return conflict_entry

        # Fallback: retornar el de mayor prioridad
        return max(entries, key=lambda e: e.priority)

    def has_multiple_meanings(self, sigla: str) -> bool:
        """
        Verifica si una sigla tiene múltiples significados.

        Args:
            sigla: Sigla a verificar

        Returns:
            True si tiene múltiples significados
        """
        normalized_sigla = normalize(sigla)
        for conflict_sigla in self.conflict_map:
            if normalize(conflict_sigla) == normalized_sigla:
                return True

        ids = self.exact_index.get(sigla, [])
        if len(ids) > 1:
            return True

        ids = self.normalized_index.get(normalized_sigla, [])
        return len(ids) > 1

    def get_all_meanings(self, sigla: str) -> list[str]:
        """
        Obtiene todos los significados posibles de una sigla.

        Args:
            sigla: Sigla a buscar

        Returns:
            Lista de todos los significados posibles
        """
        normalized_sigla = normalize(sigla)
        for conflict_sigla, resolution in self.conflict_map.items():
            if normalize(conflict_sigla) == normalized_sigla:
                return [
                    variant['significado']
                    for variant in resolution['variants']
                    if variant.get('significado')
                ]

        ids = self.exact_index.get(sigla, [])
        if not ids:
            ids = self.normalized_index.get(normalized_sigla, [])

        meanings = []
        for id_ in ids:
            entry = self.entries_by_id.get(id_)
            if entry and entry.significado not in meanings:
                meanings.append(entry.significado)

        return meanings

    def get_all_entries(self) -> list[DictionaryEntry]:
        """Retorna todas las entradas del diccionario."""
        return self._entries

    def get_info(self) -> DictionaryInfo:
        """Retorna metadata del diccionario cargado."""
        stats_unique = {entry.original for entry in self._entries}
        sources = sorted({
            entry.source
            for entry in self._entries
            if entry.source
        })
        if not sources:
            sources = ['RAE', 'DPEJ', 'BOE', 'legislación vigente']

        return DictionaryInfo(
            dictionary_version=self.version,
            build_date=self.build_date,
            total_entries=len(self._entries),
            total_acronyms=len(stats_unique),
            total_variants=len(self.exact_index),
            conflicts=len(self.conflict_map),
            custom_dictionaries=list(self.custom_dictionaries),
            sources=sources
        )


# ============================================================================
# MATCHER DE SIGLAS (SINGLETON)
# ============================================================================

@dataclass(frozen=True)
class ResolvedExpansion:
    expansion: str
    has_multiple: bool
    all_meanings: Optional[list[str]]
    ambiguity_details: Optional[str]


class SiglasMatcher:
    """
    Motor de detección de siglas legales (Singleton thread-safe).

    Responsabilidades:
    - Compilar regex optimizada para detección de siglas
    - Buscar matches en texto respetando configuración
    - Validar contextos especiales (URLs, emails, código)
    - Manejar duplicados y resolución de conflictos

    Example:
        >>> matcher = SiglasMatcher.get_instance()
        >>> matches = matcher.find_matches("La AEAT notifica", options)
        >>> matches[0].expansion
        'Agencia Estatal de Administración Tributaria'
    """

    _instance: Optional[SiglasMatcher] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, custom_dictionaries: Optional[list[str]] = None) -> SiglasMatcher:
        """Implementación thread-safe del Singleton."""
        if custom_dictionaries:
            instance = super().__new__(cls)
            instance._initialize(custom_dictionaries)
            return instance

        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def __init__(self, custom_dictionaries: Optional[list[str]] = None) -> None:
        # La inicialización real ocurre en __new__ para preservar el singleton.
        pass

    def _initialize(self, custom_dictionaries: Optional[list[str]] = None) -> None:
        """Inicializa el matcher cargando el diccionario y compilando regex."""
        self._load_dictionary(custom_dictionaries)
        self._compile_pattern()

    def _load_dictionary(self, custom_dictionaries: Optional[list[str]] = None) -> None:
        """Carga el diccionario JSON y construye los índices."""
        # Cargar JSON desde el directorio data
        data_path = Path(__file__).parent.parent / 'data' / 'dictionary.json'

        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Construir entradas
        entries = [
            DictionaryEntry(
                id=e['id'],
                original=e['original'],
                significado=e['significado'],
                variants=e.get('variants', [e['original']]),
                priority=e.get('priority', 100),
                source=e.get('source'),
                context_keywords=e.get('context_keywords', [])
            )
            for e in data['entries']
        ]

        exact_index = deepcopy(data['index']['exact'])
        normalized_index = deepcopy(data['index']['normalized'])
        custom_paths = custom_dictionaries or []
        custom_entries = self._load_custom_entries(custom_paths)
        entries.extend(custom_entries)

        for entry in custom_entries:
            self._add_entry_to_indexes(entry, exact_index, normalized_index)

        # Construir índice
        self._index = DictionaryIndex(
            entries=entries,
            exact_index=exact_index,
            normalized_index=normalized_index,
            metadata=DictionaryIndexMetadata(
                conflicts=data.get('conflicts', []),
                version=data.get('version', 'unknown'),
                build_date=data.get('buildDate', 'unknown'),
                custom_dictionaries=custom_paths,
            ),
        )

    @staticmethod
    def _add_entry_to_indexes(
        entry: DictionaryEntry,
        exact_index: dict[str, list[str]],
        normalized_index: dict[str, list[str]]
    ) -> None:
        """Añade una entrada a los índices exacto y normalizado."""
        variants = [entry.original, *entry.variants]
        for variant in variants:
            exact_index.setdefault(variant, [])
            if entry.id not in exact_index[variant]:
                exact_index[variant].append(entry.id)

            normalized = normalize(variant)
            normalized_index.setdefault(normalized, [])
            if entry.id not in normalized_index[normalized]:
                normalized_index[normalized].append(entry.id)

    def _load_custom_entries(self, paths: list[str]) -> list[DictionaryEntry]:
        """Carga entradas personalizadas desde JSON o CSV."""
        entries: list[DictionaryEntry] = []
        for path_text in paths:
            path = Path(path_text)
            if not path.exists():
                raise FileNotFoundError(f"Custom dictionary not found: {path}")

            if path.suffix.lower() == '.json':
                entries.extend(self._load_custom_json(path))
            elif path.suffix.lower() == '.csv':
                entries.extend(self._load_custom_csv(path))
            else:
                raise ValueError(
                    f"Unsupported custom dictionary format: {path.suffix}. "
                    "Use .json or .csv."
                )

        return entries

    def _load_custom_json(self, path: Path) -> list[DictionaryEntry]:
        with open(path, 'r', encoding='utf-8') as f:
            payload = json.load(f)

        raw_entries = payload.get('entries', payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_entries, list):
            raise ValueError(f"Custom JSON dictionary must contain a list of entries: {path}")

        return [
            self._custom_entry_from_mapping(item, path, index)
            for index, item in enumerate(raw_entries, start=1)
        ]

    def _load_custom_csv(self, path: Path) -> list[DictionaryEntry]:
        with open(path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            return [
                self._custom_entry_from_mapping(row, path, index)
                for index, row in enumerate(reader, start=1)
            ]

    @staticmethod
    def _split_list_value(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if not text:
            return []
        return [
            item.strip()
            for item in re.split(r'[;,]', text)
            if item.strip()
        ]

    def _custom_entry_from_mapping(
        self,
        item: object,
        path: Path,
        index: int
    ) -> DictionaryEntry:
        if not isinstance(item, dict):
            raise ValueError(f"Custom dictionary entry #{index} is not an object: {path}")

        original = (
            item.get('original')
            or item.get('sigla')
            or item.get('acronym')
        )
        significado = (
            item.get('significado')
            or item.get('meaning')
            or item.get('expansion')
        )

        if not original or not significado:
            raise ValueError(
                f"Custom dictionary entry #{index} in {path} needs "
                "'original'/'sigla'/'acronym' and 'significado'/'expansion'."
            )

        variants = self._split_list_value(item.get('variants'))
        if not variants:
            variants = [str(original)]

        context_keywords = self._split_list_value(
            item.get('context_keywords') or item.get('keywords')
        )
        priority = int(item.get('priority') or 100)
        source = item.get('source') or f"custom:{path.name}"

        return DictionaryEntry(
            id=str(item.get('id') or f"custom-{path.stem}-{index}"),
            original=str(original),
            significado=str(significado),
            variants=variants,
            priority=priority,
            source=str(source),
            context_keywords=context_keywords
        )

    def _compile_pattern(self) -> None:
        """
        Compila el patrón regex para detección de siglas.

        CRÍTICO: Las variantes se ordenan por longitud DESCENDENTE
        para prevenir matches parciales (ej: "art" antes de "art.").
        """
        # 1. Recopilar todas las variantes de todas las entradas
        all_variants: set[str] = set()
        for entry in self._index.get_all_entries():
            self._add_search_variants(all_variants, entry.original)
            for variant in entry.variants:
                self._add_search_variants(all_variants, variant)

        # 2. Ordenar por longitud DESCENDENTE (CRÍTICO)
        sorted_variants = sorted(all_variants, key=len, reverse=True)

        # 3. Escapar caracteres especiales de regex
        escaped_variants = [escape_regex(v) for v in sorted_variants]

        # 4. Construir patrón con lookahead/lookbehind para word boundaries
        # Incluye caracteres españoles: áéíóúñÑüÜ
        pattern_str = (
            r'(?<![a-zA-ZáéíóúñÑüÜ0-9])'  # Negative lookbehind
            r'(' + '|'.join(escaped_variants) + r')'  # Grupo de captura
            r'(?![a-zA-ZáéíóúñÑüÜ0-9])'  # Negative lookahead
        )

        self._pattern = re.compile(pattern_str)

    @staticmethod
    def _add_search_variants(target: set[str], value: str) -> None:
        """
        Añade variantes de búsqueda derivadas de siglas compactas.

        Replica la mejora del paquete NPM: además de la forma canónica,
        permite detectar variantes minúsculas y formas con puntos como
        A.E.A.T. sin inflar el diccionario fuente.
        """
        target.add(value)

        if re.fullmatch(r'[A-ZÁÉÍÓÚÑÜ0-9]{3,10}', value):
            dotted_upper = '.'.join(value) + '.'
            lower = value.lower()
            dotted_lower = '.'.join(lower) + '.'

            target.add(dotted_upper)
            target.add(lower)
            target.add(dotted_lower)

    @classmethod
    def get_instance(cls) -> SiglasMatcher:
        """Obtiene la instancia única del matcher."""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """Resetea la instancia singleton (útil para testing)."""
        with cls._lock:
            cls._instance = None

    def find_matches(self, text: str, options: InternalOptions) -> list[MatchInfo]:
        """
        Busca todas las siglas en el texto según las opciones.

        Algoritmo:
        1. Ejecuta regex global para encontrar candidatos
        2. Para cada match:
           - Valida word boundaries
           - Valida contexto especial (URLs, emails, código)
           - Aplica filtros exclude/include
           - Aplica expandOnlyFirst
           - Busca en diccionario
           - Maneja duplicados

        Args:
            text: Texto a procesar
            options: Opciones de expansión

        Returns:
            Lista de MatchInfo con información de cada sigla encontrada
        """
        return self.find_matches_detailed(text, options).matches

    @staticmethod
    def _add_omitted_match(
        omitted_matches: list[OmittedMatchInfo],
        match: re.Match[str],
        reason: OmittedAcronymReason,
        details: Optional[str] = None
    ) -> None:
        omitted_matches.append(OmittedMatchInfo(
            original=match.group(0),
            start_pos=match.start(),
            end_pos=match.end(),
            reason=reason,
            details=details
        ))

    @staticmethod
    def _special_context_reason(
        text: str,
        start_pos: int,
        end_pos: int,
        options: SpecialContextOptions
    ) -> Optional[OmittedAcronymReason]:
        reason_map: dict[str, OmittedAcronymReason] = {
            'url': 'inside-url',
            'email': 'inside-email',
            'code-block': 'inside-code-block',
            'inline-code': 'inside-inline-code',
        }
        special_context = is_in_special_context(text, start_pos, end_pos, options)
        if special_context:
            return reason_map.get(special_context)
        return None

    @staticmethod
    def _contains_normalized(values: list[str], normalized_value: str) -> bool:
        return any(normalize(value) == normalized_value for value in values)

    def _filter_omission_reason(
        self,
        normalized_matched: str,
        options: InternalOptions,
        seen: set[str]
    ) -> Optional[OmittedAcronymReason]:
        if options.exclude and self._contains_normalized(options.exclude, normalized_matched):
            return 'excluded'

        if options.include is not None and not self._contains_normalized(
            options.include,
            normalized_matched,
        ):
            return 'not-in-include'

        if options.expand_only_first:
            if normalized_matched in seen:
                return 'expand-only-first'
            seen.add(normalized_matched)

        return None

    def _lookup_match_entry(
        self,
        text: str,
        matched: str,
        start_pos: int,
        end_pos: int
    ) -> Optional[DictionaryEntry]:
        context_text = text[max(0, start_pos - 120):min(len(text), end_pos + 120)]
        return self._index.lookup(
            matched,
            case_sensitive=False,
            context_text=context_text
        )

    @staticmethod
    def _manual_duplicate_resolution(
        options: InternalOptions,
        normalized_matched: str
    ) -> Optional[str]:
        for key, value in options.duplicate_resolution.items():
            if normalize(key) == normalized_matched:
                return value
        return None

    def _resolve_match_expansion(
        self,
        entry: DictionaryEntry,
        normalized_matched: str,
        options: InternalOptions
    ) -> ResolvedExpansion:
        has_multiple = self._index.has_multiple_meanings(entry.original)
        expansion = entry.significado
        all_meanings = None

        if not has_multiple:
            return ResolvedExpansion(expansion, has_multiple, all_meanings, None)

        all_meanings = self._index.get_all_meanings(entry.original)
        manual_resolution = self._manual_duplicate_resolution(options, normalized_matched)
        if manual_resolution:
            return ResolvedExpansion(manual_resolution, has_multiple, all_meanings, None)

        if options.auto_resolve_duplicates:
            return ResolvedExpansion(expansion, has_multiple, all_meanings, None)

        return ResolvedExpansion(
            expansion,
            has_multiple,
            all_meanings,
            ' | '.join(all_meanings or []),
        )

    @staticmethod
    def _build_match_info(
        match: re.Match[str],
        entry: DictionaryEntry,
        resolved: ResolvedExpansion,
        options: InternalOptions
    ) -> MatchInfo:
        return MatchInfo(
            original=match.group(0) if options.preserve_case else entry.original,
            expansion=resolved.expansion,
            start_pos=match.start(),
            end_pos=match.end(),
            confidence=1.0,
            has_multiple_meanings=resolved.has_multiple,
            all_meanings=resolved.all_meanings,
            source=entry.source
        )

    def find_matches_detailed(
        self,
        text: str,
        options: InternalOptions
    ) -> MatchRunResult:
        """
        Busca siglas y conserva trazabilidad de matches omitidos.

        Returns:
            MatchRunResult con matches expandidos, omisiones y estadísticas.
        """
        matches: list[MatchInfo] = []
        omitted_matches: list[OmittedMatchInfo] = []
        seen: set[str] = set()  # Para expandOnlyFirst
        total_acronyms_found = 0
        ambiguous_not_expanded = 0

        # Configuración de contextos especiales
        context_options = SpecialContextOptions(
            skip_urls=True,
            skip_emails=True,
            skip_code_blocks=True,
            skip_inline_code=True
        )

        # Iterar sobre todos los matches del patrón
        for match in self._pattern.finditer(text):
            matched = match.group(0)
            start_pos = match.start()
            end_pos = match.end()
            normalized_matched = normalize(matched)

            # VALIDACIÓN 1: ¿Es parte de palabra más larga?
            if is_part_of_larger_word(text, start_pos, end_pos):
                continue

            # VALIDACIÓN 2: ¿Está en contexto especial?
            omitted_reason = self._special_context_reason(
                text,
                start_pos,
                end_pos,
                context_options
            )
            if omitted_reason:
                self._add_omitted_match(
                    omitted_matches,
                    match,
                    omitted_reason
                )
                continue

            omitted_reason = self._filter_omission_reason(
                normalized_matched,
                options,
                seen
            )
            if omitted_reason:
                self._add_omitted_match(
                    omitted_matches,
                    match,
                    omitted_reason
                )
                continue

            # BÚSQUEDA EN DICCIONARIO
            entry = self._lookup_match_entry(text, matched, start_pos, end_pos)
            if not entry:
                self._add_omitted_match(
                    omitted_matches,
                    match,
                    'not-found'
                )
                continue

            total_acronyms_found += 1

            # MANEJO DE DUPLICADOS
            resolved = self._resolve_match_expansion(entry, normalized_matched, options)
            if resolved.ambiguity_details is not None:
                ambiguous_not_expanded += 1
                self._add_omitted_match(
                    omitted_matches,
                    match,
                    'ambiguous-unresolved',
                    resolved.ambiguity_details
                )
                continue

            matches.append(self._build_match_info(
                match,
                entry,
                resolved,
                options
            ))

        return MatchRunResult(
            matches=matches,
            omitted_matches=omitted_matches,
            stats=MatchRunStats(
                total_acronyms_found=total_acronyms_found,
                ambiguous_not_expanded=ambiguous_not_expanded
            )
        )

    def buscar_sigla(self, sigla: str) -> Optional[AcronymSearchResult]:
        """
        Busca información sobre una sigla específica.

        Args:
            sigla: Sigla a buscar

        Returns:
            AcronymSearchResult con información de la sigla, o None
        """
        entry = self._index.lookup(sigla, case_sensitive=False)
        if not entry:
            return None

        meanings = self._index.get_all_meanings(sigla)
        if not meanings:
            meanings = [entry.significado]

        return AcronymSearchResult(
            acronym=entry.original,
            meanings=meanings,
            has_duplicates=len(meanings) > 1,
            source=entry.source
        )

    def listar_siglas(self) -> list[str]:
        """
        Lista todas las siglas disponibles.

        Returns:
            Lista de siglas originales (sin variantes)
        """
        seen = set()
        result = []
        for entry in self._index.get_all_entries():
            if entry.original not in seen:
                seen.add(entry.original)
                result.append(entry.original)
        return sorted(result)

    def obtener_estadisticas(self) -> DictionaryStats:
        """
        Obtiene estadísticas del diccionario.

        Returns:
            DictionaryStats con métricas del diccionario
        """
        entries = self._index.get_all_entries()

        # Contar siglas únicas
        unique_originals = {entry.original for entry in entries}
        total_acronyms = len(unique_originals)

        # Contar siglas con duplicados
        acronyms_with_duplicates = 0
        for original in unique_originals:
            if self._index.has_multiple_meanings(original):
                acronyms_with_duplicates += 1

        # Contar siglas con puntuación
        acronyms_with_punctuation = sum(
            1 for original in unique_originals
            if '.' in original or '/' in original or ' ' in original
        )

        return DictionaryStats(
            total_acronyms=total_acronyms,
            acronyms_with_duplicates=acronyms_with_duplicates,
            acronyms_with_punctuation=acronyms_with_punctuation
        )

    def obtener_info_diccionario(self) -> DictionaryInfo:
        """
        Obtiene metadata completa del diccionario cargado.

        Returns:
            DictionaryInfo con versión, fecha, variantes y fuentes
        """
        return self._index.get_info()


def get_matcher(custom_dictionaries: Optional[list[str]] = None) -> SiglasMatcher:
    """
    Obtiene la instancia del matcher (función de conveniencia).

    Returns:
        Instancia singleton del SiglasMatcher
    """
    if custom_dictionaries:
        return SiglasMatcher(custom_dictionaries=custom_dictionaries)
    return SiglasMatcher.get_instance()
