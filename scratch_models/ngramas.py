"""Modelo de lenguaje de n-gramas sobre los poemas, desde cero.

Es el modelo del taller 1 del curso (add-k smoothing y backoff) aplicado al
corpus de la Ilíada y la Odisea, y sirve como piso de comparacion: es un modelo
de lenguaje que no entiende nada, solo cuenta.

Uso:  python -m scratch_models.ngramas
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict

from scratch_models.corpus import UNK, datos, tokenizar

# Bigrama, no trigrama. Lo medimos y la perplejidad **empeora** al subir el
# orden: 223.5 con bigrama, 485.8 con trigrama, 692.9 con 4-grama.
#
# No es un error, es escasez de datos. El corpus tiene 82 mil tokens de
# entrenamiento y 4.811 palabras de vocabulario, asi que casi todos los
# contextos de tres palabras se vieron una sola vez. Para un contexto visto una
# vez, add-k da (1 + k) / (1 + k·V), y con V = 4.811 el denominador vale ~49:
# la unica continuacion observada se queda con 0.02 de probabilidad. El backoff
# no ayuda ahi, porque el contexto **si** existe y por eso no se acorta.
ORDEN = 2
K = 0.01         # add-k. con k mas grande la distribucion se aplana demasiado
SEMILLA = 42

# Al generar se muestrea solo entre continuaciones vistas, asi que la escasez que
# castiga la perplejidad del trigrama aqui no pesa y el contexto extra da frases coherentes.
ORDEN_GENERACION = 3


class ModeloNgramas:
    """Cuenta n-gramas de orden 1 hasta `orden` y combina los ordenes con backoff.

    La probabilidad de una palabra se calcula con el contexto **mas largo que
    exista** en los conteos; si ese contexto no se vio nunca, se acorta. Sobre
    el orden que quede se aplica add-k, que es lo que evita las probabilidades
    en cero y lo que permite calcular perplejidad: un solo cero la volveria
    infinita.

    El orden 0 es el unigrama con contexto vacio, que siempre existe, asi que
    el backoff nunca se queda sin respuesta.
    """

    def __init__(self, orden: int = ORDEN, k: float = K) -> None:
        self.orden = orden
        self.k = k
        self.conteos: dict[int, dict[str, Counter]] = {
            tamano: defaultdict(Counter) for tamano in range(orden)
        }
        self.totales: dict[int, dict[str, int]] = {
            tamano: defaultdict(int) for tamano in range(orden)
        }
        self.vocab: list[str] = []

    def entrenar(self, tokens: list[str], vocab: list[str]) -> None:
        self.vocab = vocab
        self.n_vocab = len(vocab)

        for tamano in range(self.orden):
            for i in range(tamano, len(tokens)):
                contexto = " ".join(tokens[i - tamano : i])
                self.conteos[tamano][contexto][tokens[i]] += 1
                self.totales[tamano][contexto] += 1

    def probabilidad(self, palabra: str, contexto: list[str]) -> float:
        """P(palabra | contexto), con backoff y add-k."""
        for tamano in range(min(self.orden - 1, len(contexto)), -1, -1):
            clave = " ".join(contexto[len(contexto) - tamano :]) if tamano else ""
            if clave in self.totales[tamano]:
                conteo = self.conteos[tamano][clave][palabra]
                total = self.totales[tamano][clave]
                return (conteo + self.k) / (total + self.k * self.n_vocab)
        # no deberia llegar aca porque el unigrama siempre existe
        return 1 / self.n_vocab

    def perplejidad(self, tokens: list[str], desde: int | None = None) -> float:
        """Perplejidad por palabra: exp del promedio del log negativo.

        `desde` es la primera posicion que se evalua. Por defecto es
        `orden - 1`, que es la primera palabra con contexto completo, pero
        `comparar.py` le pasa la misma posicion que usa la mini red: si un
        modelo se mide sobre mas objetivos que el otro, las dos perplejidades
        no son comparables aunque esten en las mismas unidades.
        """
        inicio = self.orden - 1 if desde is None else desde
        suma = 0.0
        n = 0
        for i in range(inicio, len(tokens)):
            contexto = tokens[i - (self.orden - 1) : i]
            suma += math.log(self.probabilidad(tokens[i], contexto))
            n += 1
        return math.exp(-suma / n)

    def continuaciones(self, contexto: list[str]) -> Counter:
        """Palabras que siguieron al contexto mas largo visto en el corpus, sin <unk>."""
        for tamano in range(min(self.orden - 1, len(contexto)), -1, -1):
            clave = " ".join(contexto[len(contexto) - tamano :]) if tamano else ""
            vistas = self.conteos[tamano].get(clave, {})
            opciones = Counter({p: n for p, n in vistas.items() if p != UNK})
            if opciones:
                return opciones
        return Counter()

    def generar(self, contexto: str, n_palabras: int = 30, temperatura: float = 1.0,
                azar: random.Random | None = None) -> str:
        """Texto de muestra, para mirar cualitativamente que aprendio.

        No usa add-k: sirve para medir, pero al generar hace que la mayoria de las
        palabras salgan del reparto uniforme y no del corpus. La temperatura baja
        favorece las continuaciones frecuentes y la alta las raras.
        """
        if temperatura <= 0:
            raise ValueError("la temperatura debe ser mayor que 0")
        azar = azar or random
        generados = [t for t in tokenizar(contexto) if t]
        for _ in range(n_palabras):
            opciones = self.continuaciones(generados)
            palabras = list(opciones)
            pesos = [opciones[p] ** (1 / temperatura) for p in palabras]
            generados.append(azar.choices(palabras, weights=pesos, k=1)[0])
        return " ".join(generados)

def main() -> None:
    random.seed(SEMILLA)
    entrenamiento, validacion, vocab = datos()

    print(f"vocabulario: {len(vocab)}   entrenamiento: {len(entrenamiento)} tokens")
    print()
    print("perplejidad en validacion, por orden:")
    for orden in (1, 2, 3, 4):
        modelo = ModeloNgramas(orden=orden)
        modelo.entrenar(entrenamiento, vocab)
        print(f"   orden {orden}  (contexto {orden - 1})   {modelo.perplejidad(validacion):8.1f}")

    print()
    print(f"efecto de k en el orden {ORDEN}:")
    for k in (1.0, 0.1, 0.01, 0.001):
        modelo = ModeloNgramas(orden=ORDEN, k=k)
        modelo.entrenar(entrenamiento, vocab)
        print(f"   k = {k:<6} {modelo.perplejidad(validacion):8.1f}")

    generador = ModeloNgramas(orden=ORDEN_GENERACION)
    generador.entrenar(entrenamiento, vocab)
    print()
    print(f"texto generado (orden {ORDEN_GENERACION}):")
    for contexto in ("canta oh", "el divino"):
        print(f"   «{generador.generar(contexto, 22)}»")


if __name__ == "__main__":
    main()
