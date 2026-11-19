"""Corre las preguntas de eval/preguntas.json con RAG y GraphRAG y compara los resultados.

Uso:
  python -m eval.run --solo-recuperacion      sin LLM: ¿llegan al contexto los cantos de la evidencia?
  python -m eval.run                          respuestas + juez LLM (se retoma si se corta)
  python -m eval.run --pregunta q14 --modo graphrag --rehacer
  python -m eval.run --sin-juez               solo genera respuestas
  python -m eval.run --resumen                rehace resumen.md con lo guardado

Salidas en eval/resultados/: respuestas.json (todo lo guardado) y resumen.md (tablas).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime

from common import config
from common.respuesta import Recuperacion, romano

PREGUNTAS = config.ROOT / "eval" / "preguntas.json"
RESULTADOS = config.ROOT / "eval" / "resultados"
RESPUESTAS = RESULTADOS / "respuestas.json"
RESUMEN = RESULTADOS / "resumen.md"
MODOS = ["rag", "graphrag"]
ABREV = {"Ilíada": "Il.", "Odisea": "Od."}
EVIDENCIA = re.compile(r"^(Ilíada|Odisea) (\d+)$")

JUEZ = """Evalúa la respuesta de un sistema a una pregunta sobre la Ilíada y la Odisea, comparándola con la referencia.

Pregunta: {pregunta}
Referencia: {referencia}
Respuesta del sistema: {respuesta}

Puntaje:
1 = tiene los datos esenciales de la referencia y ningún error importante.
0.5 = correcta en parte: falta una parte de lo esencial o tiene un error menor.
0 = incorrecta, no responde o dice que no tiene la información.
Los nombres latinos o griegos de un mismo personaje (Ulises/Odiseo, Júpiter/Zeus) cuentan como iguales.
No penalices datos extra si son correctos.

