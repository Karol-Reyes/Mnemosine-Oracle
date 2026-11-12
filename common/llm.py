"""Acceso al LLM: elección de proveedor y llamadas con reintentos ante errores transitorios."""
from __future__ import annotations

import random
import re
import time

TRANSITORIO = re.compile(
    r"\b(429|500|502|503|504)\b|UNAVAILABLE|RESOURCE_EXHAUSTED|DEADLINE_EXCEEDED|INTERNAL"
    r"|timed? ?out|timeout|ConnectError|ConnectionError|RemoteProtocolError|disconnected",
    re.I,
)


def es_transitorio(error: Exception) -> bool:
    """True si el error suele pasar solo (sobrecarga, cuota por minuto, fallo del servidor, timeout).

    Un 404 (modelo retirado) o un 400/401/403 (clave inválida) no son transitorios: no se reintentan.
    """
    return bool(TRANSITORIO.search(str(error)))


def con_reintentos(fn, *args, intentos: int = 5, espera_base: float = 4.0, espera_max: float = 60.0, **kwargs):
    """Ejecuta fn(*args, **kwargs); ante un error transitorio espera (4, 8, 16, 32 s, con jitter) y reintenta.

    Uso:  respuesta = con_reintentos(llm.invoke, "prompt")
    """
    for intento in range(1, intentos + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if intento == intentos or not es_transitorio(e):
                raise
            espera = min(espera_base * 2 ** (intento - 1), espera_max) * random.uniform(0.75, 1.25)
            print(f"     LLM ocupado ({str(e)[:70]}...); reintento {intento}/{intentos - 1} en {espera:.0f} s")
            time.sleep(espera)


def crear_llm(proveedor: str | None = None, modelo: str | None = None):
    """Crea el LLM de neo4j-graphrag según LLM_PROVIDER del .env (o según el argumento).

    gemini -> Gemini (GEMINI_API_KEY). Lleva timeout: sin él, una llamada colgada espera sin fin.
    ollama -> modelo local con Ollama (OLLAMA_HOST). Requiere `pip install ollama`.
    openai -> cualquier API compatible con OpenAI (Groq, OpenRouter, ...): LLM_BASE_URL + LLM_API_KEY.
              Requiere `pip install openai`.
    """
    from common import config

    proveedor = (proveedor or config.LLM_PROVIDER).strip().lower()
    modelo = modelo or config.LLM_MODEL
    if proveedor == "gemini":
        from google.genai import types
        from neo4j_graphrag.llm import GeminiLLM

        return GeminiLLM(
            model_name=modelo,
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=int(config.LLM_TIMEOUT_S * 1000)),  # en milisegundos
        )
    if proveedor == "ollama":
        from neo4j_graphrag.llm import OllamaLLM

        # un modelo local tarda en cargarse la primera vez: timeout más holgado
        return OllamaLLM(model_name=modelo, host=config.OLLAMA_HOST, timeout=max(config.LLM_TIMEOUT_S, 300))
    if proveedor == "openai":
        from neo4j_graphrag.llm import OpenAILLM

        return OpenAILLM(
            model_name=modelo,
            base_url=config.LLM_BASE_URL or None,
            api_key=config.LLM_API_KEY,
            timeout=config.LLM_TIMEOUT_S,
        )
    raise ValueError(f"LLM_PROVIDER desconocido: {proveedor!r} (usa gemini, ollama u openai)")
