"""GraphRAG: parte de las entidades de la pregunta, recorre el grafo y elige los fragmentos con su ayuda.

1. Busca en la pregunta nombres de entidades (con equivalencias: Ulises -> Odiseo) y pistas
   de relación (mata -> MATA_A, abuelo -> HIJO_DE) y de tipo (dioses -> Deidad).
2. Hechos: relaciones de cada entidad (las de la pista primero, en la dirección que pide la pregunta,
   luego por menciones), caminos de dos saltos si la pregunta encadena relaciones (abuelo, hijo de Zeus
   que muere) y puentes entre dos entidades de la pregunta.
3. Fragmentos: los que sustentan esos hechos y los que nombran a las entidades, ordenados por
   parecido con la pregunta y repartidos entre los poemas que la pregunta nombra.

Uso:
  python -m graphrag.retriever "¿Quién es el abuelo paterno de Telémaco?"
  python -m graphrag.retriever "..." --solo-contexto
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from dataclasses import dataclass

from neo4j import Driver

from common import config
from common.respuesta import Recuperacion, fuente_de_id, romano, texto_fuente
from graph.nombres import plano
from rag.baseline import CAMPOS, K, busqueda_vectorial

PALABRA = re.compile(r"[^\W\d_]+")

TIPOS = {
    "Deidad": "dios dioses diosa diosas deidad deidades divinidad divinidades",
    "Personaje": "personaje personajes heroe heroes mortal mortales guerrero guerreros",
    "Criatura": "criatura criaturas monstruo monstruos",
    "Lugar": "lugar lugares ciudad ciudades isla islas",
    "Grupo": "pueblo pueblos",
    "Objeto": "objeto objetos arma armas",
}

PISTAS = {
    "HIJO_DE": "hijo hija hijos hijas padre padres madre abuelo abuela abuelos nieto nieta descendiente "
               "progenitor parentesco genealogia familia",
    "HERMANO_DE": "hermano hermana hermanos hermanas parentesco familia",
    "ESPOSO_DE": "esposo esposa esposos marido casado casada matrimonio parentesco familia",
    "AMA_A": "ama amo amante amantes amor enamora enamorado enamorada",
    "MATA_A": "mata mato matan mataron matar muere murio mueren muerte asesina asesino asesinado asesinada",
    "ENFRENTA_A": "enfrenta enfrento combate combatio lucha lucho pelea disputa enojado enojada enemigo "
                  "enemigos odia ira colera",
    "AYUDA_A": "ayuda ayudo protege protegio aconseja guia apoya apoyan favorece favorecen",
    "APOYA_A": "apoya apoyan favorece favorecen bando",
    "ORDENA_A": "ordena ordeno envia envio mensaje orden",
    "VIAJA_A": "viaja viajo llega llego navega visita visito",
    "VIVE_EN": "vive vivia reina reinaba habita",
    "CREA": "crea creo forja forjo fabrica",
    "POSEE": "posee armas",
}

LIBROS = {"iliada": "Ilíada", "odisea": "Odisea"}
POEMAS = {"poema", "poemas"}
ASCENDENTE = set("abuelo abuela abuelos abuelas bisabuelo".split())
DESCENDENTE = set("nieto nieta nietos nietas".split())
ACTIVOS = set("mata mato matan mataron asesina asesino".split())

MAX_HECHOS = 25
HECHOS_GUIA = 10
POR_ENTIDAD = 15
DOS_SALTOS = 15
PUENTES = 15
POR_TIPO = 25
CANDIDATOS = 300
BONO_COOCURRENCIA = 0.05
BONO_PISTA = 0.1
CASTIGO_WIKI = 0.1
BONO_LISTADA = 0.03
MAX_LISTADAS = 5
PREFIJO = {"Ilíada": "iliada_", "Odisea": "odisea_"}


def _por_palabra(tabla: dict[str, str]) -> dict[str, set[str]]:
    salida: dict[str, set[str]] = defaultdict(set)
    for clave, palabras in tabla.items():
        for p in palabras.split():
            salida[p].add(clave)
    return salida


PALABRA_TIPO = _por_palabra(TIPOS)
PALABRA_PISTA = _por_palabra(PISTAS)


@dataclass
class Consulta:
    palabras: list[str]
    pistas: set[str]
    tipos: set[str]
    libros: list[str]
    cadena: bool
    entrantes: set[str]
    sentido: int
    listar_en: list[str]


def analizar(pregunta: str) -> Consulta:
    """Palabras, pistas de relación, tipos pedidos y poemas nombrados.

    cadena: la pregunta pide dos saltos (abuelo = padre del padre) o combina dos relaciones.
    entrantes: relaciones donde la entidad nombrada es el destino ("¿Quién mata a Héctor?").
    listar_en: poemas que solo califican al tipo pedido ("personajes de la Ilíada"), no dónde buscar.
    """
    palabras = PALABRA.findall(pregunta)
    planos = [plano(p) for p in palabras]
    pistas = set().union(*(PALABRA_PISTA.get(p, set()) for p in planos))
    tipos = set().union(*(PALABRA_TIPO.get(p, set()) for p in planos))
    libros = [LIBROS[p] for p in LIBROS if p in planos]
    listar_en = [LIBROS[p] for i, p in enumerate(planos)
                 if p in LIBROS and i >= 3 and planos[i - 2] == "de" and planos[i - 3] in PALABRA_TIPO]
    libros = [l for l in libros if l not in listar_en]
    if not libros and not listar_en and POEMAS & set(planos):
        libros = list(LIBROS.values())
    sentido = 1 if ASCENDENTE & set(planos) else -1 if DESCENDENTE & set(planos) else 0
    cadena = len(pistas - {"APOYA_A", "AYUDA_A"}) > 1 or sentido != 0
    entrantes = {"MATA_A"} if any(a in ACTIVOS and b == "a" for a, b in zip(planos, planos[1:])) else set()
    return Consulta(palabras, pistas, tipos, libros, cadena, entrantes, sentido, listar_en)


class IndiceNombres:
    """Nombre o equivalencia sin tildes -> claves de entidad en el grafo."""

    def __init__(self, entidades: list[dict]):
        self.tipo = {e["clave"]: e["tipo"] for e in entidades}
        self.nombre = {e["clave"]: e["nombre"] for e in entidades}
        self.claves: dict[str, set[str]] = defaultdict(set)
        self.alias: dict[str, list[str]] = defaultdict(list)
        for e in entidades:
            self.claves[plano(e["nombre"])].add(e["clave"])
            base = e["nombre"].split(" (")[0]
            self.claves[plano(base)].add(e["clave"])
        with open(config.EQUIVALENCIAS, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                for destino in r["entidad"].split("|"):
                    self.claves[plano(r["nombre_en_texto"])] |= self.claves.get(plano(destino), set())
                    self.alias[destino].append(r["nombre_en_texto"])
        ignorar = set(PALABRA_TIPO) | set(PALABRA_PISTA) | set(LIBROS)
        for p in ignorar:
            self.claves.pop(p, None)
        self.largo = max((len(k.split()) for k in self.claves), default=1)

    def buscar(self, palabras: list[str]) -> list[str]:
        """Claves de las entidades nombradas, en orden de aparición. Prefiere el nombre más largo."""
        encontradas: list[str] = []
        i = 0
        while i < len(palabras):
            for n in range(min(self.largo, len(palabras) - i), 0, -1):
                frase = " ".join(palabras[i:i + n])
                claves = self.claves.get(plano(frase), set())
                mayuscula = frase[0].isupper() or all(self.tipo[c] == "Grupo" for c in claves)
                if claves and mayuscula:
                    encontradas += sorted(c for c in claves if c not in encontradas)
                    i += n
                    break
            else:
                i += 1
        return encontradas


def prefijos(libros: list[str]) -> list[str]:
    """Prefijos de id de los fragmentos que cuentan como evidencia: los de los poemas nombrados, o los dos."""
    return [PREFIJO[l] for l in libros] or list(PREFIJO.values())


def en_libro(fragmentos: list[str], prefs: list[str]) -> int:
    return sum(1 for f in fragmentos if f.startswith(tuple(prefs)))


EN_LIBRO = "size([f IN coalesce({r}.fragmentos, []) WHERE any(p IN $prefijos WHERE f STARTS WITH p)])"


def _hecho(fila: dict, prefijo: str = "") -> dict:
    return {
        "a": fila[f"{prefijo}a"], "tipo": fila[f"{prefijo}tipo"], "b": fila[f"{prefijo}b"],
        "menciones": fila[f"{prefijo}menciones"] or 0, "fragmentos": fila[f"{prefijo}fragmentos"] or [],
    }


def _rel(prefijo: str, r: str) -> str:
    return (f"startNode({r}).name AS {prefijo}a, type({r}) AS {prefijo}tipo, endNode({r}).name AS {prefijo}b, "
            f"{r}.menciones AS {prefijo}menciones, {r}.fragmentos AS {prefijo}fragmentos")


def diversificar(candidatos: list[dict], libros: list[str], k: int) -> list[dict]:
    """Los k mejores; si la pregunta nombra los dos poemas, intercala fragmentos de cada uno."""
    if len(libros) < 2:
        return candidatos[:k]
    colas = {l: [c for c in candidatos if c.get("libro") == l] for l in libros}
    resto = [c for c in candidatos if c.get("libro") not in libros]
    elegidos: list[dict] = []
    while len(elegidos) < k and any(colas.values()):
        for l in libros:
            if colas[l] and len(elegidos) < k:
                elegidos.append(colas[l].pop(0))
    return elegidos + resto[: k - len(elegidos)]


class GraphRAG:
    modo = "graphrag"

    def __init__(self, driver: Driver, embedder, k: int = K):
        self.driver = driver
        self.embedder = embedder
        self.k = k
        filas = self._q(
            "MATCH (e:__Entity__) RETURN e.clave AS clave, e.name AS nombre, "
            "[l IN labels(e) WHERE NOT l STARTS WITH '__'][0] AS tipo"
        )
        self.indice = IndiceNombres(filas)

    def _q(self, cypher: str, **parametros) -> list[dict]:
        filas, _, _ = self.driver.execute_query(cypher, **parametros)
        return [dict(f) for f in filas]

    def hechos(self, semillas: list[str], c: Consulta) -> list[dict]:
        pistas, pistas_l, prefs = c.pistas, sorted(c.pistas), prefijos(c.libros)
        destinos = {self.indice.nombre[s] for s in semillas}
        hechos: list[dict] = []
        for clave in semillas:
            hechos += [_hecho(f) for f in self._q(
                f"""MATCH (e:__Entity__ {{clave: $clave}})-[r]-(o:__Entity__)
                RETURN {_rel('', 'r')}
                ORDER BY type(r) IN $pistas DESC, (type(r) IN $entrantes AND endNode(r) = e) DESC,
                         o.clave IN $semillas DESC, {EN_LIBRO.format(r='r')} DESC, r.menciones DESC
                LIMIT $limite""",
                clave=clave, pistas=pistas_l, entrantes=sorted(c.entrantes), semillas=semillas, prefijos=prefs,
                limite=POR_ENTIDAD,
            )]
            if pistas and c.cadena:
                for f in self._q(
                    f"""MATCH (e:__Entity__ {{clave: $clave}})-[r1]-(m:__Entity__)-[r2]-(o:__Entity__)
                    WHERE type(r1) IN $pistas AND type(r2) IN $pistas AND o <> e AND r1 <> r2
                      AND ($sentido = 0 OR type(r1) <> 'HIJO_DE' OR type(r2) <> 'HIJO_DE'
                           OR ($sentido = 1 AND startNode(r1) = e AND startNode(r2) = m)
                           OR ($sentido = -1 AND endNode(r1) = e AND endNode(r2) = m))
                    WITH r1, r2, size([t IN $pistas WHERE t IN [type(r1), type(r2)]]) AS cubre,
                         {EN_LIBRO.format(r='r1')} + {EN_LIBRO.format(r='r2')} AS en_libro
                    RETURN {_rel('p_', 'r1')}, {_rel('s_', 'r2')}
                    ORDER BY cubre DESC, en_libro DESC, r1.menciones + r2.menciones DESC
                    LIMIT $limite""",
                    clave=clave, pistas=pistas_l, prefijos=prefs, sentido=c.sentido, limite=DOS_SALTOS,
                ):
                    hechos += [_hecho(f, "p_"), _hecho(f, "s_")]
        if len(semillas) > 1:
            for f in self._q(
                f"""MATCH (a:__Entity__)-[r1]-(m:__Entity__)-[r2]-(b:__Entity__)
                WHERE a.clave IN $semillas AND b.clave IN $semillas AND a.clave < b.clave
                  AND NOT m.clave IN $semillas
                RETURN {_rel('p_', 'r1')}, {_rel('s_', 'r2')}
                ORDER BY (type(r1) IN $pistas OR type(r2) IN $pistas) DESC,
                         {EN_LIBRO.format(r='r1')} + {EN_LIBRO.format(r='r2')} DESC, r1.menciones + r2.menciones DESC
                LIMIT $limite""",
                semillas=semillas, pistas=pistas_l, prefijos=prefs, limite=PUENTES,
            ):
                hechos += [_hecho(f, "p_"), _hecho(f, "s_")]

        unicos: dict[tuple, dict] = {}
        for h in hechos:
            unicos.setdefault((h["a"], h["tipo"], h["b"]), h)
        orden = sorted(unicos.values(), key=lambda h: (
            h["tipo"] not in pistas, not (h["tipo"] in c.entrantes and h["b"] in destinos),
            en_libro(h["fragmentos"], prefs) == 0, -h["menciones"]))
        return orden[:MAX_HECHOS]

    def presencia(self, claves: list[str]) -> dict[str, str]:
        """clave -> 'Ilíada I, XVI; Odisea XI' según los fragmentos donde aparece."""
        cantos: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
        for f in self._q(
            """MATCH (e:__Entity__)-[:FROM_CHUNK]->(c:Chunk {fuente: 'poema'}) WHERE e.clave IN $claves
            RETURN e.clave AS clave, c.libro AS libro, collect(DISTINCT c.canto) AS cantos""",
            claves=claves,
        ):
            cantos[f["clave"]][f["libro"]] |= set(f["cantos"])
        return {
            c: "; ".join(f"{l} " + ", ".join(romano(n) for n in sorted(cs)) for l, cs in sorted(por_libro.items()))
            for c, por_libro in cantos.items()
        }

    def por_tipo(self, tipos: set[str], libros: list[str]) -> list[str]:
        """Entidades de esos tipos que aparecen en todos los poemas nombrados, las más mencionadas primero."""
        filas = self._q(
            """MATCH (e:__Entity__)-[:FROM_CHUNK]->(c:Chunk {fuente: 'poema'})
            WHERE any(t IN labels(e) WHERE t IN $tipos)
            WITH e, collect(DISTINCT c.libro) AS libros, count(c) AS n
            WHERE all(l IN $libros WHERE l IN libros)
            RETURN e.clave AS clave ORDER BY n DESC LIMIT $limite""",
            tipos=sorted(tipos), libros=libros, limite=POR_TIPO,
        )
        return [f["clave"] for f in filas]

    def fragmentos(self, semillas: list[str], hechos: list[dict], pistas: set[str], embedding: list[float],
                   libros: list[str], listadas: list[str]) -> list[dict]:
        ids = {fid for h in hechos for fid in h["fragmentos"]}
        de_pistas = {fid for h in hechos[:HECHOS_GUIA] if h["tipo"] in pistas for fid in h["fragmentos"]}
        candidatos = self._q(
            f"""MATCH (node:Chunk)
            WHERE (node.id IN $ids OR EXISTS {{ (e:__Entity__)-[:FROM_CHUNK]->(node) WHERE e.clave IN $semillas }})
              AND (size($libros) <> 1 OR node.libro IN $libros OR node.fuente = 'wikipedia')
            WITH node, vector.similarity.cosine(node.embedding, $emb) AS score,
                 COUNT {{ (e:__Entity__)-[:FROM_CHUNK]->(node) WHERE e.clave IN $semillas }} AS nombradas,
                 COUNT {{ (e:__Entity__)-[:FROM_CHUNK]->(node) WHERE e.clave IN $listadas }} AS listadas
            RETURN {CAMPOS}, nombradas, listadas
            ORDER BY node.id IN $ids DESC, nombradas DESC, score DESC
            LIMIT $limite""",
            ids=sorted(ids), semillas=semillas, listadas=listadas, libros=libros, emb=embedding,
            limite=CANDIDATOS,
        )
        for c in candidatos:
            c["score"] += BONO_COOCURRENCIA * max(c.pop("nombradas") - 1, 0)
            c["score"] += BONO_LISTADA * min(c.pop("listadas"), MAX_LISTADAS)
            c["score"] += BONO_PISTA * (c["id"] in de_pistas)
            c["score"] -= CASTIGO_WIKI * (bool(libros) and c["fuente"] == "wikipedia")
        candidatos.sort(key=lambda c: -c["score"])
        elegidos = diversificar(candidatos, libros, self.k)
        if len(elegidos) < self.k:
            vistos = {c["id"] for c in elegidos}
            extra = [c for c in busqueda_vectorial(self.driver, embedding, self.k * 2) if c["id"] not in vistos]
            elegidos += extra[: self.k - len(elegidos)]
        return elegidos

    def describir(self, clave: str, donde: dict[str, str]) -> str:
        nombre = self.indice.nombre[clave]
        alias = self.indice.alias.get(nombre)
        extra = f"; en el texto también {', '.join(alias)}" if alias else ""
        return f"{nombre} ({self.indice.tipo[clave]}{extra}): {donde.get(clave, 'no aparece en los cantos')}"

    def __call__(self, pregunta: str) -> Recuperacion:
        c = analizar(pregunta)
        pistas, tipos, libros = c.pistas, c.tipos, c.libros
        semillas = self.indice.buscar(c.palabras)
        embedding = self.embedder.encode(pregunta).tolist()

        hechos = self.hechos(semillas, c) if semillas else []
        en = c.listar_en or libros
        listadas = self.por_tipo(tipos, en) if tipos and (not semillas or (en and not pistas)) else []

        mostrar = semillas + [c for c in listadas if c not in semillas]
        if libros:
            nombres = {h[x] for h in hechos[:HECHOS_GUIA] if h["tipo"] in pistas for x in ("a", "b")}
            mostrar += [c for c, n in self.indice.nombre.items() if n in nombres and c not in mostrar]
        donde = self.presencia(mostrar) if mostrar else {}
        entidades = [self.describir(c, donde) for c in mostrar if c in semillas or c in donde]

        lineas = []
        for h in hechos:
            fuentes = sorted(map(fuente_de_id, h["fragmentos"]), key=lambda f: isinstance(f, str))
            unicas = list(dict.fromkeys(map(texto_fuente, fuentes)))
            lineas.append(f"{h['a']} -{h['tipo']}-> {h['b']} (x{h['menciones']}) [{', '.join(unicas[:4])}]")

        fragmentos = self.fragmentos(semillas, hechos, pistas, embedding, libros, listadas)
        return Recuperacion(self.modo, pregunta, fragmentos, lineas, entidades)


if __name__ == "__main__":
    from rag import baseline

    sys.exit(baseline.main(GraphRAG, __doc__))
