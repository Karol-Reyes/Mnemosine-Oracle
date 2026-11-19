"""Corpus de entrenamiento para los modelos desde cero.

Los dos modelos (n-grama y mini red) tienen que compartir tokenizacion,
vocabulario y particion. Si no, la perplejidad de uno no se puede comparar con
la del otro: un vocabulario mas chico baja la perplejidad sin que el modelo sea
mejor.

Uso:  python -m scratch_models.corpus
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

from common.config import PROCESSED

CORPUS = PROCESSED / "corpus_entrenamiento.txt"

# Las ultimas palabras del corpus quedan para validar. Se corta por el final y
# no al azar para no partir el texto en mitad de una escena y dejar en la
# validacion frases que el modelo ya vio en entrenamiento.
FRACCION_VALIDACION = 0.1

# Una palabra que aparece una sola vez no se puede aprender, y mete una entrada
# al vocabulario que solo sirve para inflarlo. Se reemplazan por <unk>, que es
# lo que permite que el n-grama y la red trabajen sobre el mismo vocabulario
# cerrado.
MIN_FRECUENCIA = 2

UNK = "<unk>"


def normalizar(texto: str) -> str:
    """Minusculas y sin signos, pero **con tildes**.

    En espanol la tilde distingue palabras: "cantó" (lo que hizo) y "canto" (el
    canto de la Ilíada) son dos cosas, igual que "él" y "el". Quitarlas las
    juntaria en una sola entrada del vocabulario. Lo que si se va es la
    puntuacion, porque los signos terminan pegados a las palabras.
    """
    texto = unicodedata.normalize("NFC", texto.lower())
    return " ".join(re.findall(r"[a-záéíóúüñ]+", texto))


def tokenizar(texto: str) -> list[str]:
    return normalizar(texto).split(" ")


def cargar() -> list[str]:
    if not CORPUS.exists():
        raise FileNotFoundError(
            f"No existe {CORPUS}. Corre primero:  python -m ingest.prepare"
        )
    return tokenizar(CORPUS.read_text(encoding="utf-8"))


def partir(tokens: list[str]) -> tuple[list[str], list[str]]:
    corte = int(len(tokens) * (1 - FRACCION_VALIDACION))
    return tokens[:corte], tokens[corte:]


def vocabulario(tokens: list[str], min_frecuencia: int = MIN_FRECUENCIA) -> list[str]:
    """El vocabulario se arma **solo con el entrenamiento**.

    Si se armara con todo el corpus, el modelo tendria una entrada reservada
    para palabras que solo aparecen en validacion, y eso es mirar el examen
    antes de darlo.
    """
    conteo = Counter(tokens)
    palabras = sorted(p for p, n in conteo.items() if n >= min_frecuencia)
    return [UNK] + palabras


def aplicar_unk(tokens: list[str], vocab: set[str]) -> list[str]:
    return [t if t in vocab else UNK for t in tokens]


def datos() -> tuple[list[str], list[str], list[str]]:
    """Devuelve (entrenamiento, validacion, vocabulario), ya con <unk>."""
    entrenamiento, validacion = partir(cargar())
    vocab = vocabulario(entrenamiento)
    conjunto = set(vocab)
    return (
        aplicar_unk(entrenamiento, conjunto),
        aplicar_unk(validacion, conjunto),
        vocab,
    )


if __name__ == "__main__":
    tokens = cargar()
    entrenamiento, validacion, vocab = datos()

    print(f"tokens en el corpus:   {len(tokens)}")
    print(f"palabras distintas:    {len(set(tokens))}")
    print(f"vocabulario (freq>={MIN_FRECUENCIA}): {len(vocab)}")
    print()
    print(f"entrenamiento: {len(entrenamiento)} tokens")
    print(f"validacion:    {len(validacion)} tokens")

    unks = sum(1 for t in validacion if t == UNK)
    print(f"<unk> en validacion: {unks} ({100 * unks / len(validacion):.1f} %)")
    print()
    print("primeras palabras:", " ".join(entrenamiento[:14]))
