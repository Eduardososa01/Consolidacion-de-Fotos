"""
Procesa TODAS las fotos de listas (carpeta fotos/extraidas/) con la vision de
Claude y arma un CSV/Excel con las personas. Es un script APARTE de la pagina web.

Uso (en tu PowerShell):
    $env:ANTHROPIC_API_KEY = "sk-ant-...tu-clave-real..."
    py extraer_a_csv.py

Resultado: lista_personas.csv  (se abre en Excel; columnas nombre, cedula, edad, ...).
Va guardando el avance foto por foto, asi que si se corta no pierdes lo ya hecho.
"""

from __future__ import annotations

import base64
import csv
import os
import sys
from pathlib import Path

import anthropic
from pydantic import BaseModel

MODELO = "claude-opus-4-8"
CARPETA = Path(__file__).parent / "fotos" / "extraidas"
SALIDA = Path(__file__).parent / "lista_personas.csv"

MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}


class Persona(BaseModel):
    nombre: str            # nombre completo tal como aparece
    cedula: str            # cedula / identidad si aparece; "" si no
    edad: str              # edad si aparece; "" si no
    seccion: str           # seccion/area si la hoja la indica (Triage, Fallecidos, etc.); "" si no
    estado: str            # estado/condicion si aparece; "" si no
    notas: str             # cualquier otra cosa util o si el nombre es dudoso


class Lista(BaseModel):
    personas: list[Persona]


INSTRUCCIONES = """En la imagen hay una o varias hojas/listas escritas a mano de un hospital con personas.
Transcribe TODAS las personas que puedas leer en TODAS las hojas visibles.
- "nombre": el nombre completo tal como aparece.
- "cedula": el numero de cedula/identidad si esta junto al nombre (solo digitos); "" si no.
- "edad": la edad si aparece; "" si no.
- "seccion": el titulo de la hoja/seccion donde esta la persona (ej. Triage, Sala de Parto, Fallecidos, Trauma/Shock) si se ve; "" si no.
- "estado": cualquier condicion que aparezca; "" si no.
- "notas": pon aqui si el nombre es dudoso/ilegible (transcribe lo mejor que puedas).
No inventes nombres ni cedulas. Si algo no aparece, deja "".
"""


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: falta ANTHROPIC_API_KEY.")
        print('  En PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-...tu-clave..."')
        return 1
    if not CARPETA.exists():
        print(f"No existe la carpeta {CARPETA}")
        return 1

    imagenes = sorted(p for p in CARPETA.iterdir()
                      if p.suffix.lower() in MEDIA_TYPES)
    if not imagenes:
        print(f"No hay imagenes en {CARPETA}")
        return 0

    cliente = anthropic.Anthropic()
    print(f"Procesando {len(imagenes)} foto(s)...\n")

    with SALIDA.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["foto", "nombre", "cedula", "edad", "seccion", "estado", "notas"])
        total = 0
        for i, ruta in enumerate(imagenes, 1):
            print(f"[{i}/{len(imagenes)}] {ruta.name} ...", end=" ")
            try:
                datos = base64.standard_b64encode(ruta.read_bytes()).decode("utf-8")
                resp = cliente.messages.parse(
                    model=MODELO, max_tokens=16000, output_format=Lista,
                    messages=[{"role": "user", "content": [
                        {"type": "image", "source": {"type": "base64",
                         "media_type": MEDIA_TYPES[ruta.suffix.lower()], "data": datos}},
                        {"type": "text", "text": INSTRUCCIONES},
                    ]}],
                )
                personas = resp.parsed_output.personas
            except Exception as e:  # noqa: BLE001
                print(f"ERROR: {e}")
                continue
            for p in personas:
                w.writerow([ruta.name, p.nombre, p.cedula, p.edad,
                            p.seccion, p.estado, p.notas])
            f.flush()
            total += len(personas)
            print(f"{len(personas)} persona(s)")

    print(f"\nListo. {total} filas en: {SALIDA}")
    print("Tip: en Excel puedes ordenar por 'nombre' y quitar duplicados (Datos -> Quitar duplicados).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
