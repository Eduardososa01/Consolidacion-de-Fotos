"""
Plataforma de coordinacion de ayuda humanitaria en hospitales.

- Publico: ve hospitales, su estado y las necesidades (requests) en tiempo real,
  y se compromete a enviar insumos (sin cuenta).
- Capitanes: una cuenta por hospital; actualizan el estado del hospital y
  gestionan los requests y sus estados.

Correr en local:
    py seed.py                  # crea hospitales y capitanes (una vez)
    py -m uvicorn app:app --reload
"""

from __future__ import annotations

from pathlib import Path

import jinja2
import csv
import io

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import auth
import config
import db

BASE = Path(__file__).parent

app = FastAPI(title="Red de Informacion Hospitales e Insumos")
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)

# cache_size=0 evita un bug del cache de plantillas de Jinja2 en Python 3.14.
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(BASE / "templates")),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
    cache_size=0,
)
# Exponer etiquetas y catalogos a las plantillas.
_jinja_env.globals.update(
    ETIQUETAS=db.ETIQUETAS, INSUMOS=db.INSUMOS, PRIORIDADES=db.PRIORIDADES,
    ESTADOS=db.ESTADOS, SEMAFOROS=db.SEMAFOROS, RECIBIENDO=db.RECIBIENDO,
    CAPACIDADES=db.CAPACIDADES, TIPOS_SANGRE=db.TIPOS_SANGRE,
    tiempo_relativo=db.tiempo_relativo, UMBRAL_VIEJO=db.UMBRAL_HORAS_VIEJO,
    PUBLIC_BASE_URL=config.PUBLIC_BASE_URL,
)
templates = Jinja2Templates(env=_jinja_env)

db.crear_tablas()

# Auto-carga: si la base esta vacia (primer arranque), crea los 10 hospitales y
# sus capitanes. Las credenciales se imprimen en los logs del servidor.
try:
    if db.resumen()["hospitales"] == 0:
        import seed
        seed.main()
except Exception as _e:  # noqa: BLE001
    print("Aviso: no se pudo auto-cargar hospitales:", _e)


def _asegurar_hospitales_extra() -> None:
    """Agrega hospitales pedidos despues del seed inicial (idempotente).
    Crea el hospital y su capitan solo si no existen ya (por nombre)."""
    from sqlalchemy import select

    # clave 'Insumos2026' (mismo hash/salt que el resto de capitanes)
    CLAVE_HASH = "36361da5026c64b25825502d0b8f5ffeb8a1f90e149bbd34bee28c67b37596d2"
    CLAVE_SALT = "b3513f2515a5749d730de68351664345"
    extras = [
        {"nombre": "Hospital Periférico de Catia", "tipo": "publico",
         "sector": "Catia", "municipio": "Libertador", "ciudad": "Caracas",
         "usuario": "capitan_11"},
    ]
    with db.engine.begin() as con:
        for h in extras:
            existe = con.execute(
                select(db.hospitals.c.id).where(db.hospitals.c.nombre == h["nombre"])
            ).first()
            if existe:
                continue
            hid = con.execute(db.hospitals.insert().values(
                nombre=h["nombre"], tipo=h["tipo"], sector=h["sector"],
                municipio=h["municipio"], ciudad=h["ciudad"],
                semaforo_insumos="estable", recibiendo_pacientes="si",
                capacidad="con_capacidad", heridos_activos="N/D",
                es_estimado_heridos=False, fallecidos="N/D",
                en_terapia_intensiva="N/D", ultima_actualizacion="",
            )).inserted_primary_key[0]
            con.execute(db.captains.insert().values(
                hospital_id=hid, usuario=h["usuario"],
                clave_hash=CLAVE_HASH, clave_salt=CLAVE_SALT,
            ))
            print(f"Hospital agregado: {h['nombre']} (capitan {h['usuario']})")


try:
    _asegurar_hospitales_extra()
except Exception as _e:  # noqa: BLE001
    print("Aviso: no se pudo agregar hospitales extra:", _e)


def _ctx(request: Request, **extra) -> dict:
    """Contexto base: incluye el capitan logueado (o None) para el nav."""
    extra["capitan"] = auth.capitan_actual(request)
    return extra


