"""Esquema fijo del grafo de conocimiento.
Fijar el esquema evita que el LLM invente tipos de nodo y de relación en cada fragmento
"""

NODE_TYPES = [
    {"label": "Deidad", "description": "Dios, diosa, ninfa o titán (Zeus, Atenea, Tetis, Calipso, Helios)."},
    {"label": "Personaje", "description": "Mortal o héroe con nombre propio (Aquiles, Héctor, Penélope, Euriclea)."},
    {"label": "Criatura", "description": "Monstruo o ser fantástico (Polifemo, Escila, Caribdis, las Sirenas)."},
    {"label": "Lugar", "description": "Ciudad, isla, región o lugar mítico (Troya, Ítaca, Pilos, el Olimpo, el Hades)."},
    {"label": "Grupo", "description": "Pueblo o colectivo (aqueos, troyanos, feacios, pretendientes)."},
    {"label": "Objeto", "description": "Objeto con nombre o importancia narrativa (las armas de Aquiles, la balsa de Ulises)."},
]

RELATIONSHIP_TYPES = [
    {"label": "HIJO_DE", "description": "El origen es hijo o hija del destino."},
    {"label": "HERMANO_DE", "description": "Hermanos o medio hermanos."},
    {"label": "ESPOSO_DE", "description": "Matrimonio o unión de pareja."},
    {"label": "AMA_A", "description": "Relación amorosa o deseo."},
    {"label": "MATA_A", "description": "El origen da muerte al destino."},
    {"label": "ENFRENTA_A", "description": "Combate, disputa u hostilidad sin muerte."},
    {"label": "AYUDA_A", "description": "Protege, aconseja, guía o favorece al destino."},
    {"label": "APOYA_A", "description": "Una deidad o personaje toma partido por un grupo (p. ej. Apolo apoya a los troyanos)."},
    {"label": "ORDENA_A", "description": "Da una orden o envía un mensaje al destino."},
    {"label": "VIAJA_A", "description": "Llega o navega a un lugar."},
    {"label": "VIVE_EN", "description": "Habita o reina en un lugar."},
    {"label": "PERTENECE_A", "description": "Un personaje forma parte de un grupo (Héctor pertenece a los troyanos)."},
    {"label": "CREA", "description": "Fabrica o forja un objeto (Hefesto crea las armas de Aquiles)."},
    {"label": "POSEE", "description": "Tiene o usa un objeto."},
]

_SERES = ["Deidad", "Personaje", "Criatura"]
PATTERNS = (
    [(a, r, b) for a in _SERES for b in _SERES
     for r in ["HIJO_DE", "HERMANO_DE", "ESPOSO_DE", "AMA_A", "MATA_A", "ENFRENTA_A", "AYUDA_A", "ORDENA_A"]]
    + [(a, "APOYA_A", "Grupo") for a in _SERES]
    + [(a, "PERTENECE_A", "Grupo") for a in ["Personaje", "Criatura"]]
    + [(a, r, "Lugar") for a in _SERES for r in ["VIAJA_A", "VIVE_EN"]]
    + [(a, r, "Objeto") for a in ["Deidad", "Personaje"] for r in ["CREA", "POSEE"]]
)

SCHEMA = {
    "node_types": NODE_TYPES,
    "relationship_types": RELATIONSHIP_TYPES,
    "patterns": PATTERNS,
    "additional_node_types": False,
    "additional_relationship_types": False,
    "additional_patterns": False,
}
