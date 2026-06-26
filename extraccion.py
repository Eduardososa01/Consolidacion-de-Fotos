"""
Logica reutilizable de extraccion de nombres a partir de fotos de listas/pizarras
de hospitales, usando la vision de Claude.

La usan tanto el CLI (`extraer.py`) como la plataforma web (`app.py`).
Requiere la variable de entorno ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import base64
import unicodedata
from pathlib import Path

import anthropic
from pydantic import BaseModel

MODELO = "claude-opus-4-8"

MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
EXTENSIONES_IMAGEN = set(MEDIA_TYPES.keys())


class Persona(BaseModel):
    nombre: str          # nombre completo tal como aparece escrito
    cedula: str          # cedula / numero de identidad junto al nombre; "" si no
    estado: str          # condicion si aparece (estable, grave, etc.); "" si no
    notas: str           # otra info (edad, cama, observaciones); "" si no hay


class Pizarra(BaseModel):
    hospital: str            # nombre del hospital/centro si aparece; "" si no
    fecha: str               # fecha que aparece en la pizarra; "" si no
    lista_incompleta: bool   # True si la foto corta nombres (texto recortado)
    personas: list[Persona]  # lista de personas legibles en la foto


INSTRUCCIONES = """Eres un asistente que ayuda a localizar personas desaparecidas tras los terremotos en Venezuela.

En la imagen hay una pizarra, hoja o lista de un hospital con nombres de personas que ingresaron al centro de salud. A veces estan escritos a mano.

Tu tarea:
- Transcribe TODOS los nombres de personas que puedas leer, exactamente como aparecen.
- Si junto al nombre hay un numero de cedula / identidad, ponlo en "cedula" (solo digitos).
- Si un nombre es dudoso o ilegible, transcribe lo que puedas y anotalo en "notas".
- Si aparece el nombre del hospital o centro, ponlo en "hospital".
- Si aparece una fecha, ponla en "fecha".
- Si junto a un nombre hay una condicion (estable, grave, fallecido, UCI, etc.), ponla en "estado".
- Cualquier otro dato util (edad, numero de cama, observaciones) va en "notas".
- Pon "lista_incompleta": true si la foto esta recortada y hay nombres cortados o listas que no se ven completas.
- No inventes nombres ni cedulas. Si un campo no aparece, dejalo como cadena vacia "".
"""


def normalizar(nombre: str) -> str:
    """Quita acentos, mayusculas y espacios extra para poder comparar nombres."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", nombre)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_acentos.lower().split())


def extraer_pizarra(cliente: anthropic.Anthropic, ruta: Path) -> Pizarra:
    """Lee una imagen y devuelve la lista de personas detectadas por Claude."""
    ruta = Path(ruta)
    datos = base64.standard_b64encode(ruta.read_bytes()).decode("utf-8")
    media_type = MEDIA_TYPES[ruta.suffix.lower()]

    respuesta = cliente.messages.parse(
        model=MODELO,
        max_tokens=8000,
        output_format=Pizarra,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": datos,
                    },
                },
                {"type": "text", "text": INSTRUCCIONES},
            ],
        }],
    )
    return respuesta.parsed_output
