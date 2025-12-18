"""
legal-expand - Sistema de configuración global

@author https://github.com/686f6c61
@repository https://github.com/686f6c61/pypi-legal-expand
@license MIT
@date 12/2025

Implementa el patrón Singleton para gestionar la configuración global
del paquete. Permite activar/desactivar la expansión globalmente y
definir opciones por defecto que se aplican a todas las llamadas.

ARQUITECTURA:
El sistema de configuración sigue el patrón Singleton thread-safe:
1. GlobalConfigManager: Instancia única que almacena la configuración
2. InternalGlobalConfig: Versión interna con valores garantizados
3. API pública: Funciones helper para facilitar el uso

RESPONSABILIDADES:
- Almacenar configuración global de manera centralizada
- Proporcionar sistema de prioridades (local > global)
- Combinar opciones locales con valores por defecto
- Garantizar thread-safety en aplicaciones multi-hilo

SISTEMA DE PRIORIDADES:
1. force_expansion (si está definido) tiene prioridad absoluta
2. enabled global aplica solo si force_expansion es None
3. Opciones locales tienen prioridad sobre defaults globales

INTEGRACIÓN CON OTROS MÓDULOS:
- types: Usa GlobalConfig, ExpansionOptions, InternalOptions
- core/engine: Consulta configuración antes de procesar
- formatters: Usa opciones combinadas para formatear
"""

from __future__ import annotations

import threading
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal, Optional

from .types import ExpansionOptions, GlobalConfig, InternalOptions


# ============================================================================
# CONFIGURACIÓN INTERNA (valores completos, sin None)
# ============================================================================

@dataclass
class InternalGlobalConfig:
    """
    Configuración interna con todos los valores resueltos.

    A diferencia de GlobalConfig público, esta clase garantiza que
    todos los valores tienen un valor por defecto (no None).
    """
    enabled: bool = True
    default_options: InternalOptions = field(default_factory=InternalOptions)


# ============================================================================
# GESTOR DE CONFIGURACIÓN GLOBAL (SINGLETON)
# ============================================================================

