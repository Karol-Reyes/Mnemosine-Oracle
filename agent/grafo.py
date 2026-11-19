"""Agente en LangGraph: elige el retriever, responde y, si el RAG normal no alcanza, reintenta con GraphRAG.

clasificar -> (fuera de tema | rag | graphrag) -> recuperar -> responder -> revisar -> (fin | recuperar)

Uso:
  python -m agent.grafo "¿Qué hijo de Zeus muere en la Ilíada y quién lo mata?"
"""
from __future__ import annotations

import argparse
import sys
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from common.llm import con_reintentos
from common.respuesta import Recuperacion, responder
from graphrag.retriever import GraphRAG
from rag.baseline import RAG

RUTAS = ("graphrag", "rag", "fuera")

PROMPT_RUTA = """Clasifica la pregunta para un asistente sobre la Ilíada y la Odisea. Responde con una sola palabra:
- graphrag: relaciones entre personajes o dioses (parentesco, quién mata, quién ayuda), listas de entidades,
  o información que cruza los dos poemas o los poemas con la mitología.
- rag: un pasaje o episodio concreto de un solo canto.
- fuera: no trata de mitología griega ni de los poemas.

Pregunta: {pregunta}
Ruta:"""

NO_ALCANZA = ("no alcanza", "no menciona", "no contiene", "no proporciona", "no detalla", "no es posible",
              "no hay información", "no tengo información")

FUERA = "Solo puedo responder sobre la Ilíada, la Odisea y la mitología griega relacionada."


class Estado(TypedDict, total=False):
    pregunta: str
    ruta: str
    recuperacion: Recuperacion
    respuesta: str
    pasos: list[str]
    reintentar: bool


class Agente:
    def __init__(self, driver, embedder, llm):
        self.llm = llm
        self.sistemas = {"rag": RAG(driver, embedder), "graphrag": GraphRAG(driver, embedder)}
        self.grafo = self._construir()

    def _construir(self):
        g = StateGraph(Estado)
        g.add_node("clasificar", self.clasificar)
        g.add_node("recuperar", self.recuperar)
        g.add_node("responder", self.responder)
        g.add_node("revisar", self.revisar)
        g.add_node("fuera", self.fuera)
        g.add_edge(START, "clasificar")
        g.add_conditional_edges("clasificar", lambda e: "fuera" if e["ruta"] == "fuera" else "recuperar")
        g.add_edge("recuperar", "responder")
        g.add_edge("responder", "revisar")
        g.add_conditional_edges("revisar", lambda e: "recuperar" if e["reintentar"] else END)
        g.add_edge("fuera", END)
        return g.compile()

    def clasificar(self, e: Estado) -> Estado:
        texto = con_reintentos(self.llm.invoke, PROMPT_RUTA.format(pregunta=e["pregunta"])).content.lower()
        ruta = next((r for r in RUTAS if r in texto), "graphrag")
        return {"ruta": ruta, "pasos": [f"clasificar: {ruta}"]}

    def recuperar(self, e: Estado) -> Estado:
        rec = self.sistemas[e["ruta"]](e["pregunta"])
        return {"recuperacion": rec, "pasos": e["pasos"] + [f"recuperar: {e['ruta']}, {len(rec.fragmentos)} fragmentos"]}

    def responder(self, e: Estado) -> Estado:
        return {"respuesta": responder(self.llm, e["recuperacion"]), "pasos": e["pasos"] + ["responder"]}

    def revisar(self, e: Estado) -> Estado:
        if e["ruta"] == "rag" and any(f in e["respuesta"].lower() for f in NO_ALCANZA):
            return {"ruta": "graphrag", "reintentar": True,
                    "pasos": e["pasos"] + ["revisar: el contexto no alcanza, se pasa a graphrag"]}
        return {"reintentar": False}

    def fuera(self, e: Estado) -> Estado:
        return {"respuesta": FUERA, "pasos": e["pasos"] + ["fuera de tema"]}

    def __call__(self, pregunta: str) -> Estado:
        return self.grafo.invoke({"pregunta": pregunta, "pasos": []})


def crear_agente() -> Agente:
    from common.llm import crear_llm
    from graph.neo4j_io import conectar
    from rag.baseline import cargar_embedder

    return Agente(conectar(), cargar_embedder(), crear_llm())


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pregunta")
    args = p.parse_args()
    estado = crear_agente()(args.pregunta)
    print("\n".join(f"- {p}" for p in estado["pasos"]))
    print("\n" + estado["respuesta"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
