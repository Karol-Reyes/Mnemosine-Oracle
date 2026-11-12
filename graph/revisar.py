"""Revisión del grafo cargado: conteos, entidades sueltas, posibles duplicados y vecinos de algunas entidades.

Uso:  python -m graph.revisar [--entidad Héctor --entidad Penélope]
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from graph import nombres
from graph.neo4j_io import conectar

ENTIDADES_DEFECTO = ["Zeus", "Aquiles", "Odiseo"]


def tabla(filas, columnas):
    for f in filas:
        print("  " + "  ".join(str(f[c]).ljust(22) for c in columnas))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--entidad", action="append")
    args = p.parse_args()
    driver = conectar()
    q = lambda cypher, **kw: driver.execute_query(cypher, **kw)[0]

    print("== Documentos")
    tabla(q("MATCH (d:Document)<-[:FROM_DOCUMENT]-(c:Chunk) "
            "RETURN d.fuente AS fuente, count(DISTINCT d) AS documentos, count(c) AS fragmentos"),
          ["fuente", "documentos", "fragmentos"])

    print("\n== Entidades por tipo")
    tabla(q("MATCH (e:__Entity__) UNWIND labels(e) AS tipo WITH tipo WHERE NOT tipo STARTS WITH '__' "
            "RETURN tipo, count(*) AS n ORDER BY n DESC"), ["tipo", "n"])

    print("\n== Relaciones por tipo")
    tabla(q("MATCH (:__Entity__)-[r]->(:__Entity__) "
            "RETURN type(r) AS tipo, count(r) AS n, sum(r.menciones) AS menciones ORDER BY n DESC"),
          ["tipo", "n", "menciones"])

    print("\n== Más conectadas")
    tabla(q("MATCH (e:__Entity__) RETURN e.name AS nombre, [l IN labels(e) WHERE NOT l STARTS WITH '__'][0] AS tipo, "
            "COUNT { (e)--(:__Entity__) } AS grado ORDER BY grado DESC LIMIT 15"), ["nombre", "tipo", "grado"])

    sueltas = q("MATCH (e:__Entity__) WHERE NOT (e)--(:__Entity__) RETURN e.name AS nombre ORDER BY nombre")
    print(f"\n== Sin relaciones con otras entidades: {len(sueltas)}")
    print("  " + ", ".join(f["nombre"] for f in sueltas[:40]))

    print("\n== Fuera de entidades.csv (las más mencionadas)")
    catalogo = set(nombres.catalogo())
    fuera = [f for f in q("MATCH (e:__Entity__)-[:FROM_CHUNK]->(c) RETURN e.name AS nombre, e.clave AS clave, "
                          "count(c) AS fragmentos ORDER BY fragmentos DESC") if f["nombre"] not in catalogo]
    tabla(fuera[:20], ["clave", "fragmentos"])

    grupos = defaultdict(list)
    for f in q("MATCH (e:__Entity__) RETURN e.clave AS clave, e.name AS nombre, COUNT { (e)-[:FROM_CHUNK]->() } AS n"):
        grupos[nombres.plano(f["nombre"])].append(f)
    repetidos = sorted((g for g in grupos.values() if len(g) > 1), key=lambda g: -sum(f["n"] for f in g))
    print(f"\n== Mismo nombre con otra tilde o tipo: {len(repetidos)} (si es el mismo ente, unifícalo en entidades.csv o equivalencias.csv)")
    for g in repetidos[:30]:
        print("  " + "  |  ".join(f"{f['clave']} ({f['n']})" for f in g))

    for nombre in args.entidad or ENTIDADES_DEFECTO:
        print(f"\n== Vecinos de {nombre}")
        filas = q("MATCH (e:__Entity__ {name: $n})-[r]-(o:__Entity__) "
                  "RETURN CASE WHEN startNode(r) = e THEN '->' ELSE '<-' END AS dir, type(r) AS tipo, "
                  "o.name AS otro, r.menciones AS menciones ORDER BY tipo, menciones DESC", n=nombre)
        for f in filas[:30]:
            a, b = (nombre, f["otro"]) if f["dir"] == "->" else (f["otro"], nombre)
            print(f"  {a} -{f['tipo']}-> {b}  ({f['menciones']})")
        if not filas:
            print("  (sin relaciones)")

    driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
