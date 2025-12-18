"""
legal-expand - Funciones de normalización y validación

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Contiene funciones utilitarias para normalización de texto, validación
de límites de palabra y detección de contextos especiales.

ARQUITECTURA:
El módulo se organiza en cuatro secciones:
1. Normalización de texto (normalize, escape_regex)
2. Validación de caracteres (is_alphanumeric)
3. Límites de palabra (is_word_boundary, is_part_of_larger_word)
4. Contextos especiales (URLs, emails, código)

RESPONSABILIDADES:
- Normalizar texto para comparación flexible de siglas
- Escapar caracteres especiales para uso en regex
- Validar que los matches son palabras completas
- Proteger siglas dentro de URLs, emails y código

PROTECCIÓN DE CONTEXTOS:
El sistema detecta y protege siglas que aparecen en:
- URLs: https://aeat.es → no expande "aeat"
- Emails: info@aeat.es → no expande "aeat"
- Bloques de código: ```AEAT.method()``` → no expande
- Código inline: `AEAT` → no expande

CARACTERES ESPAÑOLES:
Todas las funciones soportan caracteres acentuados:
áéíóúñÑüÜ (incluidos en patrones de word boundary)

INTEGRACIÓN CON OTROS MÓDULOS:
- matcher: Usa estas funciones durante la detección
- types: Define SpecialContextOptions
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional


# ============================================================================
# NORMALIZACIÓN DE TEXTO
# ============================================================================

def normalize(text: str) -> str:
    """
    Normaliza un texto para comparación flexible.

    Transforma el texto a minúsculas, elimina puntos y espacios.
    Útil para buscar variantes de siglas (AEAT, A.E.A.T., a.e.a.t).

    Args:
        text: Texto a normalizar

    Returns:
        Texto normalizado (lowercase, sin puntos, sin espacios)

    Example:
        >>> normalize("A.E.A.T.")
        'aeat'
        >>> normalize("art. ")
        'art'
    """
    return text.lower().replace('.', '').replace(' ', '')


def escape_regex(text: str) -> str:
    """
    Escapa caracteres especiales de regex.

    Convierte caracteres como . * + ? ^ $ { } ( ) | [ ] \\ en sus
    versiones escapadas para usar en patrones regex.

    Args:
        text: Texto con posibles caracteres especiales

    Returns:
        Texto con caracteres especiales escapados

    Example:
        >>> escape_regex("art.")
        'art\\\\.'
        >>> escape_regex("S.L.")
        'S\\\\.L\\\\.'
    """
    return re.escape(text)


# ============================================================================
# VALIDACIÓN DE CARACTERES Y LÍMITES DE PALABRA
# ============================================================================

# Patrón para caracteres alfanuméricos incluyendo caracteres españoles
_ALPHANUMERIC_PATTERN = re.compile(r'[a-zA-ZáéíóúñÑüÜ0-9]')


def is_alphanumeric(char: str) -> bool:
    """
    Verifica si un carácter es alfanumérico (incluyendo caracteres españoles).

    Incluye letras a-z, A-Z, dígitos 0-9 y caracteres acentuados españoles
    (á, é, í, ó, ú, ñ, Ñ, ü, Ü).

    Args:
        char: Carácter a verificar (string de longitud 1)

    Returns:
        True si es alfanumérico, False en caso contrario

    Example:
        >>> is_alphanumeric('a')
        True
        >>> is_alphanumeric('ñ')
        True
        >>> is_alphanumeric('.')
        False
    """
    if not char:
        return False
    return bool(_ALPHANUMERIC_PATTERN.match(char))


def is_word_boundary(text: str, position: int, direction: Literal['before', 'after']) -> bool:
    """
    Verifica si hay un límite de palabra en una posición dada.

    Un límite de palabra existe cuando el carácter adyacente no es
    alfanumérico o la posición está al inicio/fin del texto.

    Args:
        text: Texto a analizar
        position: Posición a verificar
        direction: 'before' para verificar antes, 'after' para después

    Returns:
        True si hay límite de palabra, False si hay carácter alfanumérico

    Example:
        >>> is_word_boundary("La AEAT", 3, 'before')  # Espacio antes de AEAT
        True
        >>> is_word_boundary("AEATX", 4, 'after')  # X después de AEAT
        False
    """
    if direction == 'before':
        if position == 0:
            return True
        return not is_alphanumeric(text[position - 1])
    else:  # direction == 'after'
        if position >= len(text):
            return True
        return not is_alphanumeric(text[position])


def is_part_of_larger_word(text: str, start_pos: int, end_pos: int) -> bool:
    """
    Verifica si un match es parte de una palabra más grande.

    Previene matches falsos como "AEAT" dentro de "CREATION" o
    "art" dentro de "partial".

    Args:
        text: Texto completo
        start_pos: Posición inicial del match
        end_pos: Posición final del match

    Returns:
        True si el match es parte de una palabra más grande

    Example:
        >>> is_part_of_larger_word("CREATION", 3, 6)  # "ATI" en CREATION
        True
        >>> is_part_of_larger_word("La AEAT", 3, 7)  # "AEAT" independiente
        False
    """
    before = text[start_pos - 1] if start_pos > 0 else ''
    after = text[end_pos] if end_pos < len(text) else ''
    return is_alphanumeric(before) or is_alphanumeric(after)


# ============================================================================
# DETECCIÓN DE CONTEXTOS ESPECIALES
# ============================================================================

def is_inside_url(text: str, start_pos: int, end_pos: int) -> bool:
    """
    Verifica si una posición está dentro de una URL.

    Detecta URLs basándose en protocolos (http://, https://) y
    dominios (www., .com, .es, etc.).

    Args:
        text: Texto completo
        start_pos: Posición inicial del match
        end_pos: Posición final del match

    Returns:
        True si la posición está dentro de una URL

    Example:
        >>> is_inside_url("Visita https://aeat.es info", 14, 18)  # "aeat" en URL
        True
        >>> is_inside_url("La AEAT informa", 3, 7)
        False
    """
    window = 100
    before = text[max(0, start_pos - window):start_pos]
    after = text[end_pos:min(len(text), end_pos + window)]

    # Buscar protocolo antes
    if re.search(r'https?://\S*$', before):
        return True

    # Buscar www. antes
    if re.search(r'www\.\S*$', before):
        return True

    # Buscar patrón de dominio (algo.algo)
    if re.search(r'\S+\.\S+$', before) and re.search(r'^\S+', after):
        # Verificar que parece una URL (tiene extensión típica)
        combined = before[-20:] + text[start_pos:end_pos] + after[:20]
        if re.search(r'\.\w{2,4}(/|$|\s)', combined):
            return True

    return False


def is_inside_email(text: str, start_pos: int, end_pos: int) -> bool:
    """
    Verifica si una posición está dentro de una dirección de email.

    Detecta emails basándose en el patrón usuario@dominio.

    Args:
        text: Texto completo
        start_pos: Posición inicial del match
        end_pos: Posición final del match

    Returns:
        True si la posición está dentro de un email

    Example:
        >>> is_inside_email("Contacta info@aeat.es aquí", 14, 18)  # "aeat" en email
        True
        >>> is_inside_email("La AEAT informa", 3, 7)
        False
    """
    window = 50
    before = text[max(0, start_pos - window):start_pos]
    after = text[end_pos:min(len(text), end_pos + window)]

    # Patrón: algo antes con @ y algo después con dominio
    has_at_before = '@' in before or re.search(r'\S+@$', before)
    has_domain_after = re.search(r'^@?\S*\.\S+', after)

    # También verificar si el @ está justo después
    has_at_after = re.search(r'^@\S+', after)
    has_user_before = re.search(r'\S+$', before) and not before.endswith(' ')

    return (has_at_before and has_domain_after) or (has_user_before and has_at_after)


def is_inside_code_block(text: str, position: int) -> bool:
    """
    Verifica si una posición está dentro de un bloque de código markdown.

    Los bloques de código están delimitados por triple backtick (```).
    Un número impar de ``` antes de la posición indica que estamos dentro.

    Args:
        text: Texto completo
        position: Posición a verificar

    Returns:
        True si está dentro de un bloque de código

    Example:
        >>> is_inside_code_block("```python\\nAEAT\\n```", 12)  # AEAT dentro de ```
        True
        >>> is_inside_code_block("Normal AEAT text", 7)
        False
    """
    before = text[:position]
    triple_backticks = before.count('```')
    return triple_backticks % 2 == 1  # Número impar = dentro del bloque


def is_inside_inline_code(text: str, position: int) -> bool:
    """
    Verifica si una posición está dentro de código inline markdown.

    El código inline está delimitado por backtick simple (`).
    Se excluyen los backticks que forman parte de bloques de código (```).

    Args:
        text: Texto completo
        position: Posición a verificar

    Returns:
        True si está dentro de código inline

    Example:
        >>> is_inside_inline_code("Usa `AEAT.method()` aquí", 6)  # AEAT dentro de `
        True
        >>> is_inside_inline_code("Normal AEAT text", 7)
        False
    """
    before = text[:position]
    # Eliminar bloques de código para no contar sus backticks
    before_no_blocks = before.replace('```', '')
    single_backticks = before_no_blocks.count('`')
    return single_backticks % 2 == 1  # Número impar = dentro del código


@dataclass
class SpecialContextOptions:
    """Opciones para verificación de contextos especiales."""
    skip_urls: bool = True
    skip_emails: bool = True
    skip_code_blocks: bool = True
    skip_inline_code: bool = True


def is_in_special_context(
    text: str,
    start_pos: int,
    end_pos: int,
    options: Optional[SpecialContextOptions] = None
) -> Optional[str]:
    """
    Verifica si una posición está en un contexto especial que debe ignorarse.

    Comprueba si el texto está dentro de URLs, emails, bloques de código
    o código inline. Retorna el tipo de contexto detectado.

    Args:
        text: Texto completo
        start_pos: Posición inicial del match
        end_pos: Posición final del match
        options: Opciones para habilitar/deshabilitar cada verificación

    Returns:
        Tipo de contexto ('url', 'email', 'code-block', 'inline-code')
        o None si no está en ningún contexto especial

    Example:
        >>> is_in_special_context("https://aeat.es", 8, 12)
        'url'
        >>> is_in_special_context("La AEAT informa", 3, 7)
        None
    """
    if options is None:
        options = SpecialContextOptions()

    if options.skip_urls and is_inside_url(text, start_pos, end_pos):
        return 'url'

    if options.skip_emails and is_inside_email(text, start_pos, end_pos):
        return 'email'

    if options.skip_code_blocks and is_inside_code_block(text, start_pos):
        return 'code-block'

    if options.skip_inline_code and is_inside_inline_code(text, start_pos):
        return 'inline-code'

    return None
