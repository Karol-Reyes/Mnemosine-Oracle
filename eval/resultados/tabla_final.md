# Tabla final de resultados

Generada por `python -m eval.tabla_final` a partir de `respuestas.json` y `scratch_models.json`.
Respuestas y juez: `gemini-3.5-flash-lite`. 20 preguntas.

## 1. RAG vs GraphRAG

Puntaje del juez: 1 correcta, 0.5 parcial, 0 incorrecta. Recall: fracción de los cantos de la evidencia que llegaron
al contexto como fragmentos de texto (solo cuenta las preguntas que tienen cantos concretos como evidencia:
18 de 20; `q01` y `q10` no). s: segundos de recuperación + respuesta.

| Tipo | n | RAG: puntaje | GraphRAG: puntaje | RAG: recall | GraphRAG: recall | RAG: s | GraphRAG: s |
|---|---|---|---|---|---|---|---|
| cruce | 8 | 0.25 | 0.75 | 0.26 | 0.86 | 4.62 | 5.30 |
| hibrida | 8 | 0.06 | 0.81 | 0.14 | 0.71 | 4.96 | 5.30 |
| control | 4 | 0.50 | 1.00 | 0.50 | 1.00 | 4.95 | 5.00 |
| total | 20 | 0.23 | 0.82 | 0.27 | 0.83 | 4.83 | 5.24 |

| Resultado del juez | RAG | GraphRAG |
|---|---|---|
| Correcta (1) | 4 | 14 |
| Parcial (0.5) | 1 | 5 |
| Incorrecta (0) | 15 | 1 |

## 2. Modelos desde cero

Perplejidad sobre los mismos objetivos de validación (vocabulario de 4811 palabras); menor es mejor.

| Modelo | Contexto (palabras) | Perplejidad |
|---|---|---|
| mini red | 2 | 128.6 |
| bigrama | 1 | 223.5 |
| unigrama | 0 | 315.0 |
| trigrama | 2 | 485.8 |
| 4-grama | 3 | 693.2 |

La mini red baja la perplejidad un 42 % frente al mejor n-grama (bigrama). Contra el
trigrama, que ve el mismo contexto de 2 palabras, es 3.8 veces mejor.
El n-grama de orden alto empeora porque, con un corpus tan pequeño, casi ninguna secuencia de 3 o 4 palabras se repite.

## 3. Lectura

- GraphRAG gana en los tres tipos de pregunta. La mayor brecha está en las híbridas (poema + Wikipedia o dos saltos
  en el grafo), donde el RAG normal casi no acierta: trae fragmentos de Wikipedia que no responden.
- Incluso en las preguntas de control (un solo canto), donde el RAG debería bastar, GraphRAG puntúa más.
- El costo de GraphRAG es pequeño: unos 0.4 s más por pregunta.
- Limitaciones: el LLM responde y juzga (el puntaje varía entre corridas, el recall es más estable), son solo
  20 preguntas, y GraphRAG corta la lista de hechos en `q09` y `q10` (hijos de Zeus) y mezcla relaciones mal
  extraídas en `q08` y `q15`.
