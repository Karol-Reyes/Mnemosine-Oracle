"""Extracción de entidades y relaciones por fragmento, con caché en data/extracciones/."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from functools import lru_cache

from neo4j_graphrag.components.entity_relation_extractor import fix_invalid_json
from neo4j_graphrag.components.schema import GraphSchema
from neo4j_graphrag.components.types import Neo4jGraph
from neo4j_graphrag.generation.prompts import PromptTemplate

from common import config
from common.llm import con_reintentos
from graph import nombres
from graph.fuentes import Fragmento
from graph.schema import SCHEMA

CACHE = config.DATA / "extracciones"
DESCARTADAS = config.DATA / "relaciones_descartadas.csv"
SIMETRICAS = {"HERMANO_DE", "ESPOSO_DE"}

PROMPT = """Eres un sistema que extrae un grafo de conocimiento de textos de mitología griega en español.

Extrae las entidades (nodos) y las relaciones entre ellas del texto de entrada.
Responde solo con un objeto JSON, sin comillas invertidas ni texto adicional, con este formato:
{{"nodes": [{{"id": "0", "label": "Deidad", "properties": {{"name": "Zeus"}}}}],
"relationships": [{{"type": "HIJO_DE", "start_node_id": "1", "end_node_id": "0", "properties": {{}}}}]}}

Usa solo estos tipos de nodo y de relación, con estos tipos de origen y destino:
{schema}

Reglas:
- Solo entidades con nombre propio o colectivos con nombre (aqueos, troyanos). Nada de pronombres ni de "un guerrero".
- "name" es el nombre propio en español, sin artículo. Usa el nombre griego, no el latino: <<EQUIVALENCIAS>>.
- Si un epíteto designa claramente a alguien (el Pelida = Aquiles), usa su nombre. Si es ambiguo (el Atrida), decide por el contexto o no lo extraigas.
- Solo relaciones que el texto afirma, no las que conoces de otras fuentes.
- Respeta la dirección: en HIJO_DE el origen es el hijo; en MATA_A, quien mata.
- Si no hay nada que extraer, responde {{"nodes": [], "relationships": []}}.

Ejemplo:
{examples}

