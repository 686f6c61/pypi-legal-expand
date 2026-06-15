# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [1.5.1] - 2026-06-15

### Cambiado

- README actualizado para documentar `1.5.1` como release de robustez, con cobertura real, Quality Gate y alcance estable del asistente BOE.
- Demo de Google Colab actualizada a `legal-expand==1.5.1`, con nota explícita sobre el gate de cobertura y los flujos BOE/CLI reforzados.
- `DEMO.txt` actualizado para instalar `1.5.1` y reflejar la batería actual de validación.
- Versiones de paquete, workflows de CI/publicación y configuración Sonar actualizadas a `1.5.1`.

### Verificado

- Añadidas pruebas deterministas para cliente BOE, caché, errores de red simulados, parsers JSON/XML, overrides, CLI, documentos, normalizador y serialización.
- Gate de cobertura configurado en `90%` en `pyproject.toml`, CI y workflow de publicación.
- Suite local: `129` tests pasados con cobertura global `94.83%`; BOE `96%`; CLI `97%`.
- Bandit sin issues accionables, build wheel/sdist OK, `twine check` OK y smoke install desde wheel OK.
- SonarQube local en Docker (`http://localhost:9000`) con Quality Gate `OK`, cobertura `94.8%`, cobertura nueva `97.4%`, `0` bugs, `0` vulnerabilidades, `0` code smells, `0` issues abiertos y duplicación nueva `0.0%`.

## [1.5.0] - 2026-06-15

### Añadido

- Revisión BOE explicada con `revisar_boe()`, agrupando referencias en `resolved`, `manual`, `review-required` y `unsupported`.
- Explicaciones deterministas por referencia con `explicar_referencia_boe()` y acciones sugeridas para revisión humana.
- Nuevas salidas del CLI `legal-expand boe`: `review-json`, `html` y `paragraphs`.
- Generación de plantilla editable con `legal-expand boe --overrides-template` y `boe_overrides_template()` para completar referencias pendientes sin perder trazabilidad.
- Informe HTML semántico con `boe_report_to_html()` e informe por párrafos con `boe_report_by_paragraph_markdown()`.
- Tipos públicos `BOEReviewSection`, `BOEReviewItem`, `BOEReviewSummary` y `BOEReviewOutput`.

### Cambiado

- El informe Markdown BOE incluye explicación y acción sugerida en referencias resueltas, pendientes y no soportadas.
- README, demo de Colab y `DEMO.txt` actualizados para explicar límites, casos de uso, revisión manual y salidas nuevas del asistente BOE.
- Versiones de paquete, workflows de CI/publicación y configuración Sonar actualizadas a `1.5.0`.

### Verificado

- Matriz BOE extendida con pruebas de revisión explicada, plantilla de overrides, HTML, informe por párrafos y CLI.
- SonarQube local en Docker (`http://localhost:9000`) con Quality Gate `OK`, `0` issues abiertos, cobertura nueva `81.4%`, duplicación nueva `0.0%` y violaciones nuevas `0`.
- Batería local de calidad ampliada a 115 tests.

## [1.4.1] - 2026-06-15

### Cambiado

- Refactor interno del detector BOE para reducir complejidad ciclomática sin cambiar la API pública ni los estados del informe.
- Dispatch del CLI simplificado mediante una tabla de comandos, manteniendo los mismos subcomandos y argumentos.
- Matcher de siglas reorganizado con objetos internos para metadata del índice y resolución de matches, reduciendo code smells sin afectar al diccionario ni al resultado.
- Demo de Google Colab actualizada a `legal-expand==1.4.1` y limpiada de imports no usados.
- `DEMO.txt` rehecho como guía real de Colab, CLI, Python, BOE, overrides y validación de calidad.
- Configuración Sonar actualizada a la versión `1.4.1` y organización `686f6c61`.

### Corregido

- Documentación de verificación de la release BOE alineada con la suite actual de 107 tests.

