# Resultados: RAG vs GraphRAG

Generado: 2026-11-19 14:29. LLM: gemini / gemini-3.5-flash-lite.

Puntaje del juez: 1 correcta, 0.5 parcial, 0 incorrecta. Recall: fracción de los cantos de la evidencia que llegaron al contexto. s: segundos de recuperación + respuesta.

## Por tipo

| Tipo | n | RAG: puntaje | GraphRAG: puntaje | RAG: recall | GraphRAG: recall | RAG: s | GraphRAG: s |
|---|---|---|---|---|---|---|---|
| cruce | 8 | 0.25 | 0.75 | 0.26 | 0.86 | 4.62 | 5.30 |
| hibrida | 8 | 0.06 | 0.81 | 0.14 | 0.71 | 4.96 | 5.30 |
| control | 4 | 0.50 | 1.00 | 0.50 | 1.00 | 4.95 | 5.00 |
| total | 20 | 0.23 | 0.82 | 0.27 | 0.83 | 4.83 | 5.24 |

## Por pregunta

| Pregunta | Tipo | RAG | GraphRAG | RAG: recall | GraphRAG: recall |
|---|---|---|---|---|---|
| q01 | cruce | 0 | 1 | - | - |
| q02 | cruce | 0 | 1 | 0.00 | 1.00 |
| q03 | cruce | 0 | 0 | 0.00 | 1.00 |
| q04 | cruce | 0 | 1 | 0.00 | 0.50 |
| q05 | cruce | 0 | 0.5 | 0.33 | 1.00 |
| q06 | cruce | 1 | 0.5 | 0.50 | 1.00 |
| q07 | cruce | 0 | 1 | 0.00 | 1.00 |
| q08 | cruce | 1 | 1 | 1.00 | 0.50 |
| q09 | hibrida | 0 | 0.5 | 0.00 | 1.00 |
| q10 | hibrida | 0 | 0.5 | - | - |
| q11 | hibrida | 0 | 1 | 0.00 | 1.00 |
| q12 | hibrida | 0 | 1 | 0.00 | 1.00 |
| q13 | hibrida | 0 | 1 | 0.00 | 0.50 |
| q14 | hibrida | 0 | 1 | 0.00 | 1.00 |
| q15 | hibrida | 0 | 0.5 | 0.00 | 0.50 |
| q16 | hibrida | 0.5 | 1 | 1.00 | 0.00 |
| q17 | control | 0 | 1 | 0.00 | 1.00 |
| q18 | control | 1 | 1 | 1.00 | 1.00 |
| q19 | control | 1 | 1 | 0.00 | 1.00 |
| q20 | control | 0 | 1 | 1.00 | 1.00 |
