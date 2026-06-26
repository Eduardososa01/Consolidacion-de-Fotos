"""
CLI para procesar en lote las fotos de la carpeta "fotos/".

Lee cada imagen, extrae los nombres con la vision de Claude y los guarda en la
misma base de datos que usa la web (como registros de tipo 'lista').

Uso:
    $env:ANTHROPIC_API_KEY = "tu-clave"
    py extraer.py

Para el flujo normal usa la web (py -m uvicorn app:app --reload); este CLI es
util para cargar muchas fotos de golpe.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import anthropic

import db
from extraccion import EXTENSIONES_IMAGEN, extraer_pizarra

CARPETA_FOTOS = Path(__file__).parent / "fotos"


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: falta la variable de entorno ANTHROPIC_API_KEY.")
        print('  En PowerShell:  $env:ANTHROPIC_API_KEY = "tu-clave"')
        return 1

    CARPETA_FOTOS.mkdir(exist_ok=True)
    imagenes = sorted(
        p for p in CARPETA_FOTOS.iterdir()
        if p.suffix.lower() in EXTENSIONES_IMAGEN
    )
    if not imagenes:
        print(f"No hay imagenes en {CARPETA_FOTOS}")
        print("Pon las fotos de las listas ahi y vuelve a correr el script.")
        return 0

    cliente = anthropic.Anthropic()
    db.crear_tablas()
    total = 0

    for ruta in imagenes:
        print(f"Procesando {ruta.name} ...")
        try:
            pizarra = extraer_pizarra(cliente, ruta)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR al procesar {ruta.name}: {e}")
            continue

        _, n = db.guardar_lista(ruta.read_bytes(), pizarra)
        total += n
        hosp = f" [{pizarra.hospital}]" if pizarra.hospital else ""
        print(f"  OK: {n} persona(s){hosp}")
        if pizarra.lista_incompleta:
            print("  AVISO: la foto parece recortada; puede faltar gente.")

    print(f"\nListo. Personas nuevas agregadas: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
