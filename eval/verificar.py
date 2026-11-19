"""Verifica las 20 preguntas contra el texto, antes de medir nada con ellas.

En `preguntas.json` las 20 estaban con `verificada: false`. Mientras eso siga
asi, cualquier tabla de resultados mide contra respuestas que nadie comprobo:
si la respuesta esperada dice algo que el corpus no dice, un sistema que
acierte sale mal evaluado y uno que invente sale bien.

El chequeo es mecanico pero no ciego: para cada pregunta busca en los cantos que
la propia pregunta declara como evidencia cada nombre propio de la respuesta
esperada, **traducido a como lo escribe Segala**. Las respuestas dicen "Atenea"
y "Zeus"; la traduccion de 1908 dice "Minerva" y "Jupiter", asi que sin
`equivalencias.csv` todo daria por ausente.

Lo que no encuentra queda listado para leerlo a mano: la salida es una lista de
cosas por revisar, no un veredicto.

Uso:  python -m eval.verificar
"""
from __future__ import annotations

import csv
import sys
import json
import re
import unicodedata
from pathlib import Path

from common.config import EQUIVALENCIAS, PROCESSED, ROOT, WIKI

PREGUNTAS = ROOT / "eval" / "preguntas.json"
CANTOS = PROCESSED / "cantos"

# Palabras con mayuscula que no son nombres de personajes ni de lugares.
NO_ES_NOMBRE = {
    "en", "el", "la", "los", "las", "de", "del", "y", "o", "a", "su", "sus",
    "iliada", "odisea", "canto", "cantos", "segun", "entre", "con", "por",
    "para", "que", "quien", "pide", "consigue", "lleva", "guia", "atrapa",
    "combate", "muere", "mata", "forja", "madre", "padre", "hijo", "hijos",
    "esposo", "esposa", "abuelo", "dioses", "dios", "todos", "ambos",
    "seleccionados", "tierra", "muertos", "red", "piedra", "armas", "nuevas",
}