# ===================== PUBLICO =====================

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request, municipio: str = "", semaforo: str = ""):
    hosp = db.listar_hospitales(municipio=municipio, semaforo=semaforo)
    return templates.TemplateResponse(request, "index.html", _ctx(
        request, hospitales=hosp, resumen=db.resumen(), municipios=db.municipios(),
        f_municipio=municipio, f_semaforo=semaforo,
    ))


@app.get("/hospital/{hospital_id}", response_class=HTMLResponse)
def hospital(request: Request, hospital_id: int):
    h = db.obtener_hospital(hospital_id)
    if not h:
        return RedirectResponse("/", status_code=303)
    reqs = db.listar_requests(hospital_id=hospital_id)
    return templates.TemplateResponse(request, "hospital.html",
                                      _ctx(request, h=h, requests=reqs))


@app.get("/necesidades", response_class=HTMLResponse)
def necesidades(request: Request, municipio: str = "", tipo: str = "",
                prioridad: str = "", estado: str = ""):
    reqs = db.listar_requests(municipio=municipio, tipo=tipo,
                              prioridad=prioridad, estado=estado)
    return templates.TemplateResponse(request, "necesidades.html", _ctx(
        request, requests=reqs, municipios=db.municipios(),
        f_municipio=municipio, f_tipo=tipo, f_prioridad=prioridad, f_estado=estado,
    ))


@app.get("/necesidad/{request_id}", response_class=HTMLResponse)
def necesidad(request: Request, request_id: int, ok: int = 0):
    r = db.obtener_request(request_id)
    if not r:
        return RedirectResponse("/necesidades", status_code=303)
    comp = db.listar_commitments(request_id)
    return templates.TemplateResponse(request, "necesidad.html",
                                      _ctx(request, r=r, compromisos=comp, ok=ok))


@app.post("/necesidad/{request_id}/ayudar")
def ayudar(request: Request, request_id: int,
           nombre_donante: str = Form(""), que_envia: str = Form(""),
           cantidad: str = Form(""), hora_estimada: str = Form(""),
           comentario: str = Form("")):
    if db.obtener_request(request_id):
        db.crear_commitment(request_id, nombre_donante, que_envia, cantidad,
                            hora_estimada, comentario)
    return RedirectResponse(f"/necesidad/{request_id}?ok=1", status_code=303)


@app.get("/personas", response_class=HTMLResponse)
def personas(request: Request, q: str = "", municipio: str = ""):
    pac = db.listar_patients(q=q, municipio=municipio)
    return templates.TemplateResponse(request, "personas.html", _ctx(
        request, personas=pac, municipios=db.municipios(),
        f_q=q, f_municipio=municipio,
    ))


@app.get("/persona/{patient_id}", response_class=HTMLResponse)
def persona(request: Request, patient_id: int):
    p = db.obtener_patient(patient_id)
    if not p:
        return RedirectResponse("/personas", status_code=303)
    return templates.TemplateResponse(request, "persona.html", _ctx(request, p=p))


# ===================== IMPORTAR LISTA (CSV) — solo capitanes =====================

_ALIAS = {
    "nombre": ["nombre", "nombres", "nombre completo"],
    "apellido": ["apellido", "apellidos"],
    "cedula": ["cedula", "ci", "cedula de identidad", "identidad", "c i"],
    "tipo_sangre": ["tipo de sangre", "tipo sangre", "sangre", "tiposangre"],
    "edad": ["edad", "edad aprox", "edad aproximada"],
    "sexo": ["sexo", "genero"],
    "estado": ["estado", "condicion"],
    "observaciones": ["observaciones", "notas", "obs", "comentario", "comentarios"],
    "seccion": ["seccion", "area", "sala"],
    "hospital": ["hospital", "centro", "hospital centro", "centro de salud",
                 "hospital/centro", "hospital o centro"],
}
MAX_FILAS_IMPORT = 50000


def _val(nrow: dict, claves: list[str]) -> str:
    for k in claves:
        if nrow.get(k):
            return str(nrow[k]).strip()
    return ""


