# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [1.3.0] - 2026-06-14

### Añadido

- CLI oficial `legal-expand` con comandos `expand`, `audit`, `glossary`, `batch`, `info` y `benchmark`.
- Serialización `to_dict()` y `to_json()` en las dataclasses públicas de salida.
- `extraer_siglas()` para detectar siglas sin modificar el texto.
- `generar_glosario()` y `exportar_glosario()` en formatos Markdown, CSV y JSON.
- `auditar_texto()` con resumen de conocidas, desconocidas, omitidas, repetidas y glosario.
- `expandir_documento()`, `procesar_archivo()` y `procesar_directorio()` para `.txt`, `.md` y `.html`.
- Soporte de diccionarios personalizados JSON/CSV mediante `custom_dictionaries`.
- `obtener_info_diccionario()` con versión, fecha, variantes, fuentes y diccionarios cargados.
- `benchmark_texto()` y subcomando CLI `benchmark`.
- Smoke test de instalación real desde wheel en CI y publicación.

### Cambiado

- El paquete expone un entry point instalable por `[project.scripts]`.
- HTML se puede procesar preservando etiquetas y expandiendo solo nodos de texto.

## [1.2.0] - 2026-06-14

### Añadido

- Nueva función `expandir_siglas_detallado()` con diagnóstico de siglas omitidas.
- Tipos públicos `DiagnosticOutput`, `OmittedAcronym` y `OmittedAcronymReason`.
- Detección de variantes minúsculas y con puntos generadas dinámicamente para siglas compactas.
- Marcador `py.typed` para cumplir PEP 561 y respaldar el clasificador `Typing :: Typed`.

### Cambiado

- `expandir_siglas(..., format='structured')` usa estadísticas del matcher para reflejar omisiones ambiguas.
- La búsqueda interna usa matching normalizado para alinear comportamiento con el paquete NPM.
- Workflow de publicación preparado para PyPI Trusted Publishing con OIDC.

### Corregido

- Sincronizado el ID de `ABE` con el diccionario del paquete NPM.
- Detección de emails más robusta en contextos protegidos.
- Documentación de duplicados ajustada al diccionario actual, que no declara conflictos.

## [1.0.0] - 2025-12-19

### Añadido

- **646 siglas legales españolas** verificadas de fuentes oficiales
- Función principal `expandir_siglas()` para expansión automática
- Tres formatos de salida:
  - `plain`: Texto con expansión entre paréntesis
  - `html`: Etiquetas `<abbr>` semánticas con tooltips
  - `structured`: Objeto con metadata completa
- Sistema de configuración global:
  - `configurar_globalmente()`: Establecer opciones por defecto
  - `obtener_configuracion_global()`: Consultar configuración
  - `resetear_configuracion()`: Restaurar valores por defecto
- Opciones avanzadas:
  - `expand_only_first`: Expandir solo primera ocurrencia
  - `exclude`: Excluir siglas específicas
  - `include`: Incluir solo siglas específicas
  - `force_expansion`: Override de configuración global
- Funciones auxiliares:
  - `buscar_sigla()`: Información sobre una sigla
  - `listar_siglas()`: Lista completa de siglas
  - `obtener_estadisticas()`: Métricas del diccionario
- Protección de contextos especiales:
  - URLs (https://aeat.es)
  - Emails (info@aeat.es)
  - Bloques de código (```)
  - Código inline (`)
- Sistema de formatters extensible:
  - `FormatterFactory.register_formatter()`: Registrar formatters personalizados
  - `FormatterFactory.list_formatters()`: Listar formatters disponibles
- Type hints completos para IDEs
- Zero dependencies en runtime
- Compatibilidad con Python 3.9, 3.10, 3.11, 3.12, 3.13
- Tests completos con pytest (52 tests)
- Demo interactiva (`python demo.py`)

### Fuentes de datos

- Real Academia Española (RAE) - Libro de Estilo de la Justicia
- Diccionario Panhispánico del Español Jurídico (DPEJ)
- Boletín Oficial del Estado (BOE)
- Legislación española vigente

### Notas técnicas

- Diccionario indexado para búsquedas O(1)
- Regex pre-compilada al cargar el módulo
- Patrón Singleton thread-safe para matcher y configuración
- Ordenamiento descendente de variantes por longitud (crítico para regex)

---

## Convenciones de versionado

- **MAJOR** (X.0.0): Cambios incompatibles en la API
- **MINOR** (0.X.0): Nuevas funcionalidades compatibles
- **PATCH** (0.0.X): Correcciones de bugs compatibles

## Enlaces

- [Repositorio](https://github.com/686f6c61/pypi-legal-expand)
- [PyPI](https://pypi.org/project/legal-expand/)
- [Issues](https://github.com/686f6c61/pypi-legal-expand/issues)