def plano(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def formas_por_entidad() -> dict[str, list[str]]:
    """De la entidad canonica a todas las formas con que aparece en el texto.

    `equivalencias.csv` va al contrario (texto -> entidad), asi que se invierte.
    La entidad tambien se incluye como forma, porque hay nombres que la
    traduccion si escribe igual (Aquiles, Helena, Patroclo).
    """
    formas: dict[str, list[str]] = {}
    with open(EQUIVALENCIAS, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            entidad = plano(fila["entidad"])
            formas.setdefault(entidad, [entidad]).append(plano(fila["nombre_en_texto"]))
    return formas


def textos_de_evidencia(evidencia: list[str]) -> dict[str, str]:
    """Los textos que la pregunta declara como su evidencia.

    Acepta lo que ya hay escrito en `preguntas.json`: "Iliada 18", "Odisea 11",
    "Odisea" (todos sus cantos), "todos los cantos", "wikis" y "equivalencias".
    """
    archivos: dict[str, str] = {}

    for item in evidencia:
        clave = plano(item)

        if "todos los cantos" in clave:
            for ruta in sorted(CANTOS.glob("*.txt")):
                archivos[ruta.stem] = ruta.read_text(encoding="utf-8")
        elif clave == "wikis":
            for ruta in sorted(WIKI.glob("*.txt")):
                archivos[f"wiki:{ruta.stem}"] = ruta.read_text(encoding="utf-8")
        elif clave == "equivalencias":
            archivos["equivalencias"] = EQUIVALENCIAS.read_text(encoding="utf-8")
        elif m := re.match(r"(iliada|odisea)\s+(\d+)", clave):
            ruta = CANTOS / f"{m.group(1)}_{int(m.group(2)):02d}.txt"
            if ruta.exists():
                archivos[ruta.stem] = ruta.read_text(encoding="utf-8")
            else:
                archivos[f"[FALTA] {ruta.name}"] = ""
        elif clave in ("iliada", "odisea"):
            for ruta in sorted(CANTOS.glob(f"{clave}_*.txt")):
                archivos[ruta.stem] = ruta.read_text(encoding="utf-8")
        else:
            archivos[f"[NO SE QUE ES] {item}"] = ""

    return archivos


def nombres_de(respuesta: str) -> list[str]:
    """Los nombres propios de la respuesta esperada."""
    crudos = re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+", respuesta)
    vistos, nombres = set(), []
    for nombre in crudos:
        p = plano(nombre)
        if p in NO_ES_NOMBRE or p in vistos:
            continue
        vistos.add(p)
        nombres.append(nombre)
    return nombres


def aparece(nombre: str, textos: dict[str, str], formas: dict[str, list[str]]) -> list[str]:
    """En que textos de la evidencia aparece el nombre, en cualquiera de sus formas."""
    candidatas = formas.get(plano(nombre), [plano(nombre)])
    donde = []
    for etiqueta, texto in textos.items():
        liso = plano(texto)
        if any(re.search(r"\b" + re.escape(f) + r"\b", liso) for f in candidatas):
            donde.append(etiqueta)
    return donde


def mejor_parrafo(nombres: list[str], textos: dict[str, str],
                  formas: dict[str, list[str]]) -> tuple[str, str, int]:
    """El parrafo de la evidencia donde coinciden mas nombres de la respuesta.

    Que cada nombre aparezca **en algun lado** del canto no verifica nada: para
    "¿quien mata a Hector?", Aquiles, Patroclo y Paris aparecen todos en el
    canto XXII, asi que la respuesta falsa "Patroclo" pasaria igual. Lo que
    acota de verdad es que los nombres aparezcan **juntos en un parrafo**, y que
    ese parrafo se pueda leer.
    """
    mejor, etiqueta_mejor, cuantos = "", "", 0

    for etiqueta, texto in textos.items():
        for parrafo in texto.split("\n\n"):
            liso = plano(parrafo)
            n = sum(
                any(
                    re.search(r"\b" + re.escape(f) + r"\b", liso)
                    for f in formas.get(plano(nombre), [plano(nombre)])
                )
                for nombre in nombres
            )
            if n > cuantos:
                mejor, etiqueta_mejor, cuantos = parrafo, etiqueta, n

    return etiqueta_mejor, mejor, cuantos


def main() -> None:
    # La consola de Windows viene en cp1252: sin esto los acentos salen como "?"
    # y un espacio de ancho cero de los articulos de Wikipedia tumba el script.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    preguntas = json.loads(PREGUNTAS.read_text(encoding="utf-8"))
    formas = formas_por_entidad()

    if not CANTOS.exists():
        raise SystemExit("No hay cantos procesados. Corre:  python -m ingest.prepare")

    por_revisar = []
    hallazgos = []
    for q in preguntas:
        textos = textos_de_evidencia(q["evidencia"])

        # los nombres de la pregunta **y** de la respuesta. "¿quien mata a
        # Hector?" responde "Aquiles": si solo se miran los de la respuesta hay
        # un unico nombre y no queda nada que cruzar, mientras que buscar
        # "Aquiles" y "Hector" juntos en un parrafo si acota.
        nombres = nombres_de(q["pregunta"] + " " + q["respuesta_esperada"])
        malos = [e for e in textos if e.startswith("[")]
        faltantes = [n for n in nombres if not aparece(n, textos, formas)]

        etiqueta, parrafo, juntos = mejor_parrafo(nombres, textos, formas)

        # con un solo nombre no hay nada que cruzar; con dos o mas, el pasaje
        # tiene que traer al menos dos juntos para que sirva de evidencia
        suficiente = juntos >= min(2, len(nombres))
        estado = "ok" if suficiente and not faltantes and not malos else "REVISAR"
        if estado == "REVISAR":
            por_revisar.append(q["id"])

        print(f"[{estado:7}] {q['id']} ({q['tipo']})  {juntos}/{len(nombres)} nombres juntos")
        if malos:
            print(f"            evidencia sin resolver: {malos}")
        if faltantes:
            print(f"            no aparecen: {faltantes}")
        if parrafo:
            print(f"            {etiqueta}: {parrafo[:260]}")
        print()

        hallazgos.append({
            "pasaje_fuente": etiqueta,
            "pasaje": parrafo[:600],
            "nombres_buscados": nombres,
            "nombres_juntos": juntos,
        })

    print(f"{len(preguntas) - len(por_revisar)} de {len(preguntas)} tienen un pasaje "
          f"con los nombres juntos")
    if por_revisar:
        print(f"a leer a mano: {', '.join(por_revisar)}")
    print()
    print("ojo: esto acota, no verifica. el pasaje de arriba hay que leerlo y")
    print("confirmar que dice lo que la respuesta esperada afirma. en las")
    print("preguntas de conjunto (q01, q10) un solo parrafo no puede probar la")
    print("respuesta completa, asi que esas quedan en verificada: false.")

    if "--escribir" in sys.argv:
        for q, datos_q in zip(preguntas, hallazgos):
            q.update(datos_q)
        PREGUNTAS.write_text(
            json.dumps(preguntas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print()
        print(f"evidencia guardada en {PREGUNTAS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
