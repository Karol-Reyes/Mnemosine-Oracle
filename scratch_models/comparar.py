"""Compara los modelos desde cero: n-grama contra mini red.

Es la segunda metrica de la evaluacion del proyecto. Las dos perplejidades se
miden sobre **los mismos objetivos**: mismo vocabulario, misma particion y la
misma posicion de arranque en validacion. Sin eso el numero mas bajo puede ser
solo el del modelo al que le toco el examen mas facil.

Uso:  python -m scratch_models.comparar
"""
from __future__ import annotations

import json

from scratch_models.corpus import datos
from scratch_models.mini_red import VENTANA, entrenar
from scratch_models.ngramas import ModeloNgramas

from common.config import ROOT

SALIDA = ROOT / "eval" / "resultados" / "scratch_models.json"


def main() -> None:
    entrenamiento, validacion, vocab = datos()
    print(f"vocabulario: {len(vocab)}")
    print(f"entrenamiento: {len(entrenamiento)} tokens   validacion: {len(validacion)}")
    print(f"los dos modelos se evaluan desde la posicion {VENTANA} de validacion")
    print()

    filas = []

    print("--- n-gramas ---")
    for orden in (1, 2, 3, 4):
        modelo = ModeloNgramas(orden=orden)
        modelo.entrenar(entrenamiento, vocab)
        pp = modelo.perplejidad(validacion, desde=VENTANA)
        nombre = {1: "unigrama", 2: "bigrama", 3: "trigrama", 4: "4-grama"}[orden]
        filas.append({"modelo": nombre, "contexto": orden - 1, "perplejidad": round(pp, 1)})
        print(f"   {nombre:10} contexto {orden - 1}   perplejidad {pp:8.1f}")

    print()
    print("--- mini red ---")
    _, mejor = entrenar(entrenamiento, validacion, vocab)
    filas.append({"modelo": "mini red", "contexto": VENTANA, "perplejidad": round(mejor, 1)})

    print()
    print("=" * 52)
    print(f"{'modelo':12} {'contexto':>9} {'perplejidad':>13}")
    for fila in sorted(filas, key=lambda f: f["perplejidad"]):
        print(f"{fila['modelo']:12} {fila['contexto']:>9} {fila['perplejidad']:>13.1f}")

    mejor_ngrama = min(f["perplejidad"] for f in filas if f["modelo"] != "mini red")
    red = next(f["perplejidad"] for f in filas if f["modelo"] == "mini red")
    trigrama = next(f["perplejidad"] for f in filas if f["modelo"] == "trigrama")

    print()
    print(f"frente al mejor n-grama (bigrama): baja la perplejidad "
          f"{100 * (1 - red / mejor_ngrama):.0f} %")

    # Esta es la comparacion que importa: el trigrama y la mini red ven las
    # **mismas dos palabras** de contexto, asi que la diferencia no es cuanta
    # informacion recibe cada uno, es que hace con ella. El n-grama cuenta
    # secuencias exactas y una que no vio no le dice nada; la red representa
    # cada palabra como un vector, asi que lo que aprendio de "Aquiles" le
    # sirve para "Patroclo" si aparecen en contextos parecidos.
    print(f"con el MISMO contexto de 2 palabras, contra el trigrama: "
          f"{trigrama / red:.1f} veces mejor ({trigrama:.0f} -> {red:.0f})")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps({"vocabulario": len(vocab), "resultados": filas},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"guardado en {SALIDA.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
