"""Genera docs/arquitectura.svg (diagrama de arquitectura del proyecto).

Uso:  python docs/generar_diagrama.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

out = []


def caja(x, y, w, h, titulo, lineas=()):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#f4f4f4" stroke="#222" stroke-width="1.5"/>')
    out.append(f'<text x="{x + 12}" y="{y + 26}" font-size="16" font-weight="bold">{escape(titulo)}</text>')
    for i, l in enumerate(lineas):
        out.append(f'<text x="{x + 12}" y="{y + 50 + 19 * i}" font-size="14">{escape(l)}</text>')


def flecha(d):
    out.append(f'<path d="{d}" fill="none" stroke="#222" stroke-width="1.5" marker-end="url(#p)"/>')


def titulo_columna(x, w, t):
    out.append(f'<text x="{x + w / 2}" y="30" font-size="15" font-weight="bold" text-anchor="middle">{escape(t)}</text>')


titulo_columna(30, 210, "Fuentes")
titulo_columna(300, 220, "Preparación")
titulo_columna(580, 250, "Base de datos")
titulo_columna(890, 200, "Recuperación")
titulo_columna(1150, 200, "Agente e interfaz")

caja(30, 50, 210, 60, "La Ilíada", ["8 cantos"])
caja(30, 120, 210, 60, "La Odisea", ["8 cantos"])
caja(30, 190, 210, 60, "Wikipedia", ["53 artículos"])
caja(30, 280, 210, 80, "Listas de nombres", ["equivalencias.csv", "entidades.csv"])

caja(300, 50, 220, 130, "Preparar los textos", ["Se limpia la ortografía", "de los cantos y se parten", "en fragmentos"])
caja(300, 210, 220, 150, "Construir el grafo", ["Gemini saca personajes", "y relaciones de cada", "fragmento"])

caja(580, 50, 250, 310, "Neo4j")
caja(600, 90, 210, 110, "Grafo", ["Personajes, dioses, lugares", "y sus relaciones"])
caja(600, 215, 210, 130, "Fragmentos", ["El texto de los cantos y", "de Wikipedia con sus", "embeddings"])

caja(890, 50, 200, 120, "RAG normal", ["Busca los 5 fragmentos", "más parecidos a la", "pregunta"])
caja(890, 200, 200, 160, "GraphRAG", ["Busca los personajes de", "la pregunta en el grafo", "y trae sus relaciones", "y fragmentos"])

caja(1150, 80, 200, 150, "Agente (LangGraph)", ["Decide si usa RAG o", "GraphRAG y responde", "con citas"])
caja(1150, 260, 200, 90, "Interfaz (Gradio)", ["Chat para hacer", "las preguntas"])

caja(30, 420, 490, 110, "Modelos desde cero", ["N-grama y mini red entrenados con el texto", "de los poemas. Se comparan con la perplejidad."])
caja(580, 420, 510, 110, "Evaluación", ["20 preguntas para comparar RAG y GraphRAG", "con el puntaje de un juez y el recall."])
caja(1150, 420, 200, 110, "Resultados", ["Tabla final con todo"])

for d in ("M240 80 H300", "M240 150 H300", "M240 220 H300", "M240 320 H300", "M410 180 V210",
          "M520 285 H580", "M830 110 H890", "M830 280 H890", "M1090 110 H1150", "M1090 240 H1150",
          "M1250 230 V260", "M1090 475 H1150"):
    flecha(d)
flecha("M30 85 H12 V475 H30")
out.append('<path d="M30 150 H12" stroke="#222" stroke-width="1.5"/>')
flecha("M1120 110 V475 H1090")
for cy in (110, 240):
    out.append(f'<circle cx="1120" cy="{cy}" r="3.5" fill="#222"/>')

W, H = 1380, 560
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
       f'font-family="Arial, Helvetica, sans-serif" fill="#222">\n'
       '<defs><marker id="p" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" '
       'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#222"/></marker></defs>\n'
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n' + "\n".join(out) + "\n</svg>\n")
destino = Path(__file__).with_name("arquitectura.svg")
destino.write_text(svg, encoding="utf-8")
print(f"escrito {destino}")
