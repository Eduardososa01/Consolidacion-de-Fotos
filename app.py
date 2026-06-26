"""
Plataforma "Reconexion" — personas encontradas -> familias.

Cualquiera puede:
  - subir la FOTO DE UNA LISTA de hospital (se extraen los nombres con vision de Claude), o
  - subir la foto de UNA PERSONA encontrada con sus datos.
Las familias buscan por nombre o cedula para ver si su familiar esta registrado.

Las fotos y los datos se guardan en la base de datos (SQLite en local, Postgres en
produccion). Correr en local:
    $env:ANTHROPIC_API_KEY = "tu-clave"
    py -m uvicorn app:app --reload
"""

from __future__ import annotations

from pathlib import Path

import anthropic
import jinja2
from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

import config
import db
from extraccion import EXTENSIONES_IMAGEN, extraer_pizarra

BASE = Path(__file__).parent

app = FastAPI(title="Reconexion")

# cache_size=0 evita un bug del cache de plantillas de Jinja2 en Python 3.14.
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(BASE / "templates")),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
    cache_size=0,
)
templates = Jinja2Templates(env=_jinja_env)

# Crear las tablas al arrancar (idempotente).
db.crear_tablas()


def _cliente_anthropic() -> anthropic.Anthropic | None:
    if not config.ANTHROPIC_API_KEY:
        return None
    return anthropic.Anthropic()


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request, q: str = "", hospital: str = "", ciudad: str = ""):
    busco = bool(q or hospital or ciudad)
    resultados = db.buscar(q=q, hospital=hospital, ciudad=ciudad)
    stats = db.contar()
    return templates.TemplateResponse(request, "index.html", {
        "resultados": resultados, "q": q, "hospital": hospital,
        "ciudad": ciudad, "busco": busco, "stats": stats,
    })


@app.get("/subir", response_class=HTMLResponse)
def subir_form(request: Request):
    return templates.TemplateResponse(request, "subir.html", {})


@app.post("/subir", response_class=HTMLResponse)
async def subir(
    request: Request,
    tipo: str = Form(...),
    foto: UploadFile = File(...),
    nombre: str = Form(""),
    cedula: str = Form(""),
    hospital: str = Form(""),
    ciudad: str = Form(""),
    fecha: str = Form(""),
    observaciones: str = Form(""),
):
    ext = Path(foto.filename or "").suffix.lower()
    if ext not in EXTENSIONES_IMAGEN:
        return templates.TemplateResponse(request, "subir.html", {
            "error": "El archivo no es una imagen valida (jpg, png, webp...).",
        })
    datos = await foto.read()

    if tipo == "lista":
        cliente = _cliente_anthropic()
        if cliente is None:
            return templates.TemplateResponse(request, "subir.html", {
                "error": "Falta configurar ANTHROPIC_API_KEY en el servidor "
                         "para poder leer los nombres de la lista.",
            })
        # Escribir la imagen a un archivo temporal para reusar extraer_pizarra.
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(datos)
            tmp_path = tmp.name
        try:
            pizarra = extraer_pizarra(cliente, tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        _, n = db.guardar_lista(datos, pizarra, ciudad=ciudad)
        mensaje = f"Lista subida: se extrajeron {n} persona(s)."
        if pizarra.lista_incompleta:
            mensaje += " Aviso: la foto parece recortada; podria faltar gente."
    else:
        db.guardar_persona(datos, nombre=nombre, cedula=cedula, hospital=hospital,
                           ciudad=ciudad, fecha=fecha, observaciones=observaciones)
        mensaje = "Persona registrada."

    return templates.TemplateResponse(request, "subir.html", {"mensaje": mensaje})


@app.get("/foto/{registro_id}")
def foto(registro_id: int):
    res = db.obtener_foto(registro_id)
    if res is None:
        return Response(status_code=404)
    datos, mime = res
    return Response(content=datos, media_type=mime,
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/persona/{persona_id}", response_class=HTMLResponse)
def detalle(request: Request, persona_id: int):
    persona = db.obtener_persona(persona_id)
    if persona is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "persona.html", {"p": persona})
