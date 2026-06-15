[![PyPI version](https://img.shields.io/pypi/v/legal-expand.svg?label=PyPI&cacheSeconds=300)](https://pypi.org/project/legal-expand/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python versions](https://img.shields.io/pypi/pyversions/legal-expand.svg)](https://pypi.org/project/legal-expand/)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/686f6c61/pypi-legal-expand/blob/main/legal_expand_demo.ipynb)

# Siglas legales españolas para documentos jurídicos

**646 siglas legales españolas verificadas** | Expansión inteligente para textos jurídicos

## ¿Qué hace este paquete?

`legal-expand` es una librería Python que **expande automáticamente siglas legales** en textos jurídicos españoles, añadiendo su significado completo entre paréntesis para facilitar la comprensión.

**Ejemplo:**
```
Entrada: "La AEAT notifica el IVA según el art. 123 del CC"
Salida:  "La AEAT (Agencia Estatal de Administración Tributaria) notifica el IVA (Impuesto sobre el Valor Añadido) según el art. (Artículo) 123 del CC (Código Civil)"
```

### Características principales

- **646 siglas verificadas** de leyes, organismos, impuestos, tribunales y procedimientos
- **Fuentes oficiales**: RAE, DPEJ, BOE y legislación vigente
- **Detección inteligente** de variantes (AEAT, A.E.A.T., A.E.A.T)
- **Múltiples formatos**: texto plano, HTML semántico, JSON estructurado
- **Diagnóstico de omisiones**: razones estables para siglas omitidas por filtros o contexto
- **CLI oficial**: expansión, auditoría, glosario, batch, metadata y benchmark desde terminal
- **Glosarios y auditoría**: exportación Markdown, CSV y JSON
- **Procesamiento de documentos**: `.txt`, `.md`, `.html` y carpetas completas
- **Diccionarios personalizados**: añade siglas propias desde JSON o CSV
- **Documentos largos optimizados**: expandir solo primera ocurrencia para evitar repeticiones
- **Control granular**: configuración global + override por llamada
- **Zero dependencies**: sin dependencias en runtime
- **Type hints completos**: tipos para autocompletado en IDEs
- **Python 3.9+**: compatible con versiones modernas

## Demo interactiva

Prueba el paquete sin instalar nada:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/686f6c61/pypi-legal-expand/blob/main/legal_expand_demo.ipynb)

El notebook incluye ejemplos de todos los casos de uso: expansión básica, formatos de salida, configuración global, documentos reales y herramientas interactivas.

## Índice

- [Demo interactiva](#demo-interactiva)
- [Instalación](#instalación)
- [CLI](#cli)
- [Uso básico](#uso-básico)
- [Formatos de salida](#formatos-de-salida)
- [Diagnóstico de omisiones](#diagnóstico-de-omisiones)
- [Glosario y auditoría](#glosario-y-auditoría)
- [Documentos y batch](#documentos-y-batch)
- [Diccionarios personalizados](#diccionarios-personalizados)
- [Control global y override](#control-global-y-override)
- [Opciones avanzadas](#opciones-avanzadas)
- [Manejo de duplicados](#manejo-de-duplicados)
- [Funciones auxiliares](#funciones-auxiliares)
- [Uso en frameworks](#uso-en-frameworks)
- [Casos de uso completos](#casos-de-uso-completos)
- [Uso en backend para LLMs](#uso-en-backend-para-llms)
- [Protección de contextos](#protección-de-contextos)
- [Extensibilidad](#extensibilidad)
- [API completa](#api-completa)
- [Siglas incluidas](#siglas-incluidas)
- [Rendimiento](#rendimiento)
- [Compatibilidad](#compatibilidad)
- [Fuentes de las siglas](#fuentes-de-las-siglas)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

## Instalación

```bash
pip install legal-expand
```

## CLI

Al instalar el paquete se crea el comando `legal-expand`.

```bash
# Expandir un archivo
legal-expand sentencia.txt --expand-only-first --output sentencia-expandida.txt

# Leer de stdin
cat sentencia.txt | legal-expand --format html

# Diagnóstico completo
legal-expand audit sentencia.txt --report-format markdown --output audit.md

# Glosario único
legal-expand glossary sentencia.txt --glossary-format csv --output glosario.csv

# Procesar una carpeta completa (.txt, .md, .html)
legal-expand batch docs/ docs-expandidos/ --format html

# Metadata y benchmark
legal-expand info
legal-expand benchmark sentencia.txt --iterations 500
```

## Uso básico

### Expansión simple

El caso de uso más común es expandir siglas en un texto legal. El paquete detecta automáticamente las siglas y añade su significado entre paréntesis.

```python
from legal_expand import expandir_siglas

texto = 'La AEAT notifica el IVA'
resultado = expandir_siglas(texto)

print(resultado)
# Salida: 'La AEAT (Agencia Estatal de Administración Tributaria) notifica el IVA (Impuesto sobre el Valor Añadido)'
```

### Expansión de múltiples siglas

El paquete puede procesar textos complejos con múltiples siglas diferentes, manteniendo la estructura y formato original del texto.

```python
texto = 'Según el art. 123 del CC y la LEC, la AEAT debe procesar el BOE.'
resultado = expandir_siglas(texto)

print(resultado)
# Salida: 'Según el art. (Artículo) 123 del CC (Código Civil) y la LEC (Ley de Enjuiciamiento Civil),
#          la AEAT (Agencia Estatal de Administración Tributaria) debe procesar el BOE (Boletín Oficial del Estado).'
```

### Detección de variantes

El sistema detecta automáticamente variantes de siglas con o sin puntos, mayúsculas/minúsculas, y espacios internos.

```python
# Todas estas variantes se detectan y expanden correctamente:

expandir_siglas('El art. 5 establece')
# Salida: 'El art. (Artículo) 5 establece'

expandir_siglas('El art 5 establece')  # Sin punto
# Salida: 'El art (Artículo) 5 establece'

expandir_siglas('La AEAT notifica')
# Salida: 'La AEAT (Agencia Estatal de Administración Tributaria) notifica'

expandir_siglas('La A.E.A.T. notifica')  # Con puntos
# Salida: 'La A.E.A.T. (Agencia Estatal de Administración Tributaria) notifica'
```

## Formatos de salida

### Formato de texto plano (por defecto)

El formato de texto plano añade el significado entre paréntesis inmediatamente después de cada sigla.

```python
resultado = expandir_siglas('La AEAT notifica el IVA')
# Salida: 'La AEAT (Agencia Estatal de Administración Tributaria) notifica el IVA (Impuesto sobre el Valor Añadido)'
```

### Formato HTML semántico

El formato HTML utiliza la etiqueta `<abbr>` con el atributo `title`, proporcionando tooltips nativos del navegador.

```python
from legal_expand import expandir_siglas, ExpansionOptions

resultado = expandir_siglas('La AEAT notifica', ExpansionOptions(format='html'))
print(resultado)
# Salida: 'La <abbr title="Agencia Estatal de Administración Tributaria">AEAT</abbr> (Agencia Estatal de Administración Tributaria) notifica'
```

**Uso en aplicaciones web (Flask, Django, FastAPI):**

```python
from flask import render_template_string
from legal_expand import expandir_siglas, ExpansionOptions

@app.route('/documento/<id>')
def documento(id):
    texto = obtener_documento(id)
    html_expandido = expandir_siglas(texto, ExpansionOptions(format='html'))
    return render_template_string('<div>{{ contenido|safe }}</div>', contenido=html_expandido)
```

### Formato estructurado (objeto)

El formato estructurado devuelve un objeto con metadata completa sobre las siglas encontradas.

```python
from legal_expand import expandir_siglas, ExpansionOptions

resultado = expandir_siglas('AEAT y BOE', ExpansionOptions(format='structured'))

print(resultado.original_text)      # 'AEAT y BOE'
print(resultado.expanded_text)      # 'AEAT (Agencia...) y BOE (Boletín...)'
print(resultado.stats.total_expanded)  # 2

for acronym in resultado.acronyms:
    print(f"{acronym.acronym} → {acronym.expansion}")
```

**Caso de uso - Análisis de documento:**

```python
analisis = expandir_siglas(documento, ExpansionOptions(format='structured'))

print(f"Documento procesado:")
print(f"- Siglas encontradas: {analisis.stats.total_acronyms_found}")
print(f"- Siglas expandidas: {analisis.stats.total_expanded}")
print(f"- Siglas ambiguas no expandidas: {analisis.stats.ambiguous_not_expanded}")

for sigla in analisis.acronyms:
    print(f"  • {sigla.acronym} → {sigla.expansion}")
```

## Diagnóstico de omisiones

Si necesitas saber por qué una sigla detectada no se expandió, usa `expandir_siglas_detallado()`.
Devuelve la misma salida estructurada y añade `omitted_acronyms` con motivos estables.

```python
from legal_expand import expandir_siglas_detallado, ExpansionOptions

resultado = expandir_siglas_detallado(
    'Visita https://aeat.es y revisa AEAT y BOE',
    ExpansionOptions(include=['AEAT'])
)

for omitida in resultado.omitted_acronyms:
    print(omitida.acronym, omitida.reason)

# Posibles razones:
# excluded, not-in-include, expand-only-first, ambiguous-unresolved,
# inside-url, inside-email, inside-code-block, inside-inline-code, not-found
```

Todos los objetos de salida principales tienen `to_dict()` y `to_json()`.

```python
print(resultado.to_json(indent=2))
```

## Glosario y auditoría

```python
from legal_expand import auditar_texto, exportar_glosario, extraer_siglas

texto = 'La AEAT gestiona el IVA. La AEAT publica aviso en el BOE. XYZ aparece.'

# Detectar sin modificar el texto
extraccion = extraer_siglas(texto)

# Exportar glosario único
markdown = exportar_glosario(texto, 'markdown')
csv = exportar_glosario(texto, 'csv')
json_glosario = exportar_glosario(texto, 'json')

# Auditar conocidas, desconocidas, omitidas y repetidas
reporte = auditar_texto(texto)
print(reporte.stats.to_dict())
```

## Documentos y batch

```python
from legal_expand import ExpansionOptions, expandir_documento, procesar_archivo, procesar_directorio

html = '<p>La AEAT notifica el IVA</p>'
resultado = expandir_documento(html, ExpansionOptions(format='html'), document_format='html')

procesar_archivo('sentencia.md', 'sentencia-expandida.md', ExpansionOptions(expand_only_first=True))
procesar_directorio('docs/', 'docs-expandidos/', ExpansionOptions(format='html'))
```

En HTML se preservan etiquetas y atributos, expandiendo solo nodos de texto.

## Diccionarios personalizados

Puedes añadir siglas propias con JSON o CSV sin recompilar el paquete.

```json
[
  {
    "acronym": "LXP",
    "expansion": "Legal Expand Personalizado",
    "variants": ["LXP"],
    "source": "equipo-interno"
  }
]
```

```python
from legal_expand import ExpansionOptions, expandir_siglas, obtener_info_diccionario

opciones = ExpansionOptions(custom_dictionaries=['mi_diccionario.json'])
print(expandir_siglas('Usa LXP en el informe', opciones))

info = obtener_info_diccionario(['mi_diccionario.json'])
print(info.to_dict())
```

## Control global y override

### Configuración global

Puedes configurar el comportamiento del paquete globalmente para toda tu aplicación.

```python
from legal_expand import configurar_globalmente, expandir_siglas, GlobalConfig, ExpansionOptions

# Configurar opciones por defecto para toda la aplicación
configurar_globalmente(GlobalConfig(
    enabled=True,
    default_options=ExpansionOptions(
        format='html',
        expand_only_first=True
    )
))

# Ahora todas las llamadas usarán estas opciones por defecto
expandir_siglas('AEAT y BOE')  # Usará format='html' y expand_only_first=True
```

### Desactivación global

Puedes desactivar la expansión globalmente.

```python
from legal_expand import configurar_globalmente, expandir_siglas, GlobalConfig

# Desactivar expansión globalmente
configurar_globalmente(GlobalConfig(enabled=False))

expandir_siglas('La AEAT notifica el IVA')
# Salida: 'La AEAT notifica el IVA' (sin expandir)
```

### Override de configuración global

El parámetro `force_expansion` permite anular la configuración global para llamadas específicas.

```python
from legal_expand import configurar_globalmente, expandir_siglas, GlobalConfig, ExpansionOptions

configurar_globalmente(GlobalConfig(enabled=False))

# No se expande (respeta configuración global)
expandir_siglas('La AEAT notifica')
# Salida: 'La AEAT notifica'

# Forzar expansión aunque esté desactivado globalmente
expandir_siglas('La AEAT notifica', ExpansionOptions(force_expansion=True))
# Salida: 'La AEAT (Agencia Estatal de Administración Tributaria) notifica'

# Forzar NO expansión aunque esté activado globalmente
configurar_globalmente(GlobalConfig(enabled=True))
expandir_siglas('La AEAT notifica', ExpansionOptions(force_expansion=False))
# Salida: 'La AEAT notifica'
```

### Resetear configuración

Restaura la configuración a sus valores por defecto.

```python
from legal_expand import resetear_configuracion

# Después de múltiples configuraciones...
resetear_configuracion()
# Ahora todo vuelve a: enabled=True, format='plain', etc.
```

## Opciones avanzadas

### Expandir solo primera ocurrencia

**Ideal para documentos largos** (sentencias, contratos, informes de 100+ páginas). Con `expand_only_first=True`, solo se expande la primera aparición de cada sigla.

```python
from legal_expand import expandir_siglas, ExpansionOptions

documento_largo = """
La AEAT ha notificado la liquidación. La AEAT requiere documentación adicional.
El contribuyente debe presentar ante la AEAT los justificantes. La AEAT verificará
los datos. En caso de discrepancia, la AEAT solicitará aclaraciones...
"""

resultado = expandir_siglas(documento_largo, ExpansionOptions(expand_only_first=True))

# Resultado:
# "La AEAT (Agencia Estatal de Administración Tributaria) ha notificado...
#  La AEAT requiere documentación... (resto sin expandir)"
```

**Beneficios:**
- Documentos de 100 páginas permanecen legibles
- Reduce el tamaño del documento en un 70-80% cuando hay muchas siglas repetidas
- Perfecto para sentencias judiciales, contratos, informes técnicos

### Excluir siglas específicas

```python
resultado = expandir_siglas('AEAT, BOE y CC', ExpansionOptions(exclude=['CC']))

print(resultado)
# Salida: 'AEAT (Agencia Estatal de Administración Tributaria), BOE (Boletín Oficial del Estado) y CC'
```

### Incluir solo siglas específicas

```python
resultado = expandir_siglas('AEAT, BOE, CC, IVA y IRPF', ExpansionOptions(include=['AEAT', 'BOE']))

print(resultado)
# Salida: 'AEAT (Agencia Estatal de Administración Tributaria), BOE (Boletín Oficial del Estado), CC, IVA y IRPF'
```

### Combinar opciones

```python
resultado = expandir_siglas(documento, ExpansionOptions(
    format='html',
    expand_only_first=True,
    exclude=['CC', 'art.'],
    preserve_case=True
))
```

## Manejo de duplicados

El motor soporta siglas con múltiples significados cuando el diccionario declare conflictos explícitos.
En la versión actual del diccionario incluido, `obtener_estadisticas().acronyms_with_duplicates` devuelve `0`, por lo que las opciones de duplicados quedan preparadas para futuras ampliaciones del diccionario sin afectar a las siglas actuales.

### Resolución manual

```python
resultado = expandir_siglas(texto, ExpansionOptions(
    duplicate_resolution={
        'SIGLA': 'Significado elegido manualmente'
    }
))
```

### Auto-resolver duplicados

```python
resultado = expandir_siglas(texto, ExpansionOptions(auto_resolve_duplicates=True))
```

### Consultar duplicados

```python
from legal_expand import obtener_estadisticas

stats = obtener_estadisticas()
print(stats.acronyms_with_duplicates)
# 0 en el diccionario actual
```

## Funciones auxiliares

### Buscar sigla específica

```python
from legal_expand import buscar_sigla

info = buscar_sigla('AEAT')
print(info)
# AcronymSearchResult(acronym='AEAT', meanings=['Agencia Estatal de Administración Tributaria'], has_duplicates=False)
```

### Listar todas las siglas

```python
from legal_expand import listar_siglas

siglas = listar_siglas()
print(f"Total de siglas: {len(siglas)}")
print(f"Primeras 10: {siglas[:10]}")
# Salida: ['AEAT', 'AENA', 'AIE', 'AJD', 'AMI', ...]
```

### Obtener estadísticas

```python
from legal_expand import obtener_estadisticas

stats = obtener_estadisticas()
print(stats)
# DictionaryStats(total_acronyms=646, acronyms_with_duplicates=0, acronyms_with_punctuation=150)

print(f"El diccionario contiene {stats.total_acronyms} siglas")
```

## Uso en frameworks

### FastAPI

```python
from fastapi import FastAPI
from pydantic import BaseModel
from legal_expand import expandir_siglas, ExpansionOptions

app = FastAPI()

class TextoRequest(BaseModel):
    texto: str
    formato: str = 'plain'

@app.post("/expandir")
async def expandir(request: TextoRequest):
    resultado = expandir_siglas(
        request.texto,
        ExpansionOptions(format=request.formato)
    )
    return {"resultado": resultado}
```

### Flask

```python
from flask import Flask, request, jsonify
from legal_expand import expandir_siglas, ExpansionOptions

app = Flask(__name__)

@app.route('/expandir', methods=['POST'])
def expandir():
    data = request.get_json()
    resultado = expandir_siglas(
        data['texto'],
        ExpansionOptions(format=data.get('formato', 'plain'))
    )
    return jsonify({'resultado': resultado})
```

### Django

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from legal_expand import expandir_siglas, ExpansionOptions

@csrf_exempt
def expandir_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        resultado = expandir_siglas(
            data['texto'],
            ExpansionOptions(format=data.get('formato', 'plain'))
        )
        return JsonResponse({'resultado': resultado})
```

### Streamlit

```python
import streamlit as st
from legal_expand import expandir_siglas, ExpansionOptions

st.title("Expansor de Siglas Legales")

texto = st.text_area("Introduce el texto legal:")
formato = st.selectbox("Formato:", ['plain', 'html', 'structured'])

if st.button("Expandir"):
    resultado = expandir_siglas(texto, ExpansionOptions(format=formato))
    if formato == 'structured':
        st.json({
            'original': resultado.original_text,
            'expandido': resultado.expanded_text,
            'siglas': len(resultado.acronyms)
        })
    else:
        st.write(resultado)
```

## Casos de uso completos

### Procesamiento de sentencias judiciales

```python
from legal_expand import expandir_siglas, ExpansionOptions

def procesar_sentencia(sentencia: str) -> str:
    return expandir_siglas(sentencia, ExpansionOptions(
        format='html',
        expand_only_first=True,
        exclude=['art.', 'núm.']  # Muy comunes, no expandir
    ))

sentencia = """
Visto el recurso de casación interpuesto por la AEAT contra
la sentencia dictada por la AN el 15 de marzo de 2024, en
relación con la liquidación del IVA correspondiente al ejercicio
2023, y de conformidad con el art. 123 de la LEC...
"""

sentencia_expandida = procesar_sentencia(sentencia)
```

### Generación de glosarios automáticos

```python
from legal_expand import expandir_siglas, ExpansionOptions

def generar_documento_con_glosario(texto: str) -> str:
    resultado = expandir_siglas(texto, ExpansionOptions(
        format='structured',
        expand_only_first=True
    ))

    # Generar glosario único (sin duplicados)
    glosario = {}
    for sigla in resultado.acronyms:
        if sigla.acronym not in glosario:
            glosario[sigla.acronym] = sigla.expansion

    # Construir documento final
    documento_final = resultado.expanded_text

    if glosario:
        documento_final += '\n\n## Glosario de Siglas\n\n'
        for sigla, significado in sorted(glosario.items()):
            documento_final += f"- **{sigla}**: {significado}\n"

    return documento_final

documento = 'La AEAT gestiona el IVA y el IRPF según normativa del BOE.'
con_glosario = generar_documento_con_glosario(documento)
print(con_glosario)
```

## Uso en backend para LLMs

Una de las aplicaciones más potentes del paquete es pre-procesar textos legales antes de enviarlos a un LLM.

### Beneficios de pre-formatear para LLMs

1. **Mayor precisión**: El LLM entiende el contexto completo sin tener que adivinar significados
2. **Control centralizado**: Toda la lógica de expansión está en el backend
3. **Consistencia**: Todos los textos procesados siguen las mismas reglas

### FastAPI + OpenAI

```python
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from legal_expand import expandir_siglas, ExpansionOptions

app = FastAPI()
client = OpenAI()

class AnalisisRequest(BaseModel):
    texto_legal: str

@app.post("/analizar-legal")
async def analizar_legal(request: AnalisisRequest):
    # 1. Expandir siglas en el backend
    texto_expandido = expandir_siglas(request.texto_legal, ExpansionOptions(
        format='plain',
        expand_only_first=True
    ))

    # 2. Enviar al LLM con contexto completo
    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Eres un asistente legal experto en derecho español."},
            {"role": "user", "content": texto_expandido}
        ]
    )

    return {
        "texto_original": request.texto_legal,
        "texto_expandido": texto_expandido,
        "analisis_llm": completion.choices[0].message.content
    }
```

### AWS Lambda

```python
import json
import boto3
from legal_expand import expandir_siglas, ExpansionOptions

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def lambda_handler(event, context):
    body = json.loads(event['body'])
    documento = body['documento']

    # Expandir siglas
    documento_expandido = expandir_siglas(documento, ExpansionOptions(
        format='plain',
        expand_only_first=True
    ))

    # Usar AWS Bedrock con modelo de tu eleccion
    response = bedrock.invoke_model(
        modelId='amazon.titan-text-express-v1',
        body=json.dumps({
            "inputText": f"Analiza este documento legal:\n\n{documento_expandido}",
            "textGenerationConfig": {
                "maxTokenCount": 4096,
                "temperature": 0.7
            }
        })
    )

    resultado_modelo = json.loads(response['body'].read())

    return {
        'statusCode': 200,
        'body': json.dumps({
            'documento_expandido': documento_expandido,
            'analisis': resultado_modelo['results'][0]['outputText']
        })
    }
```

## Protección de contextos

El paquete incluye detección inteligente de contextos donde las siglas no deben expandirse.

### URLs

```python
texto = 'Visita https://aeat.es para más información sobre AEAT'
resultado = expandir_siglas(texto)

print(resultado)
# Salida: 'Visita https://aeat.es para más información sobre AEAT (Agencia Estatal de Administración Tributaria)'
# La URL queda intacta
```

### Direcciones de email

```python
texto = 'Contacta con info@aeat.es o con la AEAT directamente'
resultado = expandir_siglas(texto)

print(resultado)
# Salida: 'Contacta con info@aeat.es o con la AEAT (Agencia...) directamente'
```

### Bloques de código

```python
texto = """
Para usar AEAT en código:
```python
AEAT = require('aeat')
```
La AEAT es un organismo oficial.
"""

resultado = expandir_siglas(texto)
# El código dentro de ``` no se toca, pero "La AEAT es..." sí se expande
```

## Extensibilidad

### Crear formatter personalizado

```python
from legal_expand import FormatterFactory, Formatter
from legal_expand.types import MatchInfo

class MarkdownFormatter(Formatter):
    def format(self, original_text: str, matches: list[MatchInfo]) -> str:
        if not matches:
            return original_text

        # Ordenar por posición descendente
        sorted_matches = sorted(matches, key=lambda m: m.start_pos, reverse=True)

        result = original_text
        for match in sorted_matches:
            acronym = original_text[match.start_pos:match.end_pos]
            replacement = f"**{acronym}** ({match.expansion})"
            result = result[:match.start_pos] + replacement + result[match.end_pos:]

        return result

# Registrar el formatter
FormatterFactory.register_formatter('markdown', MarkdownFormatter())

# Usar el formatter personalizado
resultado = expandir_siglas('La AEAT notifica', ExpansionOptions(format='markdown'))
print(resultado)
# Salida: 'La **AEAT** (Agencia Estatal de Administración Tributaria) notifica'
```

## API completa

### expandir_siglas(texto, opciones?)

Función principal que expande siglas en un texto.

**Parámetros:**
- `texto` (str): Texto a procesar
- `opciones` (ExpansionOptions, opcional): Configuración de expansión

**Retorna:** `str | StructuredOutput` según el formato especificado

### expandir_siglas_detallado(texto, opciones?)

Expande siglas y devuelve diagnóstico completo de omisiones.

**Retorna:** `DiagnosticOutput`

### extraer_siglas(texto, opciones?, incluir_desconocidas=True)

Detecta siglas sin modificar el texto.

**Retorna:** `ExtractionOutput`

### generar_glosario(texto, opciones?)

Genera entradas únicas de glosario.

**Retorna:** `list[GlossaryEntry]`

### exportar_glosario(texto, formato='markdown', opciones?)

Exporta el glosario como `markdown`, `csv` o `json`.

### auditar_texto(texto, opciones?)

Genera informe de auditoría con conocidas, desconocidas, omitidas, repetidas y glosario.

**Retorna:** `AuditReport`

### expandir_documento(), procesar_archivo(), procesar_directorio()

Procesan texto, Markdown, HTML o carpetas completas preservando estructura básica.

### obtener_info_diccionario(custom_dictionaries?)

Devuelve metadata del diccionario base y diccionarios personalizados.

### benchmark_texto(texto, opciones?, iterations=100)

Mide rendimiento de expansión.

### ExpansionOptions

```python
@dataclass
class ExpansionOptions:
    format: Literal['plain', 'html', 'structured'] = 'plain'
    force_expansion: Optional[bool] = None
    preserve_case: bool = True
    auto_resolve_duplicates: bool = False
    duplicate_resolution: dict[str, str] = field(default_factory=dict)
    expand_only_first: bool = False
    exclude: list[str] = field(default_factory=list)
    include: Optional[list[str]] = None
    custom_dictionaries: list[str] = field(default_factory=list)
```

### StructuredOutput

```python
@dataclass
class StructuredOutput:
    original_text: str
    expanded_text: str
    acronyms: list[ExpandedAcronym]
    stats: Stats
```

### DiagnosticOutput

```python
@dataclass
class DiagnosticOutput(StructuredOutput):
    omitted_acronyms: list[OmittedAcronym] = field(default_factory=list)

@dataclass
class OmittedAcronym:
    acronym: str
    position: Position
    reason: OmittedAcronymReason
    details: Optional[str] = None
```

### configurar_globalmente(config)

Configura el comportamiento global del paquete.

```python
@dataclass
class GlobalConfig:
    enabled: bool = True
    default_options: Optional[ExpansionOptions] = None
```

### obtener_configuracion_global()

Retorna la configuración global actual.

### resetear_configuracion()

Restaura la configuración global a valores por defecto.

### buscar_sigla(sigla)

Busca información sobre una sigla específica en el diccionario.

**Retorna:** `AcronymSearchResult | None`

```python
@dataclass
class AcronymSearchResult:
    acronym: str
    meanings: list[str]
    has_duplicates: bool
```

### listar_siglas()

Retorna lista con todas las siglas disponibles.

**Retorna:** `list[str]`

### obtener_estadisticas()

Retorna estadísticas del diccionario.

```python
@dataclass
class DictionaryStats:
    total_acronyms: int
    acronyms_with_duplicates: int
    acronyms_with_punctuation: int
```

## Siglas incluidas

El paquete incluye **646 siglas legales españolas**, organizadas en las siguientes categorías:

### Impuestos y tributos (45 siglas)

AEAT, IVA, IRPF, IS, ISD, ITP, AJD, IVTM, IBI, IAE, ICIO, IEPPF, IGIC, IGTE, II.EE., IIVTNU, IMIVT, IP, IPC, IRNR, etc.

### Leyes y normativa (80+ siglas)

CC, CCom, CE, LEC, LECrim, LEF, LES, LG, LGDCU, LGEP, LGP, LGSS, LGT, LH, LHL, LIRPF, LIS, LISOS, LIVA, LJCA, LOCE, LODE, LOFAGE, LOFCA, LOGSE, LOLS, LOPJ, LOTC, LOTCu, LOTJ, LPA, LPACAP, etc.

### Organismos e instituciones (60+ siglas)

AENA, AN, AP, BCE, BEI, BOCG, BOE, BOICAC, BOP, CC.AA., CEOE, CES, CGPJ, CNMV, DGCHT, DGRN, DGT, EE.GG., EE.LL., FEADER, FEDER, FEOGA, FFAA, FNMT, FOGASA, FSE, ICAC, IMSERSO, INEM, etc.

### Abreviaturas comunes (30+ siglas)

art., apdo., cfr., disp. adic., disp. derog., disp. final, disp. trans., DNI, expte., Excmo., Ilmo., núm., párr., rec., recl., Rgto., Rs., S., Ss., ss., etc.

### Tipos de sociedades (15+ siglas)

S.A., S.A.L., S.Coop., S.L., S.R.L., S.A.T., s.en C., SLNE, SCE, AIE, UTE, etc.

## Rendimiento

El paquete está optimizado para procesar documentos legales de forma eficiente:

- **Tiempo de procesamiento**:
  - Textos pequeños (100 palabras): menos de 5ms
  - Textos medianos (1,000 palabras): menos de 20ms
  - Textos grandes (10,000 palabras): menos de 100ms
- **Optimizaciones**:
  - Regex pre-compilada al cargar el módulo
  - Diccionario indexado para búsquedas O(1)
  - Sin dependencias en runtime

## Compatibilidad

- **Python**: 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
- **Frameworks**: FastAPI, Flask, Django, Streamlit, y otros
- **Sin dependencias** en runtime

## Fuentes de las siglas

El diccionario de siglas ha sido compilado de múltiples fuentes oficiales:

### Fuentes institucionales

#### Real Academia Española (RAE) - Libro de Estilo de la Justicia

Apéndice 2: Siglas más usualmente empleadas en textos jurídicos españoles.

- **URL**: [https://www.rae.es/libro-estilo-justicia/apéndice-2-siglas](https://www.rae.es/libro-estilo-justicia/apéndice-2-siglas)

#### Diccionario Panhispánico del Español Jurídico (DPEJ) - RAE

Diccionario especializado con definiciones jurídicas enriquecidas.

- **URL**: [https://dpej.rae.es/contenido/siglas-jurídicas](https://dpej.rae.es/contenido/siglas-jurídicas)

### Fuentes propias

- Boletín Oficial del Estado (BOE)
- Legislación española vigente
- Documentación de organismos públicos (AEAT, Seguridad Social, etc.)
- Práctica jurídica habitual en España

### Proceso de validación

Todas las siglas incluidas han sido:

1. **Verificadas** contra fuentes oficiales
2. **Normalizadas** según criterios de la RAE
3. **Priorizadas** según frecuencia de uso en textos legales
4. **Depuradas** eliminando duplicados y variantes incorrectas

## Contribuir

Las contribuciones son bienvenidas. Para contribuir:

1. Haz fork del repositorio
2. Crea una rama para tu funcionalidad (`git checkout -b feature/nueva-funcionalidad`)
3. Realiza tus cambios y añade tests si es necesario
4. Asegúrate de que todos los tests pasan (`pytest`)
5. Haz commit de tus cambios
6. Crea un Pull Request

### Añadir nuevas siglas

Para añadir nuevas siglas, edita el archivo `src/legal_expand/data/dictionary.json` siguiendo el formato existente.

## Licencia

MIT

## Créditos

Desarrollado con el diccionario de 646 siglas legales españolas verificadas de fuentes oficiales (RAE, BOE, DPEJ).

Basado en el paquete npm [legal-expand](https://www.npmjs.com/package/legal-expand).
