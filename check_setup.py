"""Comprueba que el entorno está listo: .env, Neo4j (+APOC), Gemini y embeddings.

Uso (desde la raíz del repo):
    python check_setup.py                 # todo
    python check_setup.py --sin-llm       # sin llamar a Gemini
    python check_setup.py --sin-embeddings
"""
from __future__ import annotations

import argparse
import sys

from common import config
from common.llm import con_reintentos, crear_llm

OK, FALLA = "[ok]", "[x] "


def revisar_neo4j() -> bool:
    from neo4j import GraphDatabase

    try:
        with GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)) as driver:
            driver.verify_connectivity()
            with driver.session() as s:
                version = s.run("CALL dbms.components() YIELD versions RETURN versions[0] AS v").single()["v"]
                print(f"{OK} Neo4j {version} en {config.NEO4J_URI}")
                try:
                    apoc = s.run("RETURN apoc.version() AS v").single()["v"]
                    print(f"{OK} APOC {apoc}")
                except Exception:
                    print(f"{FALLA} APOC no está instalado: revisa NEO4J_PLUGINS en docker-compose.yml")
                    return False
                n = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
                print(f"     nodos actuales en la base: {n}")
        return True
    except Exception as e:
        print(f"{FALLA} No conecta a Neo4j: {e}")
        print("     ¿Está corriendo?  docker compose up -d   (espera ~30 s la primera vez)")
        return False


def revisar_gemini() -> bool:
    """Comprueba el LLM configurado (LLM_PROVIDER: gemini, ollama u openai)."""
    proveedor = config.LLM_PROVIDER.strip().lower()
    if proveedor == "gemini" and not config.GEMINI_API_KEY:
        print(f"{FALLA} Falta GEMINI_API_KEY en .env  (https://aistudio.google.com/apikey)")
        return False
    if proveedor == "openai" and not config.LLM_API_KEY:
        print(f"{FALLA} Falta LLM_API_KEY en .env (y LLM_BASE_URL si el proveedor no es OpenAI)")
        return False
    try:
        llm = crear_llm()
        r = con_reintentos(llm.invoke, "¿Quién es el padre de Atenea? Responde con una sola palabra.")
        print(f"{OK} LLM {proveedor} ({config.LLM_MODEL}) responde: {r.content.strip()[:60]}")
        return True
    except Exception as e:
        print(f"{FALLA} El LLM ({proveedor}, {config.LLM_MODEL}) falló: {e}")
        return False


def revisar_embeddings() -> bool:
    try:
        from neo4j_graphrag.embeddings import SentenceTransformerEmbeddings

        emb = SentenceTransformerEmbeddings(model=config.EMBEDDING_MODEL)
        v = emb.embed_query("Atenea ayuda a Ulises")
        print(f"{OK} Embeddings {config.EMBEDDING_MODEL}: dimensión {len(v)}")
        return True
    except Exception as e:
        print(f"{FALLA} Embeddings fallaron: {e}")
        return False


def revisar_datos() -> bool:
    cantos = list((config.RAW / "iliada").glob("*.txt")) + list((config.RAW / "odisea").glob("*.txt"))
    wikis = [p for p in config.WIKI.glob("*.txt")] if config.WIKI.exists() else []
    frags = config.PROCESSED / "fragmentos.jsonl"
    print(f"{OK if cantos else FALLA} {len(cantos)} cantos en data/raw")
    print(f"{OK if wikis else '[ ] '} {len(wikis)} artículos en data/wikipedia"
          + ("" if wikis else "  -> python -m ingest.fetch_wikipedia"))
    print(f"{OK if frags.exists() else '[ ] '} fragmentos.jsonl"
          + ("" if frags.exists() else "  -> python -m ingest.prepare"))
    return bool(cantos)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-llm", action="store_true")
    ap.add_argument("--sin-embeddings", action="store_true")
    args = ap.parse_args()

    print("== Datos");       r = [revisar_datos()]
    print("== Neo4j");       r.append(revisar_neo4j())
    if not args.sin_llm:
        print(f"== LLM ({config.LLM_PROVIDER})");  r.append(revisar_gemini())
    if not args.sin_embeddings:
        print("== Embeddings (la primera vez descarga el modelo, ~470 MB)")
        r.append(revisar_embeddings())
    print("\nTodo listo." if all(r) else "\nHay pendientes arriba.")
    return 0 if all(r) else 1


if __name__ == "__main__":
    sys.exit(main())