Responde solo con JSON: {{"puntaje": 1, "razon": "una frase"}}"""


def cargar_preguntas() -> list[dict]:
    return json.loads(PREGUNTAS.read_text(encoding="utf-8"))


def cantos_evidencia(pregunta: dict) -> set[tuple[str, int]]:
    """'Ilíada 18' -> ('Ilíada', 18). Ignora 'wikis', 'todos los cantos', 'Odisea' sin número, etc."""
    return {(m[1], int(m[2])) for e in pregunta["evidencia"] if (m := EVIDENCIA.match(e.strip()))}


def recall(pregunta: dict, rec: Recuperacion) -> float | None:
    esperados = cantos_evidencia(pregunta)
    if not esperados:
        return None
    return len(esperados & rec.cantos()) / len(esperados)


def leer_guardado() -> dict:
    return json.loads(RESPUESTAS.read_text(encoding="utf-8")) if RESPUESTAS.exists() else {}


def guardar(datos: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    RESPUESTAS.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def juzgar(llm, pregunta: dict, respuesta: str) -> tuple[float | None, str]:
    from common.llm import con_reintentos

    texto = JUEZ.format(pregunta=pregunta["pregunta"], referencia=pregunta["respuesta_esperada"], respuesta=respuesta)
    salida = con_reintentos(llm.invoke, texto).content
    m = re.search(r"\{.*\}", salida, re.S)
    try:
        datos = json.loads(m.group(0))
        puntaje = float(datos["puntaje"])
        assert puntaje in (0, 0.5, 1)
        return puntaje, str(datos.get("razon", ""))
    except Exception:
        return None, f"respuesta del juez no válida: {salida[:120]}"


def ordenar(por_tipo: dict) -> list:
    return sorted(por_tipo.items(), key=lambda kv: kv[0] == "total")


def media(valores: list) -> str:
    v = [x for x in valores if x is not None]
    return f"{sum(v) / len(v):.2f}" if v else "-"


def fmt_cantos(cantos) -> str:
    return ", ".join(f"{ABREV[l]} {romano(c)}" for l, c in sorted(cantos)) or "-"


def tabla_recuperacion(preguntas: list[dict], recs: dict[str, dict[str, Recuperacion]]) -> str:
    lineas = ["| Pregunta | Tipo | Evidencia | RAG: recall | RAG: cantos | GraphRAG: recall | GraphRAG: cantos |",
              "|---|---|---|---|---|---|---|"]
    por_tipo: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for p in preguntas:
        fila = [p["id"], p["tipo"], fmt_cantos(cantos_evidencia(p))]
        for modo in MODOS:
            rec = recs[modo][p["id"]]
            r = recall(p, rec)
            por_tipo[p["tipo"]][modo].append(r)
            por_tipo["total"][modo].append(r)
            fila += ["-" if r is None else f"{r:.2f}", fmt_cantos(rec.cantos())]
        lineas.append("| " + " | ".join(fila) + " |")
    lineas += ["", "| Tipo | RAG: recall medio | GraphRAG: recall medio |", "|---|---|---|"]
    for tipo, valores in ordenar(por_tipo):
        lineas.append(f"| {tipo} | {media(valores['rag'])} | {media(valores['graphrag'])} |")
    return "\n".join(lineas)


def escribir_resumen(preguntas: list[dict], datos: dict) -> str:
    por_tipo: dict[str, dict[str, dict[str, list]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    filas = ["| Pregunta | Tipo | RAG | GraphRAG | RAG: recall | GraphRAG: recall |", "|---|---|---|---|---|---|"]
    for p in preguntas:
        celdas = [p["id"], p["tipo"]]
        recalls = []
        for modo in MODOS:
            d = datos.get(f"{modo}|{p['id']}", {})
            for tipo in (p["tipo"], "total"):
                por_tipo[tipo][modo]["puntaje"].append(d.get("puntaje"))
                por_tipo[tipo][modo]["recall"].append(d.get("recall"))
                por_tipo[tipo][modo]["tiempo"].append(d.get("tiempo_s"))
            celdas.append("-" if d.get("puntaje") is None else f"{d['puntaje']:g}")
            recalls.append("-" if d.get("recall") is None else f"{d['recall']:.2f}")
        filas.append("| " + " | ".join(celdas + recalls) + " |")

    tipos = ["| Tipo | n | RAG: puntaje | GraphRAG: puntaje | RAG: recall | GraphRAG: recall | RAG: s | GraphRAG: s |",
             "|---|---|---|---|---|---|---|---|"]
    for tipo, m in ordenar(por_tipo):
        n = len(m["rag"]["puntaje"])
        tipos.append(f"| {tipo} | {n} | " + " | ".join(
            media(m[modo][campo]) for campo in ("puntaje", "recall", "tiempo") for modo in MODOS
        ) + " |")

    texto = (f"# Resultados: RAG vs GraphRAG\n\nGenerado: {datetime.now():%Y-%m-%d %H:%M}. "
             f"LLM: {config.LLM_PROVIDER} / {config.LLM_MODEL}.\n\n"
             "Puntaje del juez: 1 correcta, 0.5 parcial, 0 incorrecta. Recall: fracción de los cantos de la "
             "evidencia que llegaron al contexto. s: segundos de recuperación + respuesta.\n\n"
             "## Por tipo\n\n" + "\n".join(tipos) + "\n\n## Por pregunta\n\n" + "\n".join(filas) + "\n")
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    RESUMEN.write_text(texto, encoding="utf-8")
    return texto


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modo", choices=MODOS, action="append")
    p.add_argument("--pregunta", action="append", help="id de la pregunta: q01, q14...")
    p.add_argument("--solo-recuperacion", action="store_true", help="no llama al LLM")
    p.add_argument("--sin-juez", action="store_true")
    p.add_argument("--rehacer", action="store_true", help="vuelve a generar lo ya guardado")
    p.add_argument("--resumen", action="store_true", help="solo reescribe resumen.md")
    p.add_argument("--pausa", type=float, default=4.0, help="segundos entre llamadas al LLM")
    args = p.parse_args()

    preguntas = cargar_preguntas()
    if args.pregunta:
        preguntas = [q for q in preguntas if q["id"] in args.pregunta]
    modos = args.modo or MODOS

    if args.resumen:
        print(escribir_resumen(cargar_preguntas(), leer_guardado()))
        return 0

    from graph.neo4j_io import conectar
    from graphrag.retriever import GraphRAG
    from rag.baseline import RAG, cargar_embedder

    driver = conectar()
    embedder = cargar_embedder()
    sistemas = {"rag": RAG(driver, embedder), "graphrag": GraphRAG(driver, embedder)}

    if args.solo_recuperacion:
        recs = {m: {q["id"]: sistemas[m](q["pregunta"]) for q in preguntas} for m in MODOS}
        texto = tabla_recuperacion(preguntas, recs)
        RESULTADOS.mkdir(parents=True, exist_ok=True)
        (RESULTADOS / "recuperacion.md").write_text("# Recuperación sin LLM\n\n" + texto + "\n", encoding="utf-8")
        print(texto)
        driver.close()
        return 0

    from common.llm import crear_llm
    from common.respuesta import responder

    llm = crear_llm()
    datos = leer_guardado()
    llamadas = 0

    def pausa():
        nonlocal llamadas
        if llamadas:
            time.sleep(args.pausa)
        llamadas += 1

    try:
        for q in preguntas:
            for modo in modos:
                clave = f"{modo}|{q['id']}"
                d = datos.get(clave)
                if d is None or args.rehacer:
                    t0 = time.time()
                    rec = sistemas[modo](q["pregunta"])
                    pausa()
                    respuesta = responder(llm, rec)
                    d = datos[clave] = {
                        "id": q["id"], "modo": modo, "tipo": q["tipo"], "pregunta": q["pregunta"],
                        "respuesta": respuesta, "tiempo_s": round(time.time() - t0, 1), "recall": recall(q, rec),
                        "fragmentos": [f["id"] for f in rec.fragmentos], "hechos": rec.hechos,
                        "entidades": rec.entidades, "contexto": rec.contexto,
                    }
                    guardar(datos)
                    print(f"\n[{clave}] {q['pregunta']}\n{respuesta}")
                if not args.sin_juez and (d.get("puntaje") is None or args.rehacer):
                    pausa()
                    d["puntaje"], d["razon"] = juzgar(llm, q, d["respuesta"])
                    guardar(datos)
                    print(f"  juez: {d['puntaje']} ({d['razon']})")
    except KeyboardInterrupt:
        print("\nInterrumpido; lo hecho quedó guardado.")
    except Exception as e:
        print(f"\nSe detuvo: {e}\nLo hecho quedó en {RESPUESTAS}; vuelve a correr el comando para seguir.")
        driver.close()
        return 2

    driver.close()
    print("\n" + escribir_resumen(cargar_preguntas(), datos))
    print(f"Guardado en {RESPUESTAS} y {RESUMEN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