Texto:
{text}
"""

EJEMPLO = """Texto: "Tetis, la diosa de argentados pies, subió al Olimpo y suplicó a Júpiter que honrara a su hijo, el Pelida, a quien Agamenón había ultrajado."
Salida: {"nodes": [{"id": "0", "label": "Deidad", "properties": {"name": "Tetis"}}, {"id": "1", "label": "Lugar", "properties": {"name": "Olimpo"}}, {"id": "2", "label": "Deidad", "properties": {"name": "Zeus"}}, {"id": "3", "label": "Personaje", "properties": {"name": "Aquiles"}}, {"id": "4", "label": "Personaje", "properties": {"name": "Agamenón"}}],
"relationships": [{"type": "VIAJA_A", "start_node_id": "0", "end_node_id": "1", "properties": {}}, {"type": "HIJO_DE", "start_node_id": "3", "end_node_id": "0", "properties": {}}, {"type": "AYUDA_A", "start_node_id": "0", "end_node_id": "3", "properties": {}}, {"type": "ENFRENTA_A", "start_node_id": "4", "end_node_id": "3", "properties": {}}]}"""

_schema = GraphSchema.model_validate(SCHEMA)
LABELS = {n.label for n in _schema.node_types}
PATRONES = {(p.source, p.relationship, p.target) for p in _schema.patterns}


def schema_texto() -> str:
    lineas = ["Nodos:"] + [f"- {n.label}: {n.description}" for n in _schema.node_types]
    lineas.append("Relaciones (origen -> destino):")
    for r in _schema.relationship_types:
        origenes = sorted({a for a, t, _ in PATRONES if t == r.label})
        destinos = sorted({b for _, t, b in PATRONES if t == r.label})
        lineas.append(f"- {r.label} ({'|'.join(origenes)} -> {'|'.join(destinos)}): {r.description}")
    return "\n".join(lineas)


def plantilla() -> PromptTemplate:
    return PromptTemplate(PROMPT.replace("<<EQUIVALENCIAS>>", nombres.texto_equivalencias()), expected_inputs=[])


def ruta_cache(frag: Fragmento):
    return CACHE / f"{frag.id}.json"


CORRUPTO = "¿½\ufffd"


def corrupto(texto) -> bool:
    return isinstance(texto, str) and any(c in texto for c in CORRUPTO)


def leer_cache(frag: Fragmento) -> Neo4jGraph | None:
    """None si no hay caché o si el LLM devolvió nombres con caracteres corruptos."""
    ruta = ruta_cache(frag)
    if not ruta.exists():
        return None
    grafo = Neo4jGraph.model_validate_json(ruta.read_text(encoding="utf-8"))
    if any(corrupto(n.properties.get("name")) for n in grafo.nodes):
        return None
    return grafo


def en_cache(frag: Fragmento) -> bool:
    return leer_cache(frag) is not None


def extraer(llm, prompt: PromptTemplate, frag: Fragmento, rehacer: bool = False) -> tuple[Neo4jGraph, bool]:
    """Devuelve (grafo crudo del LLM, si hubo llamada). Lanza ValueError si la respuesta no es un grafo válido."""
    if not rehacer:
        previo = leer_cache(frag)
        if previo is not None:
            return previo, False

    texto = prompt.format(text=frag.texto, schema=schema_texto(), examples=EJEMPLO)
    respuesta = con_reintentos(llm.invoke, texto)
    try:
        grafo = Neo4jGraph.model_validate(json.loads(fix_invalid_json(respuesta.content)))
    except Exception as e:
        raise ValueError(f"respuesta inválida del LLM en {frag.id}: {str(e).splitlines()[0]}") from e

    CACHE.mkdir(parents=True, exist_ok=True)
    ruta_cache(frag).write_text(grafo.model_dump_json(indent=1), encoding="utf-8")
    return grafo, True


@lru_cache
def descartadas() -> set[tuple[str, str, str]]:
    """Relaciones que el LLM extrae mal (epítetos leídos como parentesco, etc.)."""
    if not DESCARTADAS.exists():
        return set()
    with open(DESCARTADAS, encoding="utf-8") as f:
        return {(r["origen"], r["relacion"], r["destino"]) for r in csv.DictReader(f)}


@dataclass
class Limpio:
    nodos: dict[str, dict] = field(default_factory=dict)
    relaciones: dict[tuple, dict] = field(default_factory=dict)
    descartados: int = 0


def limpiar(grafo: Neo4jGraph, frag_id: str, acumulado: Limpio | None = None) -> Limpio:
    """Normaliza nombres, aplica el esquema y acumula nodos y relaciones del documento."""
    out = acumulado or Limpio()
    ids: dict[str, tuple[str, str]] = {}

    for n in grafo.nodes:
        nombre = n.properties.get("name")
        if n.label not in LABELS or not isinstance(nombre, str) or corrupto(nombre):
            out.descartados += 1
            continue
        nombre, label = nombres.canonico(nombre, n.label)
        if not nombre:
            out.descartados += 1
            continue
        clave = f"{label}|{nombre}"
        ids[n.id] = (clave, label)
        nodo = out.nodos.setdefault(clave, {"clave": clave, "name": nombre, "label": label, "props": {}, "fragmentos": []})
        extras = {k: v for k, v in n.properties.items() if k not in ("name", "clave", "embedding") and isinstance(v, (str, int, float))}
        nodo["props"].update(extras)
        if frag_id not in nodo["fragmentos"]:
            nodo["fragmentos"].append(frag_id)

    for r in grafo.relationships:
        a, b = ids.get(r.start_node_id), ids.get(r.end_node_id)
        if not a or not b or a[0] == b[0] or (a[1], r.type, b[1]) not in PATRONES \
                or (a[0].split("|", 1)[1], r.type, b[0].split("|", 1)[1]) in descartadas():
            out.descartados += 1
            continue
        if r.type in SIMETRICAS and b[0] < a[0]:
            a, b = b, a
        rel = out.relaciones.setdefault((a[0], r.type, b[0]), {"a": a[0], "tipo": r.type, "b": b[0], "fragmentos": []})
        if frag_id not in rel["fragmentos"]:
            rel["fragmentos"].append(frag_id)

    return out