@app.get("/importar", response_class=HTMLResponse)
def importar_form(request: Request, ok: str = "", n: int = 0, h: int = 0):
    if not auth.capitan_actual(request):
        return RedirectResponse("/entrar", status_code=303)
    return templates.TemplateResponse(request, "importar.html",
                                      _ctx(request, hospitales=db.listar_hospitales(),
                                           ok=ok, n=n, h=h))


@app.post("/importar")
async def importar(request: Request, hospital_id: str = Form(""),
                   archivo: UploadFile = File(...)):
    if not auth.capitan_actual(request):
        return RedirectResponse("/entrar", status_code=303)
    datos = await archivo.read()
    try:
        texto = datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = datos.decode("latin-1", errors="replace")
    try:
        filas = list(csv.DictReader(io.StringIO(texto)))
    except Exception:  # noqa: BLE001
        return RedirectResponse("/importar?ok=errcsv", status_code=303)

    # hospital por defecto (opcional): para filas sin columna 'hospital'
    default_hid = None
    if hospital_id.strip().isdigit() and db.obtener_hospital(int(hospital_id)):
        default_hid = int(hospital_id)

    cache = db.mapa_hospitales()   # nombre_normalizado -> id
    creados = {"n": 0}

    def resolver(nombre_hosp: str) -> int:
        nombre_hosp = (nombre_hosp or "").strip()
        if nombre_hosp:
            norm = db.normalizar(nombre_hosp)
            if norm in cache:
                return cache[norm]
            hid = db.crear_hospital(nombre_hosp)        # crea el que falte
            cache[norm] = hid
            creados["n"] += 1
            return hid
        if default_hid is not None:
            return default_hid
        # ultimo recurso: bolsa "Lista general"
        norm = db.normalizar("Lista general")
        if norm not in cache:
            cache[norm] = db.crear_hospital("Lista general")
            creados["n"] += 1
        return cache[norm]

    personas = []
    for row in filas[:MAX_FILAS_IMPORT]:
        nrow = {db.normalizar(k or ""): v for k, v in row.items()}
        nombre = _val(nrow, _ALIAS["nombre"])
        cedula = _val(nrow, _ALIAS["cedula"])
        if not nombre and not cedula:
            continue
        obs = _val(nrow, _ALIAS["observaciones"])
        seccion = _val(nrow, _ALIAS["seccion"])
        if seccion:
            obs = (seccion + " · " + obs).strip(" ·")
        personas.append({
            "hospital_id": resolver(_val(nrow, _ALIAS["hospital"])),
            "nombre": nombre, "apellido": _val(nrow, _ALIAS["apellido"]),
            "cedula": cedula, "tipo_sangre": _val(nrow, _ALIAS["tipo_sangre"]),
            "edad": _val(nrow, _ALIAS["edad"]), "sexo": _val(nrow, _ALIAS["sexo"]),
            "estado": _val(nrow, _ALIAS["estado"]), "observaciones": obs,
        })
    n = db.crear_patients_bulk(personas)
    return RedirectResponse(f"/importar?ok=ok&n={n}&h={creados['n']}", status_code=303)


# ===================== CAPITAN: login =====================

@app.get("/entrar", response_class=HTMLResponse)
def entrar_form(request: Request, error: int = 0):
    if auth.capitan_actual(request):
        return RedirectResponse("/panel", status_code=303)
    return templates.TemplateResponse(request, "entrar.html", _ctx(request, error=error))


@app.post("/entrar")
def entrar(request: Request, usuario: str = Form(...), clave: str = Form(...)):
    datos = auth.autenticar(usuario, clave)
    if not datos:
        return RedirectResponse("/entrar?error=1", status_code=303)
    request.session["captain_id"] = datos["captain_id"]
    request.session["hospital_id"] = datos["hospital_id"]
    request.session["usuario"] = datos["usuario"]
    return RedirectResponse("/panel", status_code=303)


@app.get("/salir")
def salir(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ===================== CAPITAN: panel =====================

@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, ok: str = "", n: int = 0):
    cap = auth.capitan_actual(request)
    if not cap:
        return RedirectResponse("/entrar", status_code=303)
    h = db.obtener_hospital(cap["hospital_id"])
    reqs = db.listar_requests(hospital_id=cap["hospital_id"])
    # compromisos por cada request (para que el capitan los vea)
    comp = {r["id"]: db.listar_commitments(r["id"]) for r in reqs}
    pac = db.listar_patients(hospital_id=cap["hospital_id"])
    return templates.TemplateResponse(request, "panel.html",
                                      _ctx(request, h=h, requests=reqs,
                                           compromisos=comp, personas=pac, ok=ok, n=n))


