"""Escritura del grafo en Neo4j. Todo usa MERGE: cargar dos veces el mismo documento no duplica nada."""
from __future__ import annotations

from neo4j import Driver, GraphDatabase

from common import config
from graph.extraccion import Limpio
from graph.fuentes import Documento

VECTOR_INDEX = "fragmentos_embedding"
FULLTEXT_INDEX = "entidades_nombre"


def conectar() -> Driver:
    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    driver.verify_connectivity()
    return driver


def preparar(driver: Driver, dimensiones: int) -> None:
    for q in [
        "CREATE CONSTRAINT entidad_clave IF NOT EXISTS FOR (e:__Entity__) REQUIRE e.clave IS UNIQUE",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT documento_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
        f"CREATE VECTOR INDEX {VECTOR_INDEX} IF NOT EXISTS FOR (c:Chunk) ON c.embedding "
        f"OPTIONS {{indexConfig: {{`vector.dimensions`: {int(dimensiones)}, `vector.similarity_function`: 'cosine'}}}}",
        f"CREATE FULLTEXT INDEX {FULLTEXT_INDEX} IF NOT EXISTS FOR (e:__Entity__) ON EACH [e.name]",
    ]:
        driver.execute_query(q)


def borrar_todo(driver: Driver) -> None:
    driver.execute_query("MATCH (n) DETACH DELETE n")


def documentos_cargados(driver: Driver) -> set[str]:
    filas, _, _ = driver.execute_query("MATCH (d:Document) RETURN d.id AS id")
    return {f["id"] for f in filas}


def borrar_documento(driver: Driver, doc_id: str) -> None:
    """Quita el documento, sus fragmentos y lo que solo venía de ellos."""
    filas, _, _ = driver.execute_query("MATCH (c:Chunk {documento: $id}) RETURN collect(c.id) AS ids", id=doc_id)
    ids = filas[0]["ids"]
    driver.execute_query(
        """
        MATCH (:__Entity__)-[r]->(:__Entity__)
        WHERE any(x IN r.fragmentos WHERE x IN $ids)
        SET r.fragmentos = [x IN r.fragmentos WHERE NOT x IN $ids]
        SET r.menciones = size(r.fragmentos)
        """,
        ids=ids,
    )
    driver.execute_query("MATCH (:__Entity__)-[r]->(:__Entity__) WHERE r.menciones = 0 DELETE r")
    driver.execute_query("MATCH (c:Chunk {documento: $id}) DETACH DELETE c", id=doc_id)
    driver.execute_query("MATCH (d:Document {id: $id}) DETACH DELETE d", id=doc_id)
    driver.execute_query("MATCH (e:__Entity__) WHERE NOT (e)-[:FROM_CHUNK]->() DETACH DELETE e")


def escribir_documento(driver: Driver, doc: Documento, embeddings: list[list[float]], grafo: Limpio) -> None:
    chunks = [
        {"id": f.id, "props": {**f.props, "text": f.texto, "index": f.indice, "documento": doc.id}, "embedding": e}
        for f, e in zip(doc.fragmentos, embeddings)
    ]
    driver.execute_query(
        """
        MERGE (d:Document {id: $id})
        SET d += $props
        WITH d
        UNWIND $chunks AS row
        MERGE (c:Chunk {id: row.id})
        SET c += row.props, c.embedding = row.embedding
        MERGE (c)-[:FROM_DOCUMENT]->(d)
        """,
        id=doc.id, props=doc.props, chunks=chunks,
    )
    pares = [[a.id, b.id] for a, b in zip(doc.fragmentos, doc.fragmentos[1:])]
    driver.execute_query(
        "UNWIND $pares AS p MATCH (a:Chunk {id: p[0]}), (b:Chunk {id: p[1]}) MERGE (a)-[:NEXT_CHUNK]->(b)",
        pares=pares,
    )
    driver.execute_query(
        """
        UNWIND $nodos AS row
        MERGE (e:__Entity__ {clave: row.clave})
        SET e += row.props, e.name = row.name
        WITH e, row
        CALL apoc.create.addLabels(e, [row.label]) YIELD node
        WITH node, row
        UNWIND row.fragmentos AS fid
        MATCH (c:Chunk {id: fid})
        MERGE (node)-[:FROM_CHUNK]->(c)
        """,
        nodos=list(grafo.nodos.values()),
    )
    driver.execute_query(
        """
        UNWIND $rels AS row
        MATCH (a:__Entity__ {clave: row.a}), (b:__Entity__ {clave: row.b})
        CALL apoc.merge.relationship(a, row.tipo, {}, {}, b, {}) YIELD rel
        WITH rel, row, coalesce(rel.fragmentos, []) AS previos
        SET rel.fragmentos = previos + [x IN row.fragmentos WHERE NOT x IN previos]
        SET rel.menciones = size(rel.fragmentos)
        """,
        rels=list(grafo.relaciones.values()),
    )
