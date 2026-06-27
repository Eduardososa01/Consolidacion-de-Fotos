"""
Base de datos de la plataforma de coordinacion de ayuda humanitaria
(SQLAlchemy Core). Funciona igual con SQLite (tu PC) y Postgres (produccion).

Tablas:
  - hospitals:    perfil + estado operativo + cifras (publico).
  - captains:     una cuenta por hospital (login).
  - requests:     insumos que necesita un hospital.
  - commitments:  compromisos de donantes sobre un request.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Integer, MetaData, String, Table, Column, ForeignKey,
    create_engine, func, select,
)

import config

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
metadata = MetaData()

# --- Valores posibles (para validar y para los formularios) ----------------
TIPOS_HOSPITAL = ["publico", "privado", "militar"]
SEMAFOROS = ["critico", "estable", "saturado"]
RECIBIENDO = ["si", "no", "con_restricciones"]
CAPACIDADES = ["desbordado", "al_limite", "con_capacidad"]
PRIORIDADES = ["alta", "media", "baja"]
ESTADOS = ["pendiente", "en_camino", "recibido", "completado"]

# Insumos sugeridos (el capitan puede escribir otro).
INSUMOS = [
    "Sangre O+", "Sangre O-", "Donantes de sangre", "Antibioticos", "Analgesicos",
    "Suero", "Gasas", "Material de curacion", "Oxigeno", "Ropa", "Agua",
    "Comida", "Transporte", "Otro",
]

# --- Etiquetas legibles ----------------------------------------------------
ETIQUETAS = {
    "critico": "Crítico", "estable": "Estable", "saturado": "Saturado",
    "si": "Sí", "no": "No", "con_restricciones": "Con restricciones",
    "desbordado": "Desbordado", "al_limite": "Al límite", "con_capacidad": "Con capacidad",
    "alta": "Alta", "media": "Media", "baja": "Baja",
    "pendiente": "Pendiente", "en_camino": "En camino",
    "recibido": "Recibido", "completado": "Completado",
    "publico": "Público", "privado": "Privado", "militar": "Militar",
}


hospitals = Table(
    "hospitals", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("nombre", String(300), nullable=False),
    Column("tipo", String(20), default="publico"),
    Column("sector", String(200), default=""),
    Column("municipio", String(200), default=""),
    Column("ciudad", String(200), default=""),
    Column("direccion", String(400), default=""),
    Column("telefono", String(60), default=""),
    # Estado operativo (dinamico)
    Column("semaforo_insumos", String(20), default="estable"),
    Column("recibiendo_pacientes", String(20), default="si"),
    Column("capacidad", String(20), default="con_capacidad"),
    # Cifras de pacientes (admiten "N/D")
    Column("heridos_activos", String(20), default="N/D"),
    Column("es_estimado_heridos", Boolean, default=False),
    Column("fallecidos", String(20), default="N/D"),
    Column("en_terapia_intensiva", String(20), default="N/D"),
    Column("ultima_actualizacion", String(40), default=""),
)

captains = Table(
    "captains", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("hospital_id", Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
    Column("usuario", String(80), nullable=False, unique=True),
    Column("clave_hash", String(255), nullable=False),
    Column("clave_salt", String(64), nullable=False),
)

requests = Table(
    "requests", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("hospital_id", Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
    Column("tipo_insumo", String(120), nullable=False),
    Column("descripcion", String(1000), default=""),
    Column("cantidad", String(120), default=""),
    Column("prioridad", String(20), default="media"),
    Column("estado", String(20), default="pendiente"),
    Column("creado_en", String(40), nullable=False),
    Column("actualizado_en", String(40), nullable=False),
)

commitments = Table(
    "commitments", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("request_id", Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False),
    Column("nombre_donante", String(200), default=""),
    Column("que_envia", String(400), default=""),
    Column("cantidad", String(120), default=""),
    Column("hora_estimada", String(120), default=""),
    Column("comentario", String(1000), default=""),
    Column("creado_en", String(40), nullable=False),
)


def crear_tablas() -> None:
    metadata.create_all(engine)


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="minutes")


# --- Hospitales ------------------------------------------------------------

def listar_hospitales(municipio: str = "", semaforo: str = "") -> list[dict]:
    stmt = select(hospitals)
    if municipio.strip():
        stmt = stmt.where(hospitals.c.municipio.ilike(f"%{municipio.strip()}%"))
    if semaforo.strip():
        stmt = stmt.where(hospitals.c.semaforo_insumos == semaforo.strip())
    stmt = stmt.order_by(hospitals.c.nombre)
    with engine.connect() as con:
        filas = [dict(r._mapping) for r in con.execute(stmt)]
    # adjuntar conteo de requests activos (no completados) por hospital
    activos = _requests_activos_por_hospital()
    for h in filas:
        h["requests_activos"] = activos.get(h["id"], 0)
    return filas


def obtener_hospital(hospital_id: int) -> dict | None:
    with engine.connect() as con:
        r = con.execute(select(hospitals).where(hospitals.c.id == hospital_id)).first()
        return dict(r._mapping) if r else None


def _requests_activos_por_hospital() -> dict[int, int]:
    stmt = (
        select(requests.c.hospital_id, func.count())
        .where(requests.c.estado != "completado")
        .group_by(requests.c.hospital_id)
    )
    with engine.connect() as con:
        return {row[0]: row[1] for row in con.execute(stmt)}


def actualizar_estado_hospital(hospital_id: int, datos: dict) -> None:
    campos = {k: datos[k] for k in (
        "semaforo_insumos", "recibiendo_pacientes", "capacidad",
        "heridos_activos", "es_estimado_heridos", "fallecidos",
        "en_terapia_intensiva",
    ) if k in datos}
    campos["ultima_actualizacion"] = ahora()
    with engine.begin() as con:
        con.execute(hospitals.update().where(hospitals.c.id == hospital_id).values(**campos))


def municipios() -> list[str]:
    with engine.connect() as con:
        rows = con.execute(
            select(hospitals.c.municipio).distinct().order_by(hospitals.c.municipio)
        ).all()
    return [r[0] for r in rows if r[0]]


# --- Requests (necesidades) ------------------------------------------------

def crear_request(hospital_id: int, tipo_insumo: str, descripcion: str,
                  cantidad: str, prioridad: str) -> int:
    t = ahora()
    with engine.begin() as con:
        return con.execute(requests.insert().values(
            hospital_id=hospital_id, tipo_insumo=tipo_insumo, descripcion=descripcion,
            cantidad=cantidad, prioridad=prioridad, estado="pendiente",
            creado_en=t, actualizado_en=t,
        )).inserted_primary_key[0]


_REQ_COLS = [
    requests.c.id, requests.c.tipo_insumo, requests.c.descripcion,
    requests.c.cantidad, requests.c.prioridad, requests.c.estado,
    requests.c.creado_en, requests.c.actualizado_en,
    requests.c.hospital_id, hospitals.c.nombre.label("hospital_nombre"),
    hospitals.c.municipio, hospitals.c.ciudad,
]
_ORDEN_PRIORIDAD = {"alta": 0, "media": 1, "baja": 2}


def listar_requests(hospital_id: int | None = None, municipio: str = "",
                    tipo: str = "", prioridad: str = "", estado: str = "",
                    solo_activos: bool = False) -> list[dict]:
    j = requests.join(hospitals, hospitals.c.id == requests.c.hospital_id)
    stmt = select(*_REQ_COLS).select_from(j)
    if hospital_id is not None:
        stmt = stmt.where(requests.c.hospital_id == hospital_id)
    if municipio.strip():
        stmt = stmt.where(hospitals.c.municipio.ilike(f"%{municipio.strip()}%"))
    if tipo.strip():
        stmt = stmt.where(requests.c.tipo_insumo.ilike(f"%{tipo.strip()}%"))
    if prioridad.strip():
        stmt = stmt.where(requests.c.prioridad == prioridad.strip())
    if estado.strip():
        stmt = stmt.where(requests.c.estado == estado.strip())
    if solo_activos:
        stmt = stmt.where(requests.c.estado != "completado")
    with engine.connect() as con:
        filas = [dict(r._mapping) for r in con.execute(stmt)]
    # ordenar por prioridad y fecha (mas reciente primero)
    filas.sort(key=lambda r: (_ORDEN_PRIORIDAD.get(r["prioridad"], 9),
                              r["creado_en"]), reverse=False)
    # conteo de compromisos por request
    counts = _commitments_por_request([r["id"] for r in filas])
    for r in filas:
        r["n_compromisos"] = counts.get(r["id"], 0)
    return filas


def obtener_request(request_id: int) -> dict | None:
    j = requests.join(hospitals, hospitals.c.id == requests.c.hospital_id)
    stmt = select(*_REQ_COLS, hospitals.c.telefono.label("hospital_telefono")) \
        .select_from(j).where(requests.c.id == request_id)
    with engine.connect() as con:
        r = con.execute(stmt).first()
        return dict(r._mapping) if r else None


def cambiar_estado_request(request_id: int, estado: str) -> None:
    with engine.begin() as con:
        con.execute(requests.update().where(requests.c.id == request_id)
                    .values(estado=estado, actualizado_en=ahora()))


# --- Commitments (compromisos de donantes) ---------------------------------

def crear_commitment(request_id: int, nombre_donante: str, que_envia: str,
                     cantidad: str, hora_estimada: str, comentario: str) -> int:
    with engine.begin() as con:
        cid = con.execute(commitments.insert().values(
            request_id=request_id, nombre_donante=nombre_donante, que_envia=que_envia,
            cantidad=cantidad, hora_estimada=hora_estimada, comentario=comentario,
            creado_en=ahora(),
        )).inserted_primary_key[0]
        # si el request estaba pendiente, pasa a "en camino"
        r = con.execute(select(requests.c.estado).where(requests.c.id == request_id)).first()
        if r and r[0] == "pendiente":
            con.execute(requests.update().where(requests.c.id == request_id)
                        .values(estado="en_camino", actualizado_en=ahora()))
    return cid


def listar_commitments(request_id: int) -> list[dict]:
    stmt = select(commitments).where(commitments.c.request_id == request_id) \
        .order_by(commitments.c.creado_en.desc())
    with engine.connect() as con:
        return [dict(r._mapping) for r in con.execute(stmt)]


def _commitments_por_request(ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    stmt = (select(commitments.c.request_id, func.count())
            .where(commitments.c.request_id.in_(ids))
            .group_by(commitments.c.request_id))
    with engine.connect() as con:
        return {row[0]: row[1] for row in con.execute(stmt)}


# --- Resumen para la home --------------------------------------------------

def resumen() -> dict:
    with engine.connect() as con:
        n_hosp = con.execute(select(func.count()).select_from(hospitals)).scalar() or 0
        n_act = con.execute(
            select(func.count()).select_from(requests).where(requests.c.estado != "completado")
        ).scalar() or 0
        n_crit = con.execute(
            select(func.count()).select_from(hospitals)
            .where(hospitals.c.semaforo_insumos == "critico")
        ).scalar() or 0
    return {"hospitales": n_hosp, "necesidades_activas": n_act, "hospitales_criticos": n_crit}
