"""Construye el grafo en Neo4j a partir de las wikis y los cantos.

Uso:
  python -m graph.build --plan                      cuántas llamadas al LLM faltan
  python -m graph.build --solo wikis                carga las wikis
  python -m graph.build --doc iliada_06 --doc odisea_09
  python -m graph.build                             carga todo lo que falte
  python -m graph.build --doc iliada_06 --rehacer   vuelve a extraer con el LLM (tras cambiar el prompt)
  python -m graph.build --recargar                  reescribe desde la caché, sin LLM (tras cambiar equivalencias)
  python -m graph.build --reset                     vacía Neo4j y vuelve a cargar desde la caché

Cada extracción se guarda en data/extracciones/; si la corrida se corta, al repetirla no se vuelve a pagar.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
import time

from graph import fuentes
from graph.extraccion import en_cache, extraer, limpiar, plantilla


def seleccionar(args) -> list[fuentes.Documento]:
    docs = {"wikis": fuentes.wikis, "poemas": fuentes.cantos}.get(args.solo, fuentes.todos)()
    if args.doc:
        docs = [d for d in docs if any(fnmatch.fnmatch(d.id, p) for p in args.doc)]
    return docs


def pendientes(docs, rehacer: bool) -> int:
    return sum(1 for d in docs for f in d.fragmentos if rehacer or not en_cache(f))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--solo", choices=["wikis", "poemas"])
    p.add_argument("--doc", action="append", help="id o patrón: iliada_06, odisea_*, wiki_Zeus")
    p.add_argument("--plan", action="store_true", help="solo muestra lo que falta")
    p.add_argument("--rehacer", action="store_true", help="ignora la caché y vuelve a llamar al LLM")
    p.add_argument("--recargar", action="store_true", help="reescribe documentos ya cargados")
    p.add_argument("--reset", action="store_true", help="vacía Neo4j antes de cargar")
    p.add_argument("--max-llamadas", type=int, default=0, help="se detiene tras N llamadas (0 = sin límite)")
    p.add_argument("--pausa", type=float, default=4.0, help="segundos entre llamadas (cuota por minuto)")
    args = p.parse_args()

    docs = seleccionar(args)
    if not docs:
        print("Ningún documento coincide con la selección.")
        return 1
    n_frag = sum(len(d.fragmentos) for d in docs)
    n_llm = pendientes(docs, args.rehacer)
    print(f"{len(docs)} documentos, {n_frag} fragmentos, {n_llm} llamadas al LLM pendientes.")
    if args.plan:
        for d in docs:
            faltan = sum(1 for f in d.fragmentos if args.rehacer or not en_cache(f))
            print(f"  {d.id:<28} {len(d.fragmentos):>3} fragmentos  {faltan:>3} por extraer")
        return 0

    from sentence_transformers import SentenceTransformer

    from common import config
    from graph import neo4j_io

    driver = neo4j_io.conectar()
    modelo_emb = SentenceTransformer(config.EMBEDDING_MODEL)
    if args.reset:
        neo4j_io.borrar_todo(driver)
        print("Neo4j vaciado.")
    neo4j_io.preparar(driver, modelo_emb.get_sentence_embedding_dimension())
    cargados = neo4j_io.documentos_cargados(driver)

    llm = prompt = None
    llamadas = 0
    escritos = incompletos = 0
    t0 = time.time()

    for d in docs:
        ya = d.id in cargados
        if ya and not (args.rehacer or args.recargar):
            print(f"= {d.id}: ya cargado")
            continue

        grafo = None
        faltan = 0
        for f in d.fragmentos:
            nuevo_llm = args.rehacer or not en_cache(f)
            if nuevo_llm:
                if args.max_llamadas and llamadas >= args.max_llamadas:
                    faltan += 1
                    continue
                if llm is None:
                    from common.llm import crear_llm
                    llm, prompt = crear_llm(), plantilla()
                if llamadas:
                    time.sleep(args.pausa)
            try:
                crudo, llamo = extraer(llm, prompt, f, rehacer=args.rehacer)
            except ValueError as e:
                llamadas += 1
                print(f"  ! {e}")
                faltan += 1
                continue
            except Exception as e:
                print(f"\nSe detuvo en {f.id}: {e}")
                print("Lo extraído quedó en caché. Vuelve a correr el mismo comando para continuar.")
                driver.close()
                return 2
            llamadas += llamo
            grafo = limpiar(crudo, f.id, grafo)
            if llamo:
                print(f"  {f.id}: {len(crudo.nodes)} nodos, {len(crudo.relationships)} relaciones")

        if faltan:
            incompletos += 1
            print(f"~ {d.id}: faltan {faltan} fragmentos, no se carga todavía")
            continue

        embeddings = modelo_emb.encode([f.texto for f in d.fragmentos], batch_size=16).tolist()
        if ya:
            neo4j_io.borrar_documento(driver, d.id)
        neo4j_io.escribir_documento(driver, d, embeddings, grafo)
        escritos += 1
        print(f"+ {d.id}: {len(grafo.nodos)} entidades, {len(grafo.relaciones)} relaciones, {grafo.descartados} descartes")

    driver.close()
    print(f"\nListo en {time.time() - t0:.0f} s: {escritos} documentos cargados, {llamadas} llamadas al LLM.")
    if incompletos:
        print(f"{incompletos} documentos quedaron incompletos; vuelve a correr el comando para terminarlos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
