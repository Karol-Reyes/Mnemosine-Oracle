"""
Descarga los artículos de Wikipedia en español listados en data/wikis.txt.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
LISTA = ROOT / "data" / "wikis.txt"
OUT = ROOT / "data" / "wikipedia"
API = "https://es.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "MnemosineOracle/0.1 (proyecto académico de GraphRAG; contacto vía GitHub)"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
PAUSA = 1.0                              # segundos entre artículos
MAX_REINTENTOS = 5                       # intentos por petición
ESPERA_MAX = 60                          # tope de espera entre reintentos, en segundos
REINTENTABLES = {429, 500, 502, 503, 504}
CAMPOS_MANIFEST = ["pedido", "titulo", "metodo", "url", "caracteres"]
SECCIONES_FINALES = re.compile(
    r"\n=+\s*(Referencias|Notas|Véase también|Bibliografía|Enlaces externos|Fuentes|Notas y referencias)\s*=+.*",
    re.S,
)


def get(params: dict) -> requests.Response:
    """
    GET a la API con reintentos.
    """
    for intento in range(1, MAX_REINTENTOS + 1):
        ultimo = intento == MAX_REINTENTOS
        try:
            r = SESSION.get(API, params=params, timeout=30)
        except (requests.ConnectionError, requests.Timeout) as e:
            if ultimo:
                raise
            espera = min(5 * 2 ** (intento - 1), ESPERA_MAX)
            print(f"     sin conexión ({type(e).__name__}); reintento en {espera:.0f} s")
            time.sleep(espera)
            continue
        if r.status_code in REINTENTABLES and not ultimo:
            try:
                espera = float(r.headers["Retry-After"])
            except (KeyError, ValueError):
                espera = 5 * 2 ** (intento - 1)
            espera = min(max(espera, 2.0), ESPERA_MAX)
            print(f"     HTTP {r.status_code}: espero {espera:.0f} s y reintento ({intento}/{MAX_REINTENTOS - 1})")
            time.sleep(espera)
            continue
        r.raise_for_status()
        return r
    raise RuntimeError("get(): sin respuesta")  # no se alcanza


def leer_manifest() -> list[dict]:
    ruta = OUT / "_manifest.csv"
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def guardar_manifest(manifest: dict[str, dict]) -> None:
    with open(OUT / "_manifest.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_MANIFEST)
        w.writeheader()
        w.writerows(manifest.values())


def leer_lista() -> list[tuple[str, str]]:
    pares = []
    for linea in LISTA.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        nombre, _, titulo = (p.strip() for p in linea.partition("|"))
        pares.append((nombre, titulo or nombre))
    return pares


def pedir_articulo(titulo: str) -> dict | None:
    params = {
        "action": "query", "format": "json", "formatversion": 2, "redirects": 1,
        "prop": "extracts|pageprops", "explaintext": 1, "titles": titulo,
    }
    r = get(params)
    pagina = r.json()["query"]["pages"][0]
    if pagina.get("missing") or "disambiguation" in pagina.get("pageprops", {}):
        return None
    return pagina


def buscar(nombre: str) -> str | None:
    params = {
        "action": "query", "format": "json", "list": "search", "srlimit": 1,
        "srsearch": f"{nombre} mitología griega",
    }
    r = get(params)
    resultados = r.json()["query"]["search"]
    return resultados[0]["title"] if resultados else None


def limpiar(texto: str, max_chars: int) -> str:
    texto = SECCIONES_FINALES.sub("", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    if len(texto) > max_chars:
        corte = texto.rfind("\n\n", 0, max_chars)
        texto = texto[: corte if corte > 0 else max_chars].strip()
    return texto


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-chars", type=int, default=15000,
                    help="tope de caracteres por artículo (controla el costo de extracción)")
    ap.add_argument("--force", action="store_true",
                    help="vuelve a descargar también los artículos que ya están en el manifiesto")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    pares = leer_lista()
    manifest = {} if args.force else {f["pedido"]: f for f in leer_manifest()}
    for nombre, titulo in pares:
        if nombre in manifest and (OUT / f"{nombre}.txt").exists():
            print(f"[=] {nombre:12s} ya descargado")
            continue
        try:
            pagina, metodo = pedir_articulo(titulo), "titulo"
            if pagina is None:
                encontrado = buscar(nombre)
                pagina = pedir_articulo(encontrado) if encontrado else None
                metodo = "busqueda"
        except requests.RequestException as e:
            print(f"[x] {nombre}: error de red ({e})")
            if getattr(e.response, "status_code", None) == 429:
                print("    Wikipedia sigue limitando las peticiones: paro aquí para no empeorarlo. "
                      "Espera unos minutos y vuelve a correr el comando.")
                break
            continue
        if pagina is None or not pagina.get("extract"):
            print(f"[x] {nombre}: no encontrado")
            continue

        resuelto = pagina["title"]
        url = "https://es.wikipedia.org/wiki/" + quote(resuelto.replace(" ", "_"))
        texto = limpiar(pagina["extract"], args.max_chars)
        cabecera = f"titulo: {resuelto}\nurl: {url}\nlicencia: CC BY-SA 4.0 (Wikipedia en español)\n\n"
        (OUT / f"{nombre}.txt").write_text(cabecera + texto, encoding="utf-8")
        manifest[nombre] = {"pedido": nombre, "titulo": resuelto, "metodo": metodo, "url": url,
                            "caracteres": len(texto)}
        guardar_manifest(manifest)  # tras cada artículo: si se interrumpe, no se pierde lo descargado
        aviso = "   <-- revisar" if metodo == "busqueda" else ""
        print(f"[ok] {nombre:12s} -> {resuelto:30s} {len(texto):6d} car.{aviso}")
        time.sleep(PAUSA)  # cortesía con la API

    pendientes = [n for n, _ in pares if n not in manifest]
    total = sum(int(f["caracteres"]) for f in manifest.values())
    print(f"\n{len(manifest)} artículos, {total:,} caracteres. Pendientes: {pendientes or 'ninguno'}")
    if pendientes:
        print("Vuelve a correr el comando: salta los ya descargados y pide solo los que faltan.")
    print("Revisa en _manifest.csv los que dicen 'busqueda': confirma que sean el personaje correcto.")
    return 1 if pendientes else 0


if __name__ == "__main__":
    sys.exit(main())
