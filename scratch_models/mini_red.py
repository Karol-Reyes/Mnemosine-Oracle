"""Mini red neuronal de lenguaje sobre los poemas, desde cero.

Predice la siguiente palabra a partir de las `VENTANA` anteriores. Es el mismo
esqueleto del taller 2 (una capa `nn.Embedding` y una `nn.Linear` encima), con
dos diferencias: los vectores de contexto se **concatenan** en vez de
promediarse, porque aca el orden de las palabras importa, y se agrega una capa
oculta para que la red pueda combinarlos y no solo sumarlos.

Uso:  python -m scratch_models.mini_red
"""
from __future__ import annotations

import math

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from pathlib import Path

from scratch_models.corpus import datos

CHECKPOINTS = Path(__file__).resolve().parent / "checkpoints"

VENTANA = 2          # cuantas palabras de contexto. igual que el bigrama mas una
DIM_EMBEDDING = 64
DIM_OCULTA = 128
LOTE = 128
EPOCAS = 8
TASA = 1e-3
SEMILLA = 42

torch.manual_seed(SEMILLA)


class MiniRed(nn.Module):
    def __init__(self, n_vocab: int, dim_embedding: int = DIM_EMBEDDING,
                 dim_oculta: int = DIM_OCULTA, ventana: int = VENTANA) -> None:
        super().__init__()
        self.embeddings = nn.Embedding(n_vocab, dim_embedding)
        self.oculta = nn.Linear(ventana * dim_embedding, dim_oculta)
        self.salida = nn.Linear(dim_oculta, n_vocab)

    def forward(self, contexto: torch.Tensor) -> torch.Tensor:
        # contexto llega como (lote, ventana)
        vectores = self.embeddings(contexto)          # (lote, ventana, dim_embedding)
        plano = vectores.flatten(start_dim=1)         # (lote, ventana * dim_embedding)
        return self.salida(torch.tanh(self.oculta(plano)))  # (lote, n_vocab)


def a_ventanas(tokens: list[str], indice: dict[str, int],
               ventana: int = VENTANA) -> TensorDataset:
    """Convierte la lista de palabras en pares (contexto, objetivo).

    El primer objetivo es el token en la posicion `ventana`, porque los
    anteriores no tienen contexto completo. El n-grama se evalua desde la misma
    posicion para que las perplejidades se puedan comparar.
    """
    contextos, objetivos = [], []
    for i in range(ventana, len(tokens)):
        contextos.append([indice[t] for t in tokens[i - ventana : i]])
        objetivos.append(indice[tokens[i]])
    return TensorDataset(torch.tensor(contextos), torch.tensor(objetivos))


def perdida_media(modelo: nn.Module, cargador: DataLoader,
                  criterio: nn.Module) -> float:
    """Entropia cruzada promedio por palabra, sin actualizar pesos."""
    modelo.eval()
    total, n = 0.0, 0
    with torch.no_grad():
        for contexto, objetivo in cargador:
            perdida = criterio(modelo(contexto), objetivo)
            total += perdida.item() * len(objetivo)
            n += len(objetivo)
    return total / n


def entrenar(entrenamiento: list[str], validacion: list[str], vocab: list[str],
             epocas: int = EPOCAS) -> tuple[MiniRed, float]:
    """Entrena y devuelve (modelo, mejor perplejidad en validacion)."""
    indice = {palabra: i for i, palabra in enumerate(vocab)}

    cargador_tr = DataLoader(
        a_ventanas(entrenamiento, indice), batch_size=LOTE, shuffle=True
    )
    cargador_va = DataLoader(a_ventanas(validacion, indice), batch_size=LOTE)

    modelo = MiniRed(len(vocab))
    criterio = nn.CrossEntropyLoss()
    optimizador = torch.optim.Adam(modelo.parameters(), lr=TASA)

    parametros = sum(p.numel() for p in modelo.parameters())
    print(f"parametros: {parametros:,}")
    print()
    print(f"{'epoca':>6} {'perdida_tr':>12} {'perdida_va':>12} {'perplejidad':>12}")

    mejor = float("inf")
    mejor_estado = None
    mejor_epoca = 0

    for epoca in range(1, epocas + 1):
        modelo.train()
        total, n = 0.0, 0
        for contexto, objetivo in cargador_tr:
            optimizador.zero_grad()
            perdida = criterio(modelo(contexto), objetivo)
            perdida.backward()
            optimizador.step()
            total += perdida.item() * len(objetivo)
            n += len(objetivo)

        perdida_va = perdida_media(modelo, cargador_va, criterio)
        # la perplejidad es exp de la entropia cruzada, asi que es la misma
        # medida que la perdida pero en unidades comparables con el n-grama
        perplejidad = math.exp(perdida_va)
        aviso = ""
        if perplejidad < mejor:
            mejor, mejor_epoca = perplejidad, epoca
            mejor_estado = {k: v.clone() for k, v in modelo.state_dict().items()}
            aviso = "  <- mejor"
        print(f"{epoca:>6} {total / n:>12.4f} {perdida_va:>12.4f} {perplejidad:>12.1f}{aviso}")

    # Se vuelve al mejor estado. Desde la epoca 5 la perdida de entrenamiento
    # sigue bajando y la de validacion sube: la red empieza a memorizar los
    # poemas. Si no se restaura, lo que queda es el modelo sobreajustado y los
    # vecinos de los embeddings se miran sobre el peor de todos.
    if mejor_estado is not None:
        modelo.load_state_dict(mejor_estado)
        print(f"\nse vuelve a la epoca {mejor_epoca}, que fue la mejor")

    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    torch.save({"estado": modelo.state_dict(), "vocab": vocab}, CHECKPOINTS / "mini_red.pt")

    return modelo, mejor


def vecinos(modelo: MiniRed, vocab: list[str], palabra: str, k: int = 6) -> list[str]:
    """Las palabras con el embedding mas parecido, por similitud coseno.

    Es la misma medida del taller 2, y sirve para ver si la capa de embeddings
    aprendio algo o solo memorizo: si "aquiles" queda cerca de otros heroes, la
    red capto que ocupan el mismo lugar en las frases.
    """
    indice = {p: i for i, p in enumerate(vocab)}
    if palabra not in indice:
        return []

    pesos = modelo.embeddings.weight.detach()
    objetivo = pesos[indice[palabra]]
    similitudes = nn.functional.cosine_similarity(pesos, objetivo.unsqueeze(0))
    mejores = torch.argsort(similitudes, descending=True)[: k + 1]
    return [vocab[i] for i in mejores.tolist() if vocab[i] != palabra][:k]


def main() -> None:
    entrenamiento, validacion, vocab = datos()
    print(f"vocabulario: {len(vocab)}   entrenamiento: {len(entrenamiento)} tokens")
    print()

    modelo, mejor = entrenar(entrenamiento, validacion, vocab)
    print()
    print(f"mejor perplejidad en validacion: {mejor:.1f}")
    print()
    print("vecinos en el espacio de embeddings:")
    for palabra in ("aquiles", "nave", "dioses"):
        print(f"   {palabra:10} -> {', '.join(vecinos(modelo, vocab, palabra))}")


if __name__ == "__main__":
    main()