class GlobalConfigManager:
    """
    Gestor de configuración global del paquete (Singleton thread-safe).

    Proporciona:
    - Configuración centralizada para toda la aplicación
    - Sistema de prioridades: forceExpansion > config global
    - Merge inteligente de opciones locales con globales
    - Thread-safety para aplicaciones multi-hilo

    Example:
        >>> manager = GlobalConfigManager.get_instance()
        >>> manager.set_config(GlobalConfig(enabled=False))
        >>> manager.should_expand()
        False
    """

    _instance: Optional[GlobalConfigManager] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> GlobalConfigManager:
        """Implementación thread-safe del Singleton."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._config = InternalGlobalConfig()
        return cls._instance

    @classmethod
    def get_instance(cls) -> GlobalConfigManager:
        """
        Obtiene la instancia única del gestor de configuración.

        Returns:
            La instancia singleton de GlobalConfigManager
        """
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """
        Resetea la instancia singleton.

        Útil principalmente para testing. Elimina la instancia actual
        para que la siguiente llamada a get_instance() cree una nueva.
        """
        with cls._lock:
            cls._instance = None

    def set_config(self, config: GlobalConfig) -> None:
        """
        Establece la configuración global.

        Args:
            config: Nueva configuración a aplicar

        Example:
            >>> manager.set_config(GlobalConfig(
            ...     enabled=True,
            ...     default_options=ExpansionOptions(format='html')
            ... ))
        """
        if config.enabled is not None:
            self._config.enabled = config.enabled

        if config.default_options is not None:
            opts = config.default_options
            self._config.default_options = InternalOptions(
                format=opts.format if opts.format is not None else self._config.default_options.format,
                force_expansion=opts.force_expansion,
                preserve_case=opts.preserve_case if opts.preserve_case is not None else self._config.default_options.preserve_case,
                auto_resolve_duplicates=opts.auto_resolve_duplicates if opts.auto_resolve_duplicates is not None else self._config.default_options.auto_resolve_duplicates,
                duplicate_resolution=opts.duplicate_resolution if opts.duplicate_resolution else self._config.default_options.duplicate_resolution,
                expand_only_first=opts.expand_only_first if opts.expand_only_first is not None else self._config.default_options.expand_only_first,
                exclude=opts.exclude if opts.exclude else self._config.default_options.exclude,
                include=opts.include
            )

    def get_config(self) -> GlobalConfig:
        """
        Obtiene la configuración global actual (copia inmutable).

        Returns:
            Copia de la configuración actual como GlobalConfig

        Example:
            >>> config = manager.get_config()
            >>> print(config.enabled)
            True
        """
        return GlobalConfig(
            enabled=self._config.enabled,
            default_options=ExpansionOptions(
                format=self._config.default_options.format,
                force_expansion=self._config.default_options.force_expansion,
                preserve_case=self._config.default_options.preserve_case,
                auto_resolve_duplicates=self._config.default_options.auto_resolve_duplicates,
                duplicate_resolution=deepcopy(self._config.default_options.duplicate_resolution),
                expand_only_first=self._config.default_options.expand_only_first,
                exclude=list(self._config.default_options.exclude),
                include=list(self._config.default_options.include) if self._config.default_options.include else None
            )
        )

    def reset(self) -> None:
        """
        Resetea la configuración a valores por defecto.

        Example:
            >>> manager.set_config(GlobalConfig(enabled=False))
            >>> manager.reset()
            >>> manager.get_config().enabled
            True
        """
        self._config = InternalGlobalConfig()

    def should_expand(self, options: Optional[ExpansionOptions] = None) -> bool:
        """
        Determina si se debe expandir según la configuración y opciones.

        Sistema de prioridad:
        1. force_expansion local (si está definido, tiene prioridad absoluta)
        2. config.enabled global (si force_expansion es None)

        Args:
            options: Opciones locales de la llamada actual

        Returns:
            True si se debe proceder con la expansión

        Example:
            >>> manager.set_config(GlobalConfig(enabled=False))
            >>> manager.should_expand()
            False
            >>> manager.should_expand(ExpansionOptions(force_expansion=True))
            True
        """
        # force_expansion tiene prioridad absoluta
        if options is not None and options.force_expansion is not None:
            return options.force_expansion

        # Si no hay override, usar configuración global
        return self._config.enabled

    def merge_options(self, options: Optional[ExpansionOptions] = None) -> InternalOptions:
        """
        Combina opciones locales con la configuración global.

        Las opciones locales tienen prioridad sobre las globales.
        Usa "nullish coalescing" (is not None) para preservar valores
        falsy explícitos (False, 0, []).

        Args:
            options: Opciones locales a combinar

        Returns:
            InternalOptions con todos los valores resueltos

        Example:
            >>> manager.set_config(GlobalConfig(
            ...     default_options=ExpansionOptions(format='html')
            ... ))
            >>> merged = manager.merge_options(ExpansionOptions(expand_only_first=True))
            >>> merged.format
            'html'
            >>> merged.expand_only_first
            True
        """
        defaults = self._config.default_options

        if options is None:
            return InternalOptions(
                format=defaults.format,
                force_expansion=defaults.force_expansion,
                preserve_case=defaults.preserve_case,
                auto_resolve_duplicates=defaults.auto_resolve_duplicates,
                duplicate_resolution=deepcopy(defaults.duplicate_resolution),
                expand_only_first=defaults.expand_only_first,
                exclude=list(defaults.exclude),
                include=list(defaults.include) if defaults.include else None
            )

        return InternalOptions(
            format=options.format if options.format is not None else defaults.format,
            force_expansion=options.force_expansion if options.force_expansion is not None else defaults.force_expansion,
            preserve_case=options.preserve_case if options.preserve_case is not None else defaults.preserve_case,
            auto_resolve_duplicates=options.auto_resolve_duplicates if options.auto_resolve_duplicates is not None else defaults.auto_resolve_duplicates,
            duplicate_resolution=options.duplicate_resolution if options.duplicate_resolution else deepcopy(defaults.duplicate_resolution),
            expand_only_first=options.expand_only_first if options.expand_only_first is not None else defaults.expand_only_first,
            exclude=options.exclude if options.exclude else list(defaults.exclude),
            include=options.include if options.include is not None else (list(defaults.include) if defaults.include else None)
        )


# ============================================================================
# API PÚBLICA
# ============================================================================

def configurar_globalmente(config: GlobalConfig) -> None:
    """
    Configura el comportamiento global del paquete.

    Permite activar/desactivar la expansión globalmente y establecer
    opciones por defecto que se aplicarán a todas las llamadas.

    Args:
        config: Configuración global a aplicar

    Example:
        >>> from legal_expand import configurar_globalmente, GlobalConfig, ExpansionOptions
        >>> configurar_globalmente(GlobalConfig(
        ...     enabled=True,
        ...     default_options=ExpansionOptions(
        ...         format='html',
        ...         expand_only_first=True
        ...     )
        ... ))
    """
    GlobalConfigManager.get_instance().set_config(config)


def obtener_configuracion_global() -> GlobalConfig:
    """
    Obtiene la configuración global actual.

    Returns:
        Copia de la configuración global actual

    Example:
        >>> config = obtener_configuracion_global()
        >>> print(config.enabled)
        True
    """
    return GlobalConfigManager.get_instance().get_config()


def resetear_configuracion() -> None:
    """
    Resetea la configuración global a valores por defecto.

    Example:
        >>> configurar_globalmente(GlobalConfig(enabled=False))
        >>> resetear_configuracion()
        >>> obtener_configuracion_global().enabled
        True
    """
    GlobalConfigManager.get_instance().reset()


def _get_config_manager() -> GlobalConfigManager:
    """
    Obtiene la instancia del gestor de configuración (uso interno).

    Esta función es para uso interno del paquete.
    Los usuarios deben usar las funciones públicas.

    Returns:
        Instancia singleton de GlobalConfigManager
    """
    return GlobalConfigManager.get_instance()
