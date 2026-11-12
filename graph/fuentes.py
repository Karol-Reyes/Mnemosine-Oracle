"""Documentos que entran al grafo: cantos (fragmentos.jsonl) y artículos de Wikipedia."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field

from common import config
from ingest.prepare import parrafos, trocear

MAX_CHARS_WIKI = 3000


@dataclass
class Fragmento:
    id: str
    indice: int
    texto: str
    props: dict = field(default_factory=dict)


@dataclass
class Documento:
    id: str
    props: dict
    fragmentos: list[Fragmento]


def cantos() -> list[Documento]:
    grupos: dict[str, list[dict]] = defaultdict(list)
    with open(config.PROCESSED / "fragmentos.jsonl", encoding="utf-8") as f:
        for linea in f:
            r = json.loads(linea)
            grupos[f"{r['libro_id']}_{r['canto']:02d}"].append(r)

    docs = []
    for doc_id, filas in grupos.items():
        r0 = filas[0]
        props = {"fuente": "poema", "libro": r0["libro"], "canto": r0["canto"], "titulo": r0["canto_titulo"]}
        frags = [
            Fragmento(r["id"], i, r["texto"], {"fuente": "poema", "libro": r["libro"], "canto": r["canto"]})
            for i, r in enumerate(sorted(filas, key=lambda r: r["fragmento"]))
        ]
        docs.append(Documento(doc_id, props, frags))
    return sorted(docs, key=lambda d: d.id)


def leer_wiki(ruta) -> tuple[dict, str]:
    cabecera, _, cuerpo = ruta.read_text(encoding="utf-8").partition("\n\n")
    meta = dict(l.split(": ", 1) for l in cabecera.splitlines() if ": " in l)
    return meta, cuerpo


def wikis() -> list[Documento]:
    docs = []
    for ruta in sorted(config.WIKI.glob("*.txt")):
        meta, cuerpo = leer_wiki(ruta)
        titulo = meta.get("titulo", ruta.stem)
        doc_id = "wiki_" + titulo.replace(" ", "_")
        props = {"fuente": "wikipedia", "titulo": titulo, "url": meta.get("url", "")}
        piezas = trocear(parrafos(cuerpo), MAX_CHARS_WIKI)
        frags = [
            Fragmento(f"{doc_id}_{i + 1:03d}", i, t, {"fuente": "wikipedia", "titulo": titulo})
            for i, t in enumerate(piezas)
        ]
        docs.append(Documento(doc_id, props, frags))
    return docs


def todos() -> list[Documento]:
    return wikis() + cantos()
