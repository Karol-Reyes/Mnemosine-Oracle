"""Interfaz de Mnemosine Oracle en Gradio.

Pestañas: preguntar (agente, RAG o GraphRAG), comparar RAG y GraphRAG lado a lado, y modelos desde cero.

Uso:
  python -m app.main
"""
from __future__ import annotations

import random
from functools import lru_cache

import gradio as gr

from agent.grafo import crear_agente
from app.formato import formatear
from common.respuesta import responder

EJEMPLOS = [
    "¿Qué hijo de Zeus muere en la Ilíada y quién lo mata?",
    "¿Quién es el padre de Telémaco y quién es su abuelo paterno?",
    "¿Qué personajes de la Ilíada encuentra Ulises en el Hades?",
    "¿Qué pasa con Escila y Caribdis en la Odisea?",
]

agente = crear_agente()


def preguntar(pregunta: str, modo: str):
    if not pregunta.strip():
        return "", "", ""
    if modo == "Agente":
        e = agente(pregunta)
        rec = e.get("recuperacion")
        return formatear(e["respuesta"]), "\n".join(f"- {p}" for p in e["pasos"]), rec.contexto if rec else ""
    rec = agente.sistemas[modo.lower()](pregunta)
    return formatear(responder(agente.llm, rec)), f"- {modo}", rec.contexto


def comparar(pregunta: str):
    salida = []
    for modo in ("rag", "graphrag"):
        rec = agente.sistemas[modo](pregunta)
        salida += [formatear(responder(agente.llm, rec)), rec.contexto]
    return salida


@lru_cache(maxsize=1)
def ngrama():
    from scratch_models.corpus import datos
    from scratch_models.ngramas import ModeloNgramas

    entrenamiento, _, vocab = datos()
    modelo = ModeloNgramas()
    modelo.entrenar(entrenamiento, vocab)
    return modelo


@lru_cache(maxsize=1)
def mini_red():
    import torch

    from scratch_models.mini_red import CHECKPOINTS, MiniRed

    ruta = CHECKPOINTS / "mini_red.pt"
    if not ruta.exists():
        return None, None
    guardado = torch.load(ruta)
    modelo = MiniRed(len(guardado["vocab"]))
    modelo.load_state_dict(guardado["estado"])
    return modelo, guardado["vocab"]


def generar(inicio: str, palabras: int) -> str:
    random.seed(42)
    return ngrama().generar(inicio.strip().lower() or "canta oh", int(palabras))


def vecinos(palabra: str) -> str:
    from scratch_models.mini_red import vecinos as buscar

    modelo, vocab = mini_red()
    if modelo is None:
        return "Primero entrena la red: python -m scratch_models.mini_red"
    encontrados = buscar(modelo, vocab, palabra.strip().lower())
    return ", ".join(encontrados) or "La palabra no está en el vocabulario."


with gr.Blocks(title="Mnemosine Oracle") as demo:
    gr.Markdown("# Mnemosine Oracle\nPreguntas sobre la Ilíada y la Odisea (traducción de Segalá y Estalella).")

    with gr.Tab("Preguntar"):
        pregunta = gr.Textbox(label="Pregunta", lines=2)
        modo = gr.Radio(["Agente", "RAG", "GraphRAG"], value="Agente", label="Sistema")
        boton = gr.Button("Responder", variant="primary")
        respuesta = gr.Markdown()
        with gr.Accordion("Pasos del agente", open=False):
            pasos = gr.Markdown()
        with gr.Accordion("Contexto recuperado", open=False):
            contexto = gr.Textbox(lines=20, show_label=False)
        gr.Examples(EJEMPLOS, inputs=pregunta)
        boton.click(preguntar, [pregunta, modo], [respuesta, pasos, contexto])
        pregunta.submit(preguntar, [pregunta, modo], [respuesta, pasos, contexto])

    with gr.Tab("Comparar"):
        pregunta_c = gr.Textbox(label="Pregunta", lines=2)
        boton_c = gr.Button("Comparar", variant="primary")
        with gr.Row():
            with gr.Column():
                gr.Markdown("### RAG")
                resp_rag = gr.Markdown()
                ctx_rag = gr.Textbox(label="Contexto", lines=15)
            with gr.Column():
                gr.Markdown("### GraphRAG")
                resp_graph = gr.Markdown()
                ctx_graph = gr.Textbox(label="Contexto", lines=15)
        gr.Examples(EJEMPLOS, inputs=pregunta_c)
        boton_c.click(comparar, pregunta_c, [resp_rag, ctx_rag, resp_graph, ctx_graph])

    with gr.Tab("Modelos desde cero"):
        gr.Markdown("### N-grama: texto generado")
        with gr.Row():
            inicio = gr.Textbox(value="canta oh", label="Inicio")
            n = gr.Slider(5, 50, value=20, step=1, label="Palabras")
        generado = gr.Textbox(label="Texto", lines=3)
        gr.Button("Generar").click(generar, [inicio, n], generado)

        gr.Markdown("### Mini red: palabras vecinas en el espacio de embeddings")
        palabra = gr.Textbox(value="aquiles", label="Palabra")
        cercanas = gr.Textbox(label="Vecinas")
        gr.Button("Buscar").click(vecinos, palabra, cercanas)


if __name__ == "__main__":
    demo.launch()
