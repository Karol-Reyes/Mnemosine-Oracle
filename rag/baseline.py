"""RAG normal: los k fragmentos más parecidos a la pregunta según el índice vectorial de Neo4j.

Uso:
  python -m rag.baseline "¿Quién mata a Héctor?"
  python -m rag.baseline "¿Quién mata a Héctor?" --solo-contexto     sin llamar al LLM
"""
from __future__ import annotations

import argparse
import sys

from neo4j import Driver

from common.respuesta import Recuperacion
from graph.neo4j_io import VECTOR_INDEX

K = 5

CAMPOS = """node.id AS id, node.fuente AS fuente, node.libro AS libro, node.canto AS canto,
           node.titulo AS titulo, node.text AS texto, score"""


def cargar_embedder():
    from sentence_transformers import SentenceTransformer

    from common import config

    return SentenceTransformer(config.EMBEDDING_MODEL)


def busqueda_vectorial(driver: Driver, embedding: list[float], k: int) -> list[dict]:
    filas, _, _ = driver.execute_query(
        f"CALL db.index.vector.queryNodes($indice, $k, $emb) YIELD node, score RETURN {CAMPOS} ORDER BY score DESC",
        indice=VECTOR_INDEX, k=k, emb=embedding,
    )
    return [dict(f) for f in filas]


class RAG:
    modo = "rag"

    def __init__(self, driver: Driver, embedder, k: int = K):
        self.driver = driver
        self.embedder = embedder
        self.k = k

    def __call__(self, pregunta: str) -> Recuperacion:
        embedding = self.embedder.encode(pregunta).tolist()
        return Recuperacion(self.modo, pregunta, busqueda_vectorial(self.driver, embedding, self.k))


def main(sistema=None, descripcion: str = __doc__) -> int:
    p = argparse.ArgumentParser(description=descripcion, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pregunta")
    p.add_argument("--solo-contexto", action="store_true", help="muestra lo recuperado sin llamar al LLM")
    args = p.parse_args()

    from graph.neo4j_io import conectar

    driver = conectar()
    sistema = (sistema or RAG)(driver, cargar_embedder())
    rec = sistema(args.pregunta)
    print(rec.contexto)
    if not args.solo_contexto:
        from common.llm import crear_llm
        from common.respuesta import responder

        print("\n" + "=" * 60 + "\n" + responder(crear_llm(), rec))
    driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
