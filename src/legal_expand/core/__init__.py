"""
legal-expand - Core module

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Módulo core que contiene el motor de expansión, matcher y normalizer.
Agrupa los componentes principales del sistema de procesamiento.

COMPONENTES:
- engine: Motor principal de expansión y orquestación
- matcher: Detección y validación de siglas
- normalizer: Normalización y validación de texto
"""

from .engine import (
    buscar_sigla,
    expandir_siglas,
    listar_siglas,
    obtener_estadisticas,
)
from .matcher import SiglasMatcher, get_matcher
from .normalizer import normalize, escape_regex, is_in_special_context

__all__ = [
    'expandir_siglas',
    'buscar_sigla',
    'listar_siglas',
    'obtener_estadisticas',
    'SiglasMatcher',
    'get_matcher',
    'normalize',
    'escape_regex',
    'is_in_special_context',
]
