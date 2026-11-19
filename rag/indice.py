"""Indice vectorial del RAG normal, que es el baseline contra GraphRAG.

Usa **los mismos documentos y el mismo modelo de embeddings** que el grafo
(`graph.fuentes.todos()` y `config.EMBEDDING_MODEL`). Es a proposito: si el
baseline viera otro corpus u otro modelo, la comparacion no diria nada sobre el
grafo, diria que un indice tiene mejores datos que el otro.

No necesita Neo4j ni el LLM: son embeddings locales y una busqueda por coseno
sobre una matriz en memoria. Con 700 fragmentos no hace falta nada mas.

Uso:  python -m rag.indice
"""
from __future__ import annotations

import json

import numpy as np

from common import config
from graph.fuentes import todos

INDICE = config.PROCESSED / "rag_indice.npz"
META = config.PROCESSED / "rag_meta.jsonl"

_MODELO = None


def modelo():
    """Carga el modelo una sola vez. Se importa aqui adentro porque
    sentence-transformers tarda en levantar torch."""
    global _MODELO
    if _MODELO is None:
        from sentence_transformers import SentenceTransformer

        _MODELO = SentenceTransformer(config.EMBEDDING_MODEL)
    return _MODELO


def fragmentos() -> list[dict]:
    """Todos los fragmentos, con lo que hace falta para citarlos."""
    filas = []
    for doc in todos():
        for frag in doc.fragmentos:
            filas.append({
                "id": frag.id,
                "doc": doc.id,
                "texto": frag.texto,
                **doc.props,
            })
    return filas


def construir() -> None:
    filas = fragmentos()
    print(f"fragmentos: {len(filas)}")
    poemas = sum(1 for f in filas if f["fuente"] == "poema")
    print(f"   de los poemas: {poemas}   de wikipedia: {len(filas) - poemas}")

    vectores = modelo().encode(
        [f["texto"] for f in filas],
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=True,
    )

    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(INDICE, vectores=vectores)
    with open(META, "w", encoding="utf-8") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")

    print(f"guardado: {INDICE.name} ({vectores.shape}) y {META.name}")


class Indice:
    """Busqueda por similitud coseno sobre los fragmentos."""

    def __init__(self) -> None:
        if not INDICE.exists():
            raise FileNotFoundError(
                f"No existe {INDICE}. Corre primero:  python -m rag.indice"
            )
        self.vectores = np.load(INDICE)["vectores"]
        with open(META, encoding="utf-8") as f:
            self.filas = [json.loads(l) for l in f]

    def buscar(self, pregunta: str, k: int = 5) -> list[tuple[dict, float]]:
        # los vectores ya salen normalizados, asi que el producto punto ES el coseno
        consulta = modelo().encode(pregunta, normalize_embeddings=True)
        similitudes = self.vectores @ consulta
        mejores = np.argsort(-similitudes)[:k]
        return [(self.filas[i], float(similitudes[i])) for i in mejores]


def cita(fila: dict) -> str:
    """De donde salio el fragmento, para ponerlo al lado de la respuesta."""
    if fila["fuente"] == "poema":
        return f"{fila['libro']} canto {fila['canto']} ({fila['titulo']})"
    return f"Wikipedia: {fila['titulo']}"


if __name__ == "__main__":
    construir()

    indice = Indice()
    print()
    for pregunta in ("¿Quién mata a Héctor?", "¿De quién es hijo Ulises?"):
        print(pregunta)
        for fila, puntaje in indice.buscar(pregunta, k=3):
            print(f"   {puntaje:.3f}  {cita(fila)}")
        print()
