"""Presentación de las respuestas en la interfaz: texto en párrafos y fuentes en una lista aparte."""
from __future__ import annotations

import re

CITA = re.compile(r"\[?\(+([^()]*?(?:Ilíada|Odisea|Wikipedia)[^()]*?)\)+\]?")
REFERENCIA = re.compile(r"\s*\[\d+\]")
LIBRO = re.compile(r"(Ilíada|Odisea)")
ROMANO = re.compile(r"\b[IVXL]+\b")
FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])")


def fuentes(cita: str) -> list[str]:
    salida = []
    for parte in re.split(r";", cita):
        parte = parte.strip(" ,")
        if parte.startswith("Wikipedia"):
            salida += ["Wikipedia: " + p.strip() for p in parte.split(":", 1)[1].split(",") if p.strip()]
            continue
        trozos = LIBRO.split(parte)
        for libro, resto in zip(trozos[1::2], trozos[2::2]):
            salida += [f"{libro}, canto {n}" for n in ROMANO.findall(resto)] or [libro]
    return salida


def formatear(respuesta: str) -> str:
    citas: list[str] = []
    for c in CITA.findall(respuesta):
        citas += [f for f in fuentes(c) if f not in citas]
    texto = REFERENCIA.sub("", CITA.sub("", respuesta))
    texto = re.sub(r"\(\s*[,;]?\s*\)", "", texto)
    texto = re.sub(r"\s+([.,;:])", r"\1", re.sub(r"[ \t]+", " ", texto))
    texto = re.sub(r"[,;]+(?=[.!?]|$)", "", texto).strip()
    parrafos = "\n\n".join(FRASE.split(texto))
    if not citas:
        return parrafos
    lineas = []
    for libro in ("Ilíada", "Odisea"):
        cantos = sorted({c for c in citas if c.startswith(libro + ", canto ")}, key=orden)
        if cantos:
            nombre = "canto" if len(cantos) == 1 else "cantos"
            lineas.append(f"- *{libro}*, {nombre} " + ", ".join(c.split()[-1] for c in cantos))
    wikis = sorted(c.split(": ", 1)[1] for c in citas if c.startswith("Wikipedia"))
    if wikis:
        lineas.append("- Wikipedia: " + ", ".join(wikis))
    return parrafos + "\n\n**Fuentes**\n\n" + "\n".join(lineas)


def orden(cita: str) -> tuple[str, int]:
    libro, _, canto = cita.partition(", canto ")
    valores = {"I": 1, "V": 5, "X": 10, "L": 50}
    n = [valores[c] for c in canto]
    return libro, sum(-v if i + 1 < len(n) and v < n[i + 1] else v for i, v in enumerate(n))
