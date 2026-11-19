"""Primera corrida de las 20 preguntas contra el RAG normal (el baseline).

Mide **recuperacion**, no redaccion: si el retriever trajo los documentos que
la propia pregunta declara como su evidencia. Se puede correr sin Neo4j y sin
cuota de API, y es el numero contra el que hay que comparar GraphRAG.

Dos medidas, y la segunda es la que importa para la tesis del proyecto:

- `alguno`: trajo al menos un documento de la evidencia.
- `todos`:  trajo **todos** los documentos de la evidencia.

Las preguntas de tipo `cruce` necesitan dos cantos a la vez (Hefesto esta en
Iliada XVIII y en Odisea VIII). Un indice plano ordena por parecido con la
pregunta, y los fragmentos del mismo canto se parecen entre si, asi que tiende a
traer cinco pedazos del mismo lado. Ahi es donde el grafo deberia ganar.

Uso:  python -m eval.correr
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata

import pandas as pd

from common.config import ROOT
from rag.indice import Indice, cita

PREGUNTAS = ROOT / "eval" / "preguntas.json"
SALIDA = ROOT / "eval" / "resultados" / "rag_baseline.json"
KS = (3, 5, 10)


def plano(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def docs_esperados(evidencia: list[str], todos_los_docs: set[str]) -> set[str]:
    """Convierte la evidencia escrita a mano en ids de documento.

    Los ids son los de `graph.fuentes`: `iliada_22`, `odisea_11`, `wiki_Ares`.
    `equivalencias` no es un documento, es un csv, asi que se ignora para esta
    medida.
    """
    esperados: set[str] = set()

    for item in evidencia:
        clave = plano(item)
        if "todos los cantos" in clave:
            esperados |= {d for d in todos_los_docs if not d.startswith("wiki_")}
        elif clave == "wikis":
            esperados |= {d for d in todos_los_docs if d.startswith("wiki_")}
        elif clave == "equivalencias":
            continue
        elif m := re.match(r"(iliada|odisea)\s+(\d+)", clave):
            esperados.add(f"{m.group(1)}_{int(m.group(2)):02d}")
        elif clave in ("iliada", "odisea"):
            esperados |= {d for d in todos_los_docs if d.startswith(clave + "_")}

    return esperados


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    preguntas = json.loads(PREGUNTAS.read_text(encoding="utf-8"))
    indice = Indice()
    todos_los_docs = {fila["doc"] for fila in indice.filas}

    # las de evidencia difusa ("todos los cantos", "wikis") aceptan cualquiera de
    # un conjunto grande, asi que `todos` no significa lo mismo ahi. se marcan.
    filas, detalle = [], []
    for q in preguntas:
        esperados = docs_esperados(q["evidencia"], todos_los_docs)
        difusa = len(esperados) > 3 or not esperados

        fila = {"id": q["id"], "tipo": q["tipo"], "difusa": difusa,
                "esperados": len(esperados)}
        recuperados_5 = []
        for k in KS:
            docs = [f["doc"] for f, _ in indice.buscar(q["pregunta"], k=k)]
            if k == 5:
                recuperados_5 = docs
            fila[f"alguno@{k}"] = bool(esperados & set(docs))
            fila[f"todos@{k}"] = bool(esperados) and esperados <= set(docs)
        filas.append(fila)
        detalle.append({"id": q["id"], "esperados": sorted(esperados),
                        "recuperados@5": recuperados_5})

    tabla = pd.DataFrame(filas)

    print("por tipo de pregunta (de las 20):")
    columnas = [f"{m}@{k}" for k in KS for m in ("alguno", "todos")]
    print(tabla.groupby("tipo")[columnas].sum().to_string())
    print()
    print("total:")
    print(tabla[columnas].sum().to_string())
    print()

    # las de evidencia precisa son las que miden de verdad el `todos`
    precisas = tabla[~tabla["difusa"]]
    print(f"solo las {len(precisas)} preguntas con evidencia precisa (<=3 documentos):")
    print(precisas[columnas].sum().to_string())
    print()

    # El sesgo de fuente. Es el hallazgo mas util de esta corrida: explica casi
    # todos los fallos de arriba y es la razon concreta para pasar al grafo.
    en_indice = sum(1 for f in indice.filas if f["fuente"] == "wikipedia")
    wiki = sum(
        1
        for q in preguntas
        for f, _ in indice.buscar(q["pregunta"], k=5)
        if f["fuente"] == "wikipedia"
    )
    total = 5 * len(preguntas)
    arrasadas = sum(
        1
        for q in preguntas
        if all(f["fuente"] == "wikipedia" for f, _ in indice.buscar(q["pregunta"], k=5))
    )

    print("sesgo de fuente:")
    print(f"   wikipedia es el {100 * en_indice / len(indice.filas):.0f} % del indice "
          f"({en_indice} de {len(indice.filas)} fragmentos)")
    print(f"   pero se lleva el {100 * wiki / total:.0f} % de los puestos "
          f"recuperados ({wiki} de {total})")
    print(f"   en {arrasadas} de las {len(preguntas)} preguntas se lleva los 5 y "
          f"los poemas quedan en cero")
    print()

    print("donde falla el `todos@5` (las de cruce son el caso de interes):")
    for fila, det in zip(filas, detalle):
        if not fila["todos@5"] and not fila["difusa"]:
            print(f"   {fila['id']} ({fila['tipo']}) esperaba {det['esperados']}")
            print(f"        trajo {det['recuperados@5']}")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps({"k": list(KS), "por_pregunta": filas, "detalle": detalle},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print()
    print(f"guardado en {SALIDA.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
