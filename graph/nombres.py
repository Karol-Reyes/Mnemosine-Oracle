"""Nombres canónicos de las entidades, según equivalencias.csv y entidades.csv."""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from functools import lru_cache

from common import config

ARTICULO = re.compile(r"^(el|la|los|las|lo)\s+", re.I)


def _clave(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip().casefold()


def plano(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def _limpiar(nombre: str) -> str:
    n = " ".join(unicodedata.normalize("NFC", nombre).split()).strip(" .,;:«»\"'")
    n = ARTICULO.sub("", n)
    return n[:1].upper() + n[1:]


@lru_cache
def equivalencias() -> dict[str, str]:
    """nombre en el texto -> entidad. Las ambiguas (Atrida -> Agamenón|Menelao) se omiten."""
    with open(config.EQUIVALENCIAS, encoding="utf-8") as f:
        return {_clave(r["nombre_en_texto"]): r["entidad"] for r in csv.DictReader(f) if "|" not in r["entidad"]}


@lru_cache
def catalogo() -> dict[str, str]:
    """nombre canónico -> tipo."""
    with open(config.ENTIDADES, encoding="utf-8") as f:
        return {r["nombre"]: r["tipo"] for r in csv.DictReader(f)}


@lru_cache
def _por_clave() -> dict[str, str]:
    return {plano(n): n for n in catalogo()}


@lru_cache
def _variantes() -> dict[str, str]:
    """Grafía más frecuente en la caché para cada nombre sin tildes (Nestor -> Néstor)."""
    cuenta: Counter = Counter()
    for ruta in (config.DATA / "extracciones").glob("*.json"):
        for nodo in json.loads(ruta.read_text(encoding="utf-8")).get("nodes", []):
            nombre = (nodo.get("properties") or {}).get("name")
            if isinstance(nombre, str) and _limpiar(nombre):
                cuenta[_limpiar(nombre)] += 1
    mejor: dict[str, str] = {}
    for nombre, veces in cuenta.items():
        k = plano(nombre)
        if k not in mejor or (veces, nombre.casefold() != k) > (cuenta[mejor[k]], mejor[k].casefold() != k):
            mejor[k] = nombre
    return mejor


def canonico(nombre: str, tipo: str) -> tuple[str, str]:
    """('el Pelida', 'Personaje') -> ('Aquiles', 'Personaje'); ('Orco', 'Lugar') -> ('Hades (inframundo)', 'Lugar')."""
    n = _limpiar(nombre)
    if not n:
        return "", tipo
    n = equivalencias().get(_clave(n), n)
    n = _por_clave().get(plano(n)) or _variantes().get(plano(n)) or n

    tipo_catalogo = catalogo().get(n)
    if tipo_catalogo and tipo_catalogo != tipo:
        variante = next((c for c, t in catalogo().items() if t == tipo and c.startswith(n + " (")), None)
        return (variante, tipo) if variante else (n, tipo_catalogo)
    return n, tipo


def texto_equivalencias() -> str:
    """'Júpiter -> Zeus, Minerva -> Atenea, ...' para el prompt."""
    with open(config.EQUIVALENCIAS, encoding="utf-8") as f:
        pares = [f"{r['nombre_en_texto']} -> {r['entidad'].replace('|', ' o ')}" for r in csv.DictReader(f)]
    return ", ".join(pares)
