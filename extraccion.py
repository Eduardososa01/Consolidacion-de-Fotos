"""
Lectura de fotos de listas de hospital con la vision de Claude.

Recibe la imagen de una lista (pizarra/hoja con nombres) y devuelve las personas
detectadas, para agregarlas a la seccion "Personas". Usa la API de Anthropic
(requiere ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import base64

import anthropic
from pydantic import BaseModel

import config

MODELO = "claude-opus-4-8"

MEDIA_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".gif": "image/gif",
}
EXTENSIONES_IMAGEN = set(MEDIA_TYPES.keys())


class PersonaLista(BaseModel):
    nombre: str    # nombre completo tal como aparece
    cedula: str    # cedula / identidad si aparece junto al nombre; "" si no


class ListaExtraida(BaseModel):
    personas: list[PersonaLista]


INSTRUCCIONES = """Eres un asistente que ayuda a coordinar ayuda en hospitales durante una emergencia en Venezuela.

En la imagen hay una lista, pizarra u hoja de un hospital con nombres de personas que ingresaron. A veces estan escritos a mano.

Tu tarea:
- Transcribe TODOS los nombres de personas que puedas leer, exactamente como aparecen.
- Si junto al nombre hay un numero de cedula/identidad, ponlo en "cedula" (solo digitos).
- Si un nombre es dudoso, transcribe lo que mejor puedas leer.
- No inventes nombres ni cedulas. Si la cedula no aparece, deja "".
"""


def hay_api() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def extraer_personas(datos_imagen: bytes, media_type: str) -> ListaExtraida:
    """Llama a Claude vision y devuelve la lista de personas leidas."""
    cliente = anthropic.Anthropic()
    datos = base64.standard_b64encode(datos_imagen).decode("utf-8")
    respuesta = cliente.messages.parse(
        model=MODELO,
        max_tokens=8000,
        output_format=ListaExtraida,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": media_type, "data": datos}},
                {"type": "text", "text": INSTRUCCIONES},
            ],
        }],
    )
    return respuesta.parsed_output
