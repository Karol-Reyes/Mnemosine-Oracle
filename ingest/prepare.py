"""Prepara los cantos de la Ilíada y la Odisea.

Uso (desde la raíz del repo):  python -m ingest.prepare
Solo usa la biblioteca estándar.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
LIBROS = {"iliada": "Ilíada", "odisea": "Odisea"}
MAX_CHARS = 1500

# Ortografía de 1908-1910 -> actual. Solo palabras completas.
ORTOGRAFIA = {
    "á": "a", "Á": "A", "ó": "o", "Ó": "O", "é": "e", "É": "E",
    "fué": "fue", "Fué": "Fue", "fuí": "fui", "Fuí": "Fui",
    "dió": "dio", "Dió": "Dio", "vió": "vio", "Vió": "Vio",
    "pié": "pie", "piés": "pies", "ví": "vi", "Ví": "Vi",
}
_PALABRA = re.compile(r"\b(" + "|".join(map(re.escape, ORTOGRAFIA)) + r")\b")


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto)
    texto = _PALABRA.sub(lambda m: ORTOGRAFIA[m.group(1)], texto)
    texto = texto.replace("--", " — ")
    texto = re.sub(r"[ \t]+", " ", texto)
    return texto.strip()


def parrafos(cuerpo: str) -> list[str]:
    """Une las líneas cortadas del .txt en párrafos."""
    bloques = re.split(r"\n\s*\n", cuerpo)
    return [" ".join(l.strip() for l in b.splitlines()).strip() for b in bloques if b.strip()]


def leer_canto(ruta: Path) -> tuple[str, list[str]]:
    """Devuelve (título, párrafos). Quita el encabezado 'CANTO ...' y usa el subtítulo como título."""
    lineas = ruta.read_text(encoding="utf-8").strip().splitlines()
    ps = parrafos("\n".join(lineas))
    if ps and ps[0].upper().startswith("CANTO"):
        ps = ps[1:]
    titulo = ""
    if ps and ps[0].isupper() and len(ps[0]) < 120:
        titulo, ps = ps[0], ps[1:]
    ps = [normalizar(p) for p in ps]
    return formatear_titulo(normalizar(titulo), " ".join(ps)), ps


def formatear_titulo(titulo: str, cuerpo: str) -> str:
    """'COLOQUIO DE HÉCTOR Y ANDRÓMACA' -> 'Coloquio de Héctor y Andrómaca'.
    Una palabra queda en mayúscula inicial si en el canto aparece así y nunca en minúscula."""
    palabras = []
    for i, w in enumerate(titulo.lower().split(" ")):
        nucleo = w.strip(".,;:—")
        nombre_propio = nucleo and re.search(rf"\b{re.escape(nucleo.capitalize())}\b", cuerpo) \
            and not re.search(rf"\b{re.escape(nucleo)}\b", cuerpo)
        palabras.append(w.capitalize() if i == 0 or nombre_propio else w)
    return " ".join(palabras)


def trocear(ps: list[str], max_chars: int = MAX_CHARS) -> list[str]:
    """Agrupa párrafos hasta ~max_chars; corta por oraciones los párrafos muy largos."""
    piezas: list[str] = []
    for p in ps:
        if len(p) <= max_chars:
            piezas.append(p)
            continue
        actual = ""
        for oracion in re.split(r"(?<=[.;:?!»])\s+", p):
            if actual and len(actual) + len(oracion) + 1 > max_chars:
                piezas.append(actual)
                actual = oracion
            else:
                actual = f"{actual} {oracion}".strip()
        if actual:
            piezas.append(actual)

    fragmentos, actual = [], ""
    for pieza in piezas:
        if actual and len(actual) + len(pieza) + 2 > max_chars:
            fragmentos.append(actual)
            actual = pieza
        else:
            actual = f"{actual}\n\n{pieza}".strip()
    if actual:
        fragmentos.append(actual)
    return fragmentos


def main() -> int:
    (OUT / "cantos").mkdir(parents=True, exist_ok=True)
    registros, entrenamiento = [], []

    for libro_id, libro in LIBROS.items():
        archivos = sorted((RAW / libro_id).glob("*.txt"))
        if not archivos:
            print(f"[!] No hay cantos en {RAW / libro_id}")
            return 1
        for ruta in archivos:
            canto = int(re.search(r"(\d+)", ruta.stem).group(1))
            titulo, ps = leer_canto(ruta)
            texto = "\n\n".join(ps)
            (OUT / "cantos" / f"{libro_id}_{canto:02d}.txt").write_text(texto, encoding="utf-8")
            entrenamiento.append(texto)

            frags = trocear(ps)
            for i, frag in enumerate(frags, start=1):
                registros.append({
                    "id": f"{libro_id}_{canto:02d}_{i:03d}",
                    "libro": libro,
                    "libro_id": libro_id,
                    "canto": canto,
                    "canto_titulo": titulo,
                    "fragmento": i,
                    "texto": frag,
                })
            print(f"{libro:7s} canto {canto:2d}  {len(texto):6d} caracteres  {len(frags):3d} fragmentos  «{titulo}»")

    with open(OUT / "fragmentos.jsonl", "w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (OUT / "corpus_entrenamiento.txt").write_text("\n\n".join(entrenamiento), encoding="utf-8")

    print(f"\nListo: {len(registros)} fragmentos en {OUT / 'fragmentos.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
