# Mnemosine Oracle

Un asistente de mitología griega con GraphRAG.

Responde preguntas cruzando información entre La Ilíada, La Odisea y artículos de Wikipedia, apoyado en un grafo de conocimiento en Neo4j. Se compara contra un RAG tradicional y contra modelos de lenguaje hechos desde cero.

---

## Tabla de contenido

1. [Investigación](#investigación)
2. [Arquitectura](#arquitectura)
3. [Corpus](#corpus)
4. [Estructura del repositorio](#estructura-del-repositorio)
5. [Instalación](#instalación)
6. [Uso paso a paso](#uso-paso-a-paso)
7. [Esquema del grafo](#esquema-del-grafo)
8. [Evaluación](#evaluación)
9. [Hoja de ruta](#hoja-de-ruta)

---

## Investigación

| Pieza | Tecnología | Por qué |
|---|---|---|
| Base de grafos | Neo4j 5.26 + APOC (Docker) | Requerido por `neo4j-graphrag`; incluye índice vectorial |
| Extracción del grafo | `neo4j-graphrag` `SimpleKGPipeline` + **Gemini 2.5 Flash** | Capa gratuita de Google AI Studio |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` | 384 dimensiones; el mismo modelo para RAG y GraphRAG (comparación justa) |
| Agente | LangGraph | Decide qué herramienta consultar |
| Interfaz | Gradio | Chat, temperatura, camino recorrido en el grafo |
| Modelos desde cero | Python / PyTorch | N-grama y mini red sobre los poemas |

---

## Corpus

| Fuente | Contenido | Licencia |
|---|---|---|
| La Ilíada, Homero, trad. Luis Segalá y Estalella (1908). [Gutenberg #57654](https://www.gutenberg.org/ebooks/57654) | Cantos I, III, VI, XVI, XVIII, XXI, XXII, XXIV | Dominio público |
| La Odisea, Homero, trad. Luis Segalá y Estalella (1910). [Gutenberg #58221](https://www.gutenberg.org/ebooks/58221) | Cantos I, IV, V, VIII, IX, XI, XII, XXII | Dominio público |
| [Wikipedia en español](https://es.wikipedia.org/) | 53 artículos de dioses, héroes, criaturas y lugares (lista en `data/wikis.txt`) | CC BY-SA 4.0 |

**Por qué estos cantos.** 

Se eligieron para que haya personajes que aparecen en los dos poemas y así existan cruces reales: Zeus, Atenea, Hermes, Hefesto, Ares, Afrodita, Menelao, Helena, Agamenón, Aquiles (Odisea XI), Odiseo y Hades.

**Cómo se usa cada fuente**

- **Poemas:** aportan la narrativa (quién hace qué, en qué canto). Alimentan el grafo y el RAG, y son el texto de entrenamiento de los modelos desde cero.
- **Wikipedia:** aporta datos canónicos (genealogía, atributos). Alimenta el grafo y el RAG, pero no el entrenamiento desde cero.
- **equivalencias.csv:** une los nombres latinos y los epítetos de la traducción (Júpiter, Minerva, Pelida, Laertíada, etc.) con el nombre canónico de la entidad.
- **entidades.csv:** lista fija de entidades con su tipo, para que el extractor no cree duplicados.

---

## Estructura del repositorio

```
Mnemosine-Oracle/
├── check_setup.py
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── common/config.py        # rutas y variables de entorno
├── data/
│   ├── raw/iliada/         # cantos originales
│   ├── raw/odisea/
│   ├── wikipedia/          # artículos descargados
│   ├── processed/          # cantos normalizados
│   ├── extracciones/       # salida del LLM por fragmento (caché del grafo)
│   ├── equivalencias.csv
│   ├── entidades.csv
│   └── wikis.txt
├── ingest/                 # Fase 1: preparación de datos
│   ├── prepare.py
│   └── fetch_wikipedia.py
├── graph/                  # Fase 2: construcción del grafo
│   ├── schema.py           # tipos de nodo y relación
│   ├── fuentes.py          # cantos y wikis como documentos
│   ├── nombres.py          # nombres canónicos
│   ├── extraccion.py       # prompt, caché y limpieza
│   ├── neo4j_io.py         # escritura en Neo4j
│   ├── build.py            # carga el grafo
│   ├── revisar.py          # revisión del grafo
│   └── dumps/              # respaldos del grafo
├── rag/                    # Fase 3: RAG normal (baseline)
├── graphrag/               # Fase 3: retrievers de GraphRAG
├── agent/                  # Fase 4: agente LangGraph
├── scratch_models/         # Fase 4: n-grama y mini red
├── app/                    # Fase 4: interfaz Gradio
└── eval/                   # Fase 5: preguntas y resultados
    └── preguntas.json
```

---

## Instalación

### Requisitos

- Python **3.10 a 3.13**
- Docker Desktop
- Una llave gratuita de Gemini: <https://aistudio.google.com/apikey>

### 1. Entorno de Python

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux o macOS:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Neo4j

```powershell
docker compose up -d
```

### 3. Verificar

```powershell
python check_setup.py
```

Debe mostrar `[ok]` en Neo4j, APOC, Gemini y embeddings.

---

## Uso paso a paso

Todos los comandos se corren desde la raíz del repo, con el entorno activado.

| Paso | Comando | Resultado |
|---|---|---|
| 1. Preparar cantos | `python -m ingest.prepare` | `data/processed/`: cantos normalizados, `fragmentos.jsonl`, `corpus_entrenamiento.txt` |
| 2. Descargar Wikipedia | `python -m ingest.fetch_wikipedia` | `data/wikipedia/*.txt` y `_manifest.csv` (revisa las filas marcadas `busqueda`) |
| 3. Construir el grafo | `python -m graph.build` | Grafo en Neo4j y `data/extracciones/` |
| 3b. Revisar el grafo | `python -m graph.revisar` | Conteos, duplicados y vecinos de algunas entidades |
| 4. RAG y GraphRAG | *Fase 3, en construcción* | |
| 5. Agente e interfaz | *Fase 4, en construcción* | |
| 6. Evaluación | *Fase 5, en construcción* | |

### Normalización del texto

Las traducciones son de 1908-1910 y usan ortografía antigua. `prepare.py` la moderniza (`á` - `a`, `fué` - `fue`, `dió` - `dio`, `--` - `—`), une las líneas cortadas de Gutenberg en párrafos y parte cada canto en fragmentos de aproximandamene 1500 caracteres. Cada fragmento guarda libro, canto, canto_titulo y fragmento, para poder citar la fuente en cada respuesta.

---

## Esquema del grafo

El esquema es fijo en `graph/schema.py`, para que el LLM no invente tipos de nodo o de relación en cada fragmento.

**Nodos:** Deidad, Personaje, Criatura, Lugar, Grupo, Objeto.

**Relaciones:** HIJO_DE, HERMANO_DE, ESPOSO_DE, AMA_A, ENFRENTA_A, AYUDA_A, APOYA_A, ORDENA_A, VIAJA_A, VIVE_EN, PERTENECE_A, CREA, POSEE

Además está el **grafo léxico**: 

```
(:Chunk)-[:FROM_DOCUMENT]->(:Document)
```
Con `NEXT_CHUNK` entre fragmentos seguidos y el embedding de cada fragmento. Cada entidad apunta a los fragmentos donde aparece con `FROM_CHUNK`, y cada relación guarda en `fragmentos` los ids de donde salió y en `menciones` cuántos son. Así se recupera el libro y el canto de origen.

---

## Construcción del grafo

Cada fragmento (unos 1500 caracteres en los cantos, 3000 en las wikis) se manda una vez al LLM con el esquema, la lista de `equivalencias.csv` y un ejemplo. La respuesta se guarda en `data/extracciones/<fragmento>.json`, así que una corrida cortada se retoma sin repetir llamadas, y el grafo se puede reconstruir sin el LLM.

Antes de escribir en Neo4j se limpia la extracción:

- Los nombres pasan a su forma canónica: `Júpiter` -> `Zeus`, `el Pelida` -> `Aquiles`, `los argivos` -> `Aqueos`.
- Si una extracción trae caracteres corruptos, se vuelve a pedir al LLM.
- Si la entidad está en `entidades.csv`, se usa ese tipo (Polifemo siempre es `Criatura`). `Hades` como lugar pasa a `Hades (inframundo)`.
- Se descartan tipos y relaciones que no estén en el esquema.
- Las entidades se unen por tipo y nombre, sin duplicados entre fragmentos ni documentos.

| Comando | Para qué |
|---|---|
| `python -m graph.build --plan` | Ver cuántas llamadas al LLM faltan |
| `python -m graph.build --solo wikis` | Cargar las wikis |
| `python -m graph.build --doc iliada_06 --doc odisea_09` | Cargar cantos sueltos (acepta patrones: `odisea_*`) |
| `python -m graph.build --doc iliada_06 --rehacer` | Volver a extraer con el LLM tras cambiar el prompt |
| `python -m graph.build --recargar` | Reescribir desde la caché tras cambiar `equivalencias.csv` |
| `python -m graph.build --reset` | Vaciar Neo4j y cargar todo desde la caché |
| `python -m graph.build --max-llamadas 200` | Limitar las llamadas de una corrida (cuota diaria) |

---

## Evaluación

`eval/preguntas.json` tiene **20 preguntas** con su respuesta esperada y los cantos donde está la evidencia:

| Tipo | Cantidad | Qué mide |
|---|---|---|
| `cruce` | 8 | Información repartida entre la Ilíada y la Odisea |
| `hibrida` | 8 | Poema + Wikipedia, o dos saltos en el grafo |
| `control` | 4 | Un solo canto (el RAG normal debería acertarlas) |

Las preguntas se definieron **antes** de construir el grafo, para no sesgarlas hacia lo que el grafo ya contesta bien. Cada respuesta esperada se verifica contra el texto (campo `verificada`).

**Métricas:**

1. Aciertos de RAG normal vs. GraphRAG, por tipo de pregunta.
2. Pérdida y perplejidad del n-grama y la mini red frente a un transformer.

*Resultados: pendientes.*

---

## Hoja de ruta

**Fase 0: base**
- [x] Estructura del repositorio
- [x] `docker-compose.yml` con Neo4j + APOC
- [x] `requirements.txt`, `.env.example`, `check_setup.py`
- [ ] Neo4j levantado y `check_setup.py` en verde

**Fase 1: datos (días 1-2)**
- [x] 16 cantos seleccionados en `data/raw/`
- [x] `equivalencias.csv` y `entidades.csv`
- [x] `prepare.py`: normalización y fragmentos
- [ ] Descargar Wikipedia y revisar `_manifest.csv`

**Fase 2: grafo (días 3-4)**
- [x] Esquema fijo (`graph/schema.py`)
- [x] Carga reanudable y revisión (`graph/build.py`, `graph/revisar.py`)
- [x] Cargar las wikis (esqueleto genealógico)
- [x] Cargar un canto por poema y revisar a mano
- [ ] Cargar el resto y subir `data/extracciones/` al repo como respaldo

**Fase 3: recuperación (días 5-7)**
- [ ] RAG normal (baseline)
- [ ] GraphRAG con retrievers de Neo4j
- [ ] Primera corrida de las 20 preguntas

**Fase 4: agente, modelos e interfaz (días 8-11)**
- [ ] Agente en LangGraph
- [ ] N-grama y mini red
- [ ] Interfaz en Gradio

**Fase 5: cierre (días 12-14)**
- [ ] Tabla de resultados
- [ ] Diagrama y diapositivas
