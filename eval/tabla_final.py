"""Tabla final de resultados (Fase 5): junta las metricas del proyecto en un solo archivo.

Solo lee lo que ya esta guardado en eval/resultados/ (no llama al LLM ni a Neo4j):
  - respuestas.json      puntaje del juez, recall, tiempo y los fragmentos que vio cada sistema
  - scratch_models.json  perplejidad del n-grama y la mini red

El recall se recalcula desde los fragmentos guardados en respuestas.json (el contexto
que de verdad recibio el LLM), asi que es coherente con el puntaje del juez.

Uso:  python -m eval.tabla_final
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

RESULTADOS = Path(__file__).resolve().parent / "resultados"
PREGUNTAS = Path(__file__).resolve().parent / "preguntas.json"
SALIDA = RESULTADOS / "tabla_final.md"

MODOS = ("rag", "graphrag")
NOMBRES = {"rag": "RAG", "graphrag": "GraphRAG"}
EVIDENCIA = re.compile(r"^(Ilíada|Odisea) (\d+)$")
FRAGMENTO = re.compile(r"^(iliada|odisea)_(\d+)_\d+$")
LIBRO = {"iliada": "Ilíada", "odisea": "Odisea"}
ORDEN_TIPOS = ("cruce", "hibrida", "control", "total")


def cantos_evidencia(pregunta: dict) -> set[tuple[str, int]]:
    return {(m[1], int(m[2])) for e in pregunta["evidencia"] if (m := EVIDENCIA.match(e.strip()))}


def cantos_recuperados(fragmentos: list[str]) -> set[tuple[str, int]]:
    return {(LIBRO[m[1]], int(m[2])) for f in fragmentos if (m := FRAGMENTO.match(f))}


def recall(pregunta: dict, fragmentos: list[str]) -> float | None:
    esperados = cantos_evidencia(pregunta)
    if not esperados:
        return None
    return len(esperados & cantos_recuperados(fragmentos)) / len(esperados)


def media(valores: list) -> float | None:
    v = [x for x in valores if x is not None]
    return sum(v) / len(v) if v else None


def fmt(x: float | None, decimales: int = 2) -> str:
    return "-" if x is None else f"{x:.{decimales}f}"


def main() -> None:
    preguntas = json.loads(PREGUNTAS.read_text(encoding="utf-8"))
    datos = json.loads((RESULTADOS / "respuestas.json").read_text(encoding="utf-8"))
    modelos = json.loads((RESULTADOS / "scratch_models.json").read_text(encoding="utf-8"))

    acum: dict[str, dict[str, dict[str, list]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    conteo: dict[str, dict[float, int]] = {m: defaultdict(int) for m in MODOS}
    discrepancias = []
    for p in preguntas:
        for modo in MODOS:
            d = datos[f"{modo}|{p['id']}"]
            r = recall(p, d["fragmentos"])
            if (r is None) != (d.get("recall") is None) or (r is not None and abs(r - d["recall"]) > 1e-9):
                discrepancias.append(f"{modo}|{p['id']}: recalculado {r}, guardado {d.get('recall')}")
            for tipo in (p["tipo"], "total"):
                acum[tipo][modo]["puntaje"].append(d.get("puntaje"))
                acum[tipo][modo]["recall"].append(r)
                acum[tipo][modo]["tiempo"].append(d.get("tiempo_s"))
            if d.get("puntaje") is not None:
                conteo[modo][d["puntaje"]] += 1

    n_por_tipo = {t: sum(1 for p in preguntas if t == "total" or p["tipo"] == t) for t in ORDEN_TIPOS}
    n_recall = {t: sum(1 for p in preguntas if (t == "total" or p["tipo"] == t) and cantos_evidencia(p))
                for t in ORDEN_TIPOS}

    filas = ["| Tipo | n | RAG: puntaje | GraphRAG: puntaje | RAG: recall | GraphRAG: recall | RAG: s | GraphRAG: s |",
             "|---|---|---|---|---|---|---|---|"]
    for tipo in ORDEN_TIPOS:
        m = acum[tipo]
        celdas = [fmt(media(m[modo][campo])) for campo in ("puntaje", "recall", "tiempo") for modo in MODOS]
        filas.append(f"| {tipo} | {n_por_tipo[tipo]} | " + " | ".join(celdas) + " |")

    jueces = ["| Resultado del juez | RAG | GraphRAG |", "|---|---|---|"]
    for valor, nombre in ((1, "Correcta (1)"), (0.5, "Parcial (0.5)"), (0, "Incorrecta (0)")):
        jueces.append(f"| {nombre} | {conteo['rag'][valor]} | {conteo['graphrag'][valor]} |")

    por_pp = sorted(modelos["resultados"], key=lambda f: f["perplejidad"])
    red = next(f["perplejidad"] for f in por_pp if f["modelo"] == "mini red")
    mejor_ngrama = min(f["perplejidad"] for f in por_pp if f["modelo"] != "mini red")
    perpl = ["| Modelo | Contexto (palabras) | Perplejidad |", "|---|---|---|"]
    for f in por_pp:
        perpl.append(f"| {f['modelo']} | {f['contexto']} | {f['perplejidad']:.1f} |")

    texto = f"""# Tabla final de resultados

Generada por `python -m eval.tabla_final` a partir de `respuestas.json` y `scratch_models.json`.
Respuestas y juez: `gemini-3.5-flash-lite`. {len(preguntas)} preguntas.

## 1. RAG vs GraphRAG

Puntaje del juez: 1 correcta, 0.5 parcial, 0 incorrecta. Recall: fracción de los cantos de la evidencia que llegaron
al contexto como fragmentos de texto (solo cuenta las preguntas que tienen cantos concretos como evidencia:
{n_recall['total']} de {n_por_tipo['total']}; `q01` y `q10` no). s: segundos de recuperación + respuesta.

{chr(10).join(filas)}

{chr(10).join(jueces)}

## 2. Modelos desde cero

Perplejidad sobre los mismos objetivos de validación (vocabulario de {modelos['vocabulario']} palabras); menor es mejor.

{chr(10).join(perpl)}

La mini red baja la perplejidad un {100 * (1 - red / mejor_ngrama):.0f} % frente al mejor n-grama (bigrama). Contra el
trigrama, que ve el mismo contexto de 2 palabras, es {next(f['perplejidad'] for f in por_pp if f['modelo'] == 'trigrama') / red:.1f} veces mejor.
El n-grama de orden alto empeora porque, con un corpus tan pequeño, casi ninguna secuencia de 3 o 4 palabras se repite.

## 3. Lectura

- GraphRAG gana en los tres tipos de pregunta. La mayor brecha está en las híbridas (poema + Wikipedia o dos saltos
  en el grafo), donde el RAG normal casi no acierta: trae fragmentos de Wikipedia que no responden.
- Incluso en las preguntas de control (un solo canto), donde el RAG debería bastar, GraphRAG puntúa más.
- El costo de GraphRAG es pequeño: unos 0.4 s más por pregunta.
- Limitaciones: el LLM responde y juzga (el puntaje varía entre corridas, el recall es más estable), son solo
  20 preguntas, y GraphRAG corta la lista de hechos en `q09` y `q10` (hijos de Zeus) y mezcla relaciones mal
  extraídas en `q08` y `q15`.
"""
    SALIDA.write_text(texto, encoding="utf-8")
    print(texto)
    if discrepancias:
        print("AVISO: recall recalculado distinto del guardado en:")
        print("\n".join(discrepancias))
    else:
        print("Recall recalculado coincide con el guardado en respuestas.json.")


if __name__ == "__main__":
    main()
