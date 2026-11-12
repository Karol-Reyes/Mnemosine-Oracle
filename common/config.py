"""Configuración compartida: rutas del proyecto y variables del archivo .env."""
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Rutas de datos
DATA = ROOT / "data"
RAW = DATA / "raw"
WIKI = DATA / "wikipedia"
PROCESSED = DATA / "processed"
EQUIVALENCIAS = DATA / "equivalencias.csv"
ENTIDADES = DATA / "entidades.csv"
WIKIS_LISTA = DATA / "wikis.txt"

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "mnemosine123")

# LLM y embeddings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")   # gemini | ollama | openai (API compatible: Groq, OpenRouter...)
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "60"))  # una llamada más lenta se corta y se reintenta
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")         # solo para LLM_PROVIDER=openai
LLM_API_KEY = os.getenv("LLM_API_KEY", "")           # solo para LLM_PROVIDER=openai
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)

LIBROS = {"iliada": "Ilíada", "odisea": "Odisea"}