@app.post("/panel/estado")
def panel_estado(request: Request,
                 semaforo_insumos: str = Form(...), recibiendo_pacientes: str = Form(...),
                 capacidad: str = Form(...), heridos_activos: str = Form("N/D"),
                 es_estimado_heridos: str = Form(""), fallecidos: str = Form("N/D"),
                 en_terapia_intensiva: str = Form("N/D")):
    cap = auth.capitan_actual(request)
    if not cap:
        return RedirectResponse("/entrar", status_code=303)
    db.actualizar_estado_hospital(cap["hospital_id"], {
        "semaforo_insumos": semaforo_insumos,
        "recibiendo_pacientes": recibiendo_pacientes,
        "capacidad": capacidad,
        "heridos_activos": heridos_activos.strip() or "N/D",
        "es_estimado_heridos": bool(es_estimado_heridos),
        "fallecidos": fallecidos.strip() or "N/D",
        "en_terapia_intensiva": en_terapia_intensiva.strip() or "N/D",
    })
    return RedirectResponse("/panel?ok=estado", status_code=303)


@app.post("/panel/request/nuevo")
def panel_request_nuevo(request: Request, tipo_insumo: str = Form(...),
                        descripcion: str = Form(""), cantidad: str = Form(""),
                        prioridad: str = Form("media")):
    cap = auth.capitan_actual(request)
    if not cap:
        return RedirectResponse("/entrar", status_code=303)
    db.crear_request(cap["hospital_id"], tipo_insumo.strip(), descripcion.strip(),
                     cantidad.strip(), prioridad)
    return RedirectResponse("/panel?ok=request", status_code=303)


@app.post("/panel/persona/nuevo")
def panel_persona_nuevo(request: Request, nombre: str = Form(""),
                        apellido: str = Form(""), cedula: str = Form(""),
                        tipo_sangre: str = Form(""), edad: str = Form(""),
                        sexo: str = Form(""), estado: str = Form(""),
                        observaciones: str = Form("")):
    cap = auth.capitan_actual(request)
    if not cap:
        return RedirectResponse("/entrar", status_code=303)
    db.crear_patient(cap["hospital_id"], nombre.strip(), apellido.strip(),
                     cedula.strip(), tipo_sangre.strip(), edad.strip(),
                     sexo.strip(), estado.strip(), observaciones.strip())
    return RedirectResponse("/panel?ok=persona", status_code=303)


@app.post("/panel/request/{request_id}/estado")
def panel_request_estado(request: Request, request_id: int, estado: str = Form(...)):
    cap = auth.capitan_actual(request)
    if not cap:
        return RedirectResponse("/entrar", status_code=303)
    r = db.obtener_request(request_id)
    # solo el capitan dueno del hospital puede cambiar su request
    if r and r["hospital_id"] == cap["hospital_id"] and estado in db.ESTADOS:
        db.cambiar_estado_request(request_id, estado)
    return RedirectResponse("/panel?ok=estado_req", status_code=303)


@app.post("/panel/request/{request_id}/borrar")
def panel_request_borrar(request: Request, request_id: int):
    cap = auth.capitan_actual(request)
    if not cap:
        return RedirectResponse("/entrar", status_code=303)
    r = db.obtener_request(request_id)
    if r and r["hospital_id"] == cap["hospital_id"]:
        db.borrar_request(request_id)
    return RedirectResponse("/panel?ok=del_req", status_code=303)


@app.post("/panel/persona/{patient_id}/borrar")
def panel_persona_borrar(request: Request, patient_id: int):
    cap = auth.capitan_actual(request)
    if not cap:
        return RedirectResponse("/entrar", status_code=303)
    p = db.obtener_patient(patient_id)
    if p and p["hospital_id"] == cap["hospital_id"]:
        db.borrar_patient(patient_id)
    return RedirectResponse("/panel?ok=del_persona", status_code=303)
