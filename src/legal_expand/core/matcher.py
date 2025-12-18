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

import json
import re
import threading
from pathlib import Path
from typing import Optional

from ..types import (
    AcronymSearchResult,
    DictionaryEntry,
    DictionaryStats,
    InternalOptions,
    MatchInfo,
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
        normalized_index: dict[str, list[str]]
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

    def lookup(self, sigla: str, case_sensitive: bool = True) -> Optional[DictionaryEntry]:
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
            return self._resolve_ids(ids, sigla)

        # NIVEL 2: Flexible match (sin puntos ni espacios)
        flexible = sigla.replace('.', '').replace(' ', '')
        ids = self.exact_index.get(flexible)
        if ids:
            return self._resolve_ids(ids, sigla)

        # NIVEL 3: Normalized match (solo si no es case-sensitive)
        if not case_sensitive:
            normalized_sigla = normalize(sigla)
            ids = self.normalized_index.get(normalized_sigla)
            if ids:
                return self._resolve_ids(ids, sigla)

        return None

    def _resolve_ids(self, ids: list[str], original_sigla: str) -> Optional[DictionaryEntry]:
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

        # Múltiples significados: retornar el de mayor prioridad
        entries = [self.entries_by_id.get(id_) for id_ in ids]
        entries = [e for e in entries if e is not None]

        if not entries:
            return None

        return max(entries, key=lambda e: e.priority)

    def has_multiple_meanings(self, sigla: str) -> bool:
        """
        Verifica si una sigla tiene múltiples significados.

        Args:
            sigla: Sigla a verificar

        Returns:
            True si tiene múltiples significados
        """
        ids = self.exact_index.get(sigla, [])
        if len(ids) > 1:
            return True

        normalized_sigla = normalize(sigla)
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
        ids = self.exact_index.get(sigla, [])
        if not ids:
            normalized_sigla = normalize(sigla)
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


# ============================================================================
# MATCHER DE SIGLAS (SINGLETON)
# ============================================================================

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

    def __new__(cls) -> SiglasMatcher:
        """Implementación thread-safe del Singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Inicializa el matcher cargando el diccionario y compilando regex."""
        self._load_dictionary()
        self._compile_pattern()

    def _load_dictionary(self) -> None:
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
                priority=e.get('priority', 100)
            )
            for e in data['entries']
        ]

        # Construir índice
        self._index = DictionaryIndex(
            entries=entries,
            exact_index=data['index']['exact'],
            normalized_index=data['index']['normalized']
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
            all_variants.add(entry.original)
            for variant in entry.variants:
                all_variants.add(variant)

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
        matches: list[MatchInfo] = []
        seen: set[str] = set()  # Para expandOnlyFirst

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

            # VALIDACIÓN 1: ¿Es parte de palabra más larga?
            if is_part_of_larger_word(text, start_pos, end_pos):
                continue

            # VALIDACIÓN 2: ¿Está en contexto especial?
            if is_in_special_context(text, start_pos, end_pos, context_options):
                continue

            # VALIDACIÓN 3: ¿Está excluida?
            if options.exclude:
                normalized_matched = normalize(matched)
                if any(normalize(ex) == normalized_matched for ex in options.exclude):
                    continue

            # VALIDACIÓN 4: ¿Está incluida? (si include está definido)
            if options.include is not None:
                normalized_matched = normalize(matched)
                if not any(normalize(inc) == normalized_matched for inc in options.include):
                    continue

            # VALIDACIÓN 5: ¿Ya vimos esta sigla? (expandOnlyFirst)
            if options.expand_only_first:
                normalized_matched = normalize(matched)
                if normalized_matched in seen:
                    continue
                seen.add(normalized_matched)

            # BÚSQUEDA EN DICCIONARIO
            entry = self._index.lookup(matched, options.preserve_case)
            if not entry:
                continue

            # MANEJO DE DUPLICADOS
            has_multiple = self._index.has_multiple_meanings(matched)
            expansion = entry.significado
            all_meanings = None

            if has_multiple:
                all_meanings = self._index.get_all_meanings(matched)

                # Verificar resolución manual
                if options.duplicate_resolution:
                    manual_resolution = options.duplicate_resolution.get(matched)
                    if manual_resolution:
                        expansion = manual_resolution
                    elif not options.auto_resolve_duplicates:
                        # No hay resolución manual y no auto-resolve: skip
                        continue
                elif not options.auto_resolve_duplicates:
                    # No hay resolución y no auto-resolve: skip
                    continue

            matches.append(MatchInfo(
                original=matched,
                expansion=expansion,
                start_pos=start_pos,
                end_pos=end_pos,
                confidence=1.0,
                has_multiple_meanings=has_multiple,
                all_meanings=all_meanings
            ))

        return matches

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
            acronym=sigla,
            meanings=meanings,
            has_duplicates=len(meanings) > 1
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
        unique_originals = set(e.original for e in entries)
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


def get_matcher() -> SiglasMatcher:
    """
    Obtiene la instancia del matcher (función de conveniencia).

    Returns:
        Instancia singleton del SiglasMatcher
    """
    return SiglasMatcher.get_instance()
