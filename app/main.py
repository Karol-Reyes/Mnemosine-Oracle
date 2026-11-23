"""Interfaz de Mnemosine Oracle en Gradio.

Pestañas: preguntar (agente, RAG o GraphRAG), comparar RAG y GraphRAG lado a lado, y modelos desde cero.

Uso:
  python -m app.main
"""
from __future__ import annotations

from functools import lru_cache

import gradio as gr

from app.formato import formatear
from common.respuesta import responder

EJEMPLOS = [
    "¿Qué hijo de Zeus muere en la Ilíada y quién lo mata?",
    "¿Quién es el padre de Telémaco y quién es su abuelo paterno?",
    "¿Qué personajes de la Ilíada encuentra Ulises en el Hades?",
    "¿Qué pasa con Escila y Caribdis en la Odisea?",
]

MAX_PREGUNTA = 500
ORDENES = {"Bigrama": 2, "Trigrama": 3, "4-grama": 4}


@lru_cache(maxsize=1)
def agente():
    # se crea al primer uso: si Neo4j está apagado, la pestaña de modelos desde cero sigue funcionando
    from agent.grafo import crear_agente

    return crear_agente()


def aviso(e: Exception) -> str:
    modulo, nombre = type(e).__module__, type(e).__name__
    if modulo.startswith("neo4j.") or isinstance(e, ConnectionError):
        return "**Neo4j no responde.** Levántalo con `docker compose up -d` y vuelve a intentar."
    if "LLM" in nombre or "genai" in modulo or "google" in modulo:
        return "**El LLM no respondió** (cuota, clave o conexión). Espera un momento y vuelve a intentar."
    return f"**Error:** {nombre}: {str(e)[:200]}"


def validar(pregunta: str) -> str | None:
    if not pregunta:
        return "Escribe una pregunta."
    if len(pregunta) > MAX_PREGUNTA:
        return f"La pregunta es muy larga ({len(pregunta)} caracteres; máximo {MAX_PREGUNTA})."
    return None


def preguntar(pregunta: str, modo: str):
    pregunta = pregunta.strip()
    if problema := validar(pregunta):
        return problema, "", ""
    try:
        a = agente()
        if modo == "Agente":
            e = a(pregunta)
            rec = e.get("recuperacion")
            return formatear(e["respuesta"]), "\n".join(f"- {p}" for p in e["pasos"]), rec.contexto if rec else ""
        rec = a.sistemas[modo.lower()](pregunta)
        return formatear(responder(a.llm, rec)), f"- {modo}", rec.contexto
    except Exception as e:
        return aviso(e), "", ""


def comparar(pregunta: str):
    pregunta = pregunta.strip()
    if problema := validar(pregunta):
        return [problema, "", "", ""]
    salida = []
    for modo in ("rag", "graphrag"):
        try:
            a = agente()
            rec = a.sistemas[modo](pregunta)
            salida += [formatear(responder(a.llm, rec)), rec.contexto]
        except Exception as e:
            salida += [aviso(e), ""]
    return salida


@lru_cache(maxsize=len(ORDENES))
def ngrama(orden: int):
    from scratch_models.corpus import datos
    from scratch_models.ngramas import ModeloNgramas

    entrenamiento, _, vocab = datos()
    modelo = ModeloNgramas(orden=orden)
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


def generar(inicio: str, palabras: int, orden: str, temperatura: float) -> str:
    try:
        modelo = ngrama(ORDENES[orden])
    except FileNotFoundError as e:
        return str(e)
    return modelo.generar(inicio.strip() or "canta oh", int(palabras), float(temperatura))


def vecinos(palabra: str) -> str:
    from scratch_models.mini_red import vecinos as buscar

    palabra = palabra.strip().lower()
    if not palabra:
        return "Escribe una palabra."
    modelo, vocab = mini_red()
    if modelo is None:
        return "Primero entrena la red: python -m scratch_models.mini_red"
    encontrados = buscar(modelo, vocab, palabra)
    return ", ".join(encontrados) or "La palabra no está en el vocabulario."


with gr.Blocks(title="Mnemosine Oracle") as demo:
    gr.Markdown("# Mnemosine Oracle\nPreguntas sobre la Ilíada y la Odisea (traducción de Segalá y Estalella).")

    with gr.Tab("Preguntar"):
        pregunta = gr.Textbox(label="Pregunta", lines=2, max_length=MAX_PREGUNTA)
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
        pregunta_c = gr.Textbox(label="Pregunta", lines=2, max_length=MAX_PREGUNTA)
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
        gr.Markdown("### N-grama: texto generado\n"
                    "Elige solo entre continuaciones vistas en los poemas. Con más contexto las frases son más "
                    "coherentes, pero copian más del original.")
        with gr.Row():
            inicio = gr.Textbox(value="canta oh", label="Inicio")
            n = gr.Slider(5, 50, value=20, step=1, label="Palabras")
        with gr.Row():
            orden = gr.Radio(list(ORDENES), value="Trigrama", label="Contexto")
            temperatura = gr.Slider(0.2, 1.5, value=0.8, step=0.1, label="Temperatura",
                                    info="Baja: lo más frecuente. Alta: más variado y menos coherente.")
        generado = gr.Textbox(label="Texto", lines=3)
        gr.Button("Generar").click(generar, [inicio, n, orden, temperatura], generado)

        gr.Markdown("### Mini red: palabras vecinas en el espacio de embeddings")
        palabra = gr.Textbox(value="aquiles", label="Palabra")
        cercanas = gr.Textbox(label="Vecinas")
        gr.Button("Buscar").click(vecinos, palabra, cercanas)


if __name__ == "__main__":
    demo.launch()
