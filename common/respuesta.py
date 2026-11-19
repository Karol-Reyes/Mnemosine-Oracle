"""Piezas comunes de RAG y GraphRAG: resultado de la recuperación, citas y generación de la respuesta."""
from __future__ import annotations

from dataclasses import dataclass, field

from common.llm import con_reintentos

LIBROS_ID = {"iliada": "Ilíada", "odisea": "Odisea"}

PROMPT = """Eres Mnemosine, una asistente experta en la Ilíada y la Odisea (traducción de Luis Segalá y Estalella).

Responde la pregunta usando solo el contexto. Reglas:
- Responde en español, en pocas frases y de forma directa.
- Cita la fuente de cada dato entre paréntesis: (Ilíada, canto XXII), (Odisea, canto IX) o (Wikipedia: Zeus).
- Usa los nombres griegos (Zeus, Atenea, Odiseo) aunque el texto use los latinos (Júpiter, Minerva, Ulises).
- Los hechos del grafo se extrajeron automáticamente y pueden tener errores: si se contradicen, prefiere el que
  tiene más respaldo (xN) y el que confirman los fragmentos.
- Si el contexto no alcanza para responder, dilo; no completes con lo que sepas de otras fuentes.

Contexto:
{contexto}

Pregunta: {pregunta}
Respuesta:"""


@dataclass
class Recuperacion:
    modo: str
    pregunta: str
    fragmentos: list[dict]
    hechos: list[str] = field(default_factory=list)
    entidades: list[str] = field(default_factory=list)

    @property
    def contexto(self) -> str:
        partes = []
        if self.entidades:
            partes.append("Entidades de la pregunta:\n" + "\n".join(f"- {e}" for e in self.entidades))
        if self.hechos:
            partes.append("Hechos del grafo (origen -RELACIÓN-> destino (xN fragmentos que lo respaldan) [dónde]):\n"
                          + "\n".join(f"- {h}" for h in self.hechos))
        textos = [f"[{i}] {cita(f)}\n{f['texto']}" for i, f in enumerate(self.fragmentos, 1)]
        partes.append("Fragmentos:\n\n" + "\n\n".join(textos))
        return "\n\n".join(partes)

    def cantos(self) -> set[tuple[str, int]]:
        """(libro, canto) de los fragmentos de texto recuperados."""
        return {(f["libro"], int(f["canto"])) for f in self.fragmentos if f.get("libro")}


def romano(n: int) -> str:
    valores = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    salida = ""
    for v, s in valores:
        while n >= v:
            salida += s
            n -= v
    return salida


def cita(fragmento: dict) -> str:
    if fragmento.get("libro"):
        return f"{fragmento['libro']}, canto {romano(int(fragmento['canto']))}"
    return f"Wikipedia: {fragmento.get('titulo', '?')}"


def fuente_de_id(frag_id: str) -> tuple[str, int] | str:
    """'iliada_16_004' -> ('Ilíada', 16); 'wiki_Zeus_002' -> 'Wikipedia: Zeus'."""
    if frag_id.startswith("wiki_"):
        return "Wikipedia: " + frag_id[5:].rsplit("_", 1)[0].replace("_", " ")
    libro, canto, _ = frag_id.split("_")
    return LIBROS_ID[libro], int(canto)


def texto_fuente(fuente: tuple[str, int] | str) -> str:
    return fuente if isinstance(fuente, str) else f"{fuente[0]} {romano(fuente[1])}"


def responder(llm, recuperacion: Recuperacion) -> str:
    prompt = PROMPT.format(contexto=recuperacion.contexto, pregunta=recuperacion.pregunta)
    return con_reintentos(llm.invoke, prompt).content.strip()