### Verificado

- `ruff check .` y perfil estricto de smells sobre `src/legal_expand`: sin issues.
- `mypy src/legal_expand`: sin issues.
- `bandit -r src/legal_expand -ll`: sin issues identificados.
- `pytest --cov`: 107 tests pasados.
- `compileall`, build wheel/sdist y smoke install desde wheel: OK.
- CI de GitHub en Python 3.9, 3.10, 3.11, 3.12, 3.13 y 3.14: OK.
- SonarScanner conecta con SonarQube Cloud, pero el análisis remoto requiere que exista el proyecto o que se configure `SONAR_TOKEN`; el servidor devuelve `Project not found` antes de ejecutar el análisis.

## [1.4.0] - 2026-06-15

### Añadido

- Asistente BOE opt-in con `detectar_referencias_boe()` y `enriquecer_boe()` para localizar referencias legales españolas sin modificar el texto original.
- Subcomando `legal-expand boe` con salida Markdown o JSON, modo `offline` por defecto y modos `cache-first`/`online` para consultar la API de legislación consolidada del BOE cuando se solicite.
- Tipos públicos `BOEOptions`, `BOENorm`, `BOEUnitBlock`, `BOEReference`, `BOEEnrichmentStats` y `BOEEnrichmentOutput`.
- Resolución conservadora de referencias frecuentes como `art. 217 LEC`, `artículo 24 de la Constitución Española`, `art. 14.2 de la Ley 39/2015`, `Ley Orgánica 3/2018`, `Real Decreto 203/2021`, anexos y disposiciones.
- Soporte de formas abreviadas frecuentes como `RD 203/2021`, `LO 3/2018`, `disp. final séptima`, artículos con subletra (`art. 14.2.a)`) y artículos con sufijo (`artículo 14 bis`).
- Overrides manuales en JSON para añadir aliases o referencias que el detector no pueda resolver con seguridad, marcadas como `manual` en el informe.
- Estados estables para auditoría: `resolved`, `resolved-url-only`, `manual`, `needs-boe-search`, `ambiguous`, `not-found`, `unsupported` y `network-error`.
- Demo de Google Colab actualizada a `legal-expand==1.4.0`, con sección BOE, matriz de 25 casos, CLI `legal-expand boe` y ejemplo de overrides manuales.

### Cambiado

- README ampliado con explicación de expectativas, casos de uso, límites deliberados, edición manual y aviso sobre el carácter informativo de los textos consolidados del BOE.

### Seguridad del comportamiento

- El enriquecimiento BOE no se mezcla con `expandir_siglas()` y no consulta red salvo que se use el subcomando/API BOE.
- `Ley 2/2023` sin fecha ni título se marca como ambigua para evitar resolver una norma incorrecta.
- Las referencias dentro de URLs, emails, bloques de código y código inline se ignoran.
- La normativa UE, incluido `RGPD`, se marca como no soportada por esta función, en lugar de intentar resolverla como BOE.

### Verificado

- Añadida una matriz de 25 casos de uso y edge cases para textos tipo sentencia, recurso administrativo, apuntes de oposición, normas completas, referencias ambiguas, abreviaturas procesales, contextos protegidos, overrides manuales y cliente BOE con fixtures.
- Suite completa validada: 107 tests.

## [1.3.1] - 2026-06-15

### Cambiado

- Demo de Google Colab rehecha para `legal-expand==1.3.1`, con recorrido guiado por CLI, auditoría, glosarios, procesamiento batch, HTML seguro, diccionarios personalizados, configuración global y benchmark.
- Badges del README y del notebook actualizados a shields.io para reflejar la versión publicada en PyPI y las versiones Python soportadas.

### Verificado

- El notebook mantiene JSON válido y sus celdas Python principales se ejecutan contra la API pública actual.
- Los ejemplos CLI de la demo se validan con el comando instalable `legal-expand`.

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
