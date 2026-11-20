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
vocabulario: 4811
entrenamiento: 82442 tokens   validacion: 9161
los dos modelos se evaluan desde la posicion 2 de validacion

--- n-gramas ---
   unigrama   contexto 0   perplejidad    315.0
   bigrama    contexto 1   perplejidad    223.5
   trigrama   contexto 2   perplejidad    485.8
   4-grama    contexto 3   perplejidad    693.2

--- mini red ---
parametros: 945,035

 epoca   perdida_tr   perdida_va  perplejidad
     1       6.2287       5.2365        188.0  <- mejor
     2       5.2595       5.0276        152.6  <- mejor
     3       4.9107       4.9288        138.2  <- mejor
     4       4.6351       4.8885        132.8  <- mejor
     5       4.4017       4.8570        128.6  <- mejor
     6       4.1984       4.8671        129.9
     7       4.0197       4.8825        132.0
     8       3.8583       4.8822        131.9

se vuelve a la epoca 5, que fue la mejor

modelo        contexto   perplejidad
mini red             2         128.6
bigrama              1         223.5
unigrama             0         315.0
trigrama             2         485.8
4-grama              3         693.2

frente al mejor n-grama (bigrama): baja la perplejidad 42 %
con el MISMO contexto de 2 palabras, contra el trigrama: 3.8 veces mejor (486 -> 129)
```

La perdida de entrenamiento sigue bajando en las epocas 6 a 8 pero la de validacion sube: ahi empieza a sobreajustar, y por eso se guarda el estado de la epoca 5.

## 20b. Verificar las 20 preguntas

```powershell
python -m eval.verificar
```

Resultado (ultimas lineas):

```
[ok     ] q20 (control)  3/3 nombres juntos
            odisea_12: «Asi, pues, se han llevado a cumplimiento todas estas cosas. Oye ahora lo que voy a decir [...]»

20 de 20 tienen un pasaje con los nombres juntos

ojo: esto acota, no verifica. el pasaje de arriba hay que leerlo y
confirmar que dice lo que la respuesta esperada afirma.
```

El script encuentra un pasaje para las 20, pero eso solo acota: hay que leerlo. Leyendolos quedaron **12 en `verificada: true`** (4 de cada tipo). Las otras 8 tienen el pasaje guardado en `preguntas.json` pero no alcanza: las de conjunto (q01, q10) piden varios cantos, y en otras el parrafo nombra a los dos personajes sin afirmar la relacion que la respuesta dice.

## 20c. Recall del baseline sin Neo4j

```powershell
python -m rag.indice
python -m eval.correr
```

Resultado:

```
total:
alguno@3      8
todos@3       2
alguno@5     10
todos@5       3
alguno@10    13
todos@10      6

sesgo de fuente:
   wikipedia es el 32 % del indice (214 de 664 fragmentos)
   pero se lleva el 70 % de los puestos recuperados (70 de 100)
   en 9 de las 20 preguntas se lleva los 5 y los poemas quedan en cero
```

## 21. Interfaz

```powershell
python -m app.main
```

Resultado:

```
* Running on local URL:  http://127.0.0.1:7860
```
