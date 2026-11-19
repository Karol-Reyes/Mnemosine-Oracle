# Pruebas

Todos los comandos se corren desde la raíz del repo, con el entorno activado.

## 1. Entorno

```powershell
python check_setup.py
```

Resultado:

```
== Datos
[ok] 16 cantos en data/raw
[ok] 53 artículos en data/wikipedia
[ok] fragmentos.jsonl
== Neo4j
[ok] Neo4j 5.26.x
[ok] APOC
== LLM (gemini)
[ok] LLM gemini (gemini-3.5-flash-lite) responde
== Embeddings
[ok] Embeddings paraphrase-multilingual-MiniLM-L12-v2: dimensión 384

Todo listo.
```

## 2. Preparar los cantos

```powershell
python -m ingest.prepare
```

Resultado:

```
Ilíada  canto  1 ... fragmentos
...
Odisea  canto 12 ... fragmentos
Listo: 450 fragmentos en data/processed/fragmentos.jsonl
```

## 3. Plan de construcción del grafo

```powershell
python -m graph.build --plan
```

Resultado:

```
69 documentos, 664 fragmentos, 0 llamadas al LLM pendientes.
```

## 4. Reconstruir el grafo desde la caché

```powershell
python -m graph.build --reset
```

Resultado:

```
Neo4j vaciado.
+ iliada_01: ... entidades, ... relaciones, ... descartes
...
Listo en ... s: 69 documentos cargados, 0 llamadas al LLM.
```

## 5. Revisar el grafo

```powershell
python -m graph.revisar
```

Resultado:

```
== Documentos
  poema        16   450
  wikipedia    53   214
== Entidades por tipo
== Relaciones por tipo
== Más conectadas
```

## 6. Índices en Neo4j

```cypher
SHOW INDEXES YIELD name, state WHERE name IN ['fragmentos_embedding', 'entidades_nombre'] RETURN name, state
```

Resultado:

```
fragmentos_embedding   ONLINE
entidades_nombre       ONLINE
```

## 7. Total de fragmentos

```cypher
MATCH (c:Chunk) RETURN count(c) AS fragmentos
```

Resultado:

```
664
```

## 8. RAG normal: hijo de Zeus que muere

```powershell
python -m rag.baseline "¿Qué hijo de Zeus muere en la Ilíada y quién lo mata?"
```

Resultado:

```
Fragmentos solo de Wikipedia (Atenea, Helena, Hades, Egisto).
El contexto provisto no menciona qué hijo de Zeus muere en la Ilíada ni quién lo mata.
```

## 9. GraphRAG: hijo de Zeus que muere

```powershell
python -m graphrag.retriever "¿Qué hijo de Zeus muere en la Ilíada y quién lo mata?"
```

Resultado:

```
Sarpedón, hijo de Zeus, muere a manos de Patroclo (Ilíada, canto XVI).
```

## 10. GraphRAG: quién mata a Héctor

```powershell
python -m graphrag.retriever "¿Quién mata a Héctor y en qué canto?"
```

Resultado:

```
Aquiles mata a Héctor (Ilíada, canto XXII).
```

## 11. GraphRAG: abuelo de Telémaco

```powershell
python -m graphrag.retriever "¿Quién es el padre de Telémaco y quién es su abuelo paterno?"
```

Resultado:

```
El padre de Telémaco es Odiseo y su abuelo paterno es Laertes (Odisea I, IV, XI).
```

## 12. GraphRAG: personajes de la Ilíada en el Hades

```powershell
python -m graphrag.retriever "¿Qué personajes de la Ilíada encuentra Ulises en el Hades?"
```

Resultado:

```
Odiseo encuentra en el inframundo las almas de Aquiles, Patroclo, Antíloco y Áyax (Odisea, canto XI).
```

## 13. GraphRAG: equivalente romano de Ares

```powershell
python -m graphrag.retriever "¿Cuál es el equivalente romano de Ares y qué hace en cada poema?"
```

Resultado:

```
El equivalente romano de Ares es Marte. En la Ilíada apoya a los troyanos y se enfrenta a Atenea (Ilíada XXI). En la Odisea se narran sus amores con Afrodita (Odisea VIII).
```

## 14. Recuperación sin LLM

```powershell
python -m eval.run --solo-recuperacion
```

Resultado:

```
Recall de evidencia: RAG 0.27, GraphRAG 0.83
Guardado en eval/resultados/recuperacion.md
```

## 15. Evaluación completa

```powershell
python -m eval.run
```

Resultado:

```
Puntaje del juez: RAG 0.23, GraphRAG 0.82
Recall de evidencia: RAG 0.27, GraphRAG 0.83
Guardado en eval/resultados/respuestas.json y eval/resultados/resumen.md
```

## 16. Repetir una pregunta

```powershell
python -m eval.run --pregunta q14 --modo graphrag --rehacer
```

Resultado:

```
[graphrag|q14] ¿Qué hijo de Zeus muere en la Ilíada y quién lo mata?
Sarpedón, hijo de Zeus, muere a manos de Patroclo (Ilíada, canto XVI).
  juez: 1.0
```

## 17. Agente: pregunta de relaciones

```powershell
python -m agent.grafo "¿Qué hijo de Zeus muere en la Ilíada y quién lo mata?"
```

Resultado:

```
- clasificar: graphrag
- recuperar: graphrag, 5 fragmentos
- responder

Sarpedón, hijo de Zeus, muere a manos de Patroclo (Ilíada, canto XVI).
```

## 18. Agente: pasaje de un canto

```powershell
python -m agent.grafo "¿Qué pasa con Escila y Caribdis en la Odisea?"
```

Resultado:

```
- clasificar: rag
- recuperar: rag, 5 fragmentos
- responder

Escila devora a seis compañeros de Odiseo y Caribdis sorbe el agua del mar tres veces al día (Odisea, canto XII).
```

## 19. Agente: fuera de tema

```powershell
python -m agent.grafo "¿Cuál es la capital de Francia?"
```

Resultado:

```
- clasificar: fuera
- fuera de tema

Solo puedo responder sobre la Ilíada, la Odisea y la mitología griega relacionada.
```

## 20. Modelos desde cero

```powershell
python -m scratch_models.comparar
```

Resultado:

```
--- n-gramas ---
   unigrama   contexto 0   perplejidad ...
   bigrama    contexto 1   perplejidad ...
--- mini red ---
modelo       contexto   perplejidad
```

## 21. Interfaz

```powershell
python -m app.main
```

Resultado:

```
* Running on local URL:  http://127.0.0.1:7860
```
