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

import re
import unicodedata
from datetime import datetime, timezone

# Si un hospital no se actualiza en mas de estas horas, se marca como "viejo".
UMBRAL_HORAS_VIEJO = 6

from sqlalchemy import (
    Boolean, Integer, MetaData, String, Table, Column, ForeignKey,
    create_engine, func, inspect, select, text,
)

import config


def normalizar(texto: str) -> str:
    """Quita acentos, mayusculas y espacios extra para comparar nombres."""
    sin = "".join(c for c in unicodedata.normalize("NFD", texto or "")
                  if unicodedata.category(c) != "Mn")
    return " ".join(sin.lower().split())


def parse_num(texto: str) -> int | None:
    """Saca el primer numero entero de un texto libre ('20 unidades' -> 20)."""
    if not texto:
        return None
    m = re.search(r"\d+", texto.replace(".", "").replace(",", ""))
    return int(m.group()) if m else None


def tiempo_relativo(iso: str | None) -> dict | None:
    """Convierte una fecha ISO en {relativo:'hace 2 h', exacto:'27/06/2026 16:19 UTC', horas:2.1}."""
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    seg = (datetime.now(timezone.utc) - t).total_seconds()
    seg = max(seg, 0)
    horas = seg / 3600
    if seg < 60:
        rel = "hace un momento"
    elif seg < 3600:
        rel = f"hace {int(seg // 60)} min"
    elif seg < 86400:
        h = int(horas)
        rel = f"hace {h} h" if h != 1 else "hace 1 h"
    else:
        d = int(seg // 86400)
        rel = f"hace {d} días" if d != 1 else "hace 1 día"
    return {"relativo": rel, "exacto": t.strftime("%d/%m/%Y %H:%M UTC"), "horas": horas}

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
metadata = MetaData()

# --- Valores posibles (para validar y para los formularios) ----------------
TIPOS_HOSPITAL = ["publico", "privado", "militar"]
SEMAFOROS = ["critico", "estable", "saturado"]
RECIBIENDO = ["si", "no", "con_restricciones"]
CAPACIDADES = ["desbordado", "al_limite", "con_capacidad"]
PRIORIDADES = ["alta", "media", "baja"]
ESTADOS = ["pendiente", "en_camino", "recibido", "completado"]
TIPOS_SANGRE = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]

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
    # Datos del paciente (opcionales; utiles para pedidos de sangre)
    Column("paciente_nombre", String(200), default=""),
    Column("paciente_apellido", String(200), default=""),
    Column("paciente_cedula", String(60), default=""),
    Column("paciente_tipo_sangre", String(10), default=""),
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

# Personas que el capitan registra al ver entrar a alguien al hospital.
patients = Table(
    "patients", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("hospital_id", Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
    Column("nombre", String(200), default=""),
    Column("apellido", String(200), default=""),
    Column("nombre_normalizado", String(400), default=""),
    Column("cedula", String(60), default=""),
    Column("tipo_sangre", String(10), default=""),
    Column("edad", String(40), default=""),
    Column("sexo", String(20), default=""),
    Column("estado", String(120), default=""),
    Column("observaciones", String(1000), default=""),
    Column("creado_en", String(40), nullable=False),
)


def crear_tablas() -> None:
    metadata.create_all(engine)
    _migrar_columnas_paciente()
    _crear_indices()


def _crear_indices() -> None:
    """Indices para que la busqueda de personas sea rapida con miles de registros."""
    idx = [
        "CREATE INDEX IF NOT EXISTS idx_pac_norm ON patients (nombre_normalizado)",
        "CREATE INDEX IF NOT EXISTS idx_pac_cedula ON patients (cedula)",
    ]
    try:
        with engine.begin() as con:
            for s in idx:
                con.execute(text(s))
    except Exception as e:  # noqa: BLE001
        print("Aviso: no se pudieron crear indices:", e)


def _migrar_columnas_paciente() -> None:
    """Anade las columnas de paciente a 'requests' si una base vieja no las tiene."""
    insp = inspect(engine)
    if "requests" not in insp.get_table_names():
        return
    existentes = {c["name"] for c in insp.get_columns("requests")}
    nuevas = {
        "paciente_nombre": "VARCHAR(200)",
        "paciente_apellido": "VARCHAR(200)",
        "paciente_cedula": "VARCHAR(60)",
        "paciente_tipo_sangre": "VARCHAR(10)",
    }
    with engine.begin() as con:
        for nombre, tipo in nuevas.items():
            if nombre not in existentes:
                con.execute(text(f"ALTER TABLE requests ADD COLUMN {nombre} {tipo} DEFAULT ''"))


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
    # ordenar para que lo CRITICO salte primero (solo cuenta si fue reportado)
    orden = {"critico": 0, "saturado": 1}

    def _clave(h: dict) -> tuple:
        rep = bool(h["ultima_actualizacion"])
        prio = orden.get(h["semaforo_insumos"], 2) if rep else 3
        return (prio, h["nombre"])

    filas.sort(key=_clave)
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
                  cantidad: str, prioridad: str, paciente_nombre: str = "",
                  paciente_apellido: str = "", paciente_cedula: str = "",
                  paciente_tipo_sangre: str = "") -> int:
    t = ahora()
    with engine.begin() as con:
        return con.execute(requests.insert().values(
            hospital_id=hospital_id, tipo_insumo=tipo_insumo, descripcion=descripcion,
            cantidad=cantidad, prioridad=prioridad, estado="pendiente",
            paciente_nombre=paciente_nombre, paciente_apellido=paciente_apellido,
            paciente_cedula=paciente_cedula, paciente_tipo_sangre=paciente_tipo_sangre,
            creado_en=t, actualizado_en=t,
        )).inserted_primary_key[0]


_REQ_COLS = [
    requests.c.id, requests.c.tipo_insumo, requests.c.descripcion,
    requests.c.cantidad, requests.c.prioridad, requests.c.estado,
    requests.c.paciente_nombre, requests.c.paciente_apellido,
    requests.c.paciente_cedula, requests.c.paciente_tipo_sangre,
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
    # conteo y suma de compromisos por request (para la barra de progreso)
    ids = [r["id"] for r in filas]
    counts = _commitments_por_request(ids)
    sumas = _comprometido_por_request(ids)
    for r in filas:
        r["n_compromisos"] = counts.get(r["id"], 0)
        r["objetivo"] = parse_num(r["cantidad"])
        r["comprometido"] = sumas.get(r["id"], 0)
    return filas


def obtener_request(request_id: int) -> dict | None:
    j = requests.join(hospitals, hospitals.c.id == requests.c.hospital_id)
    stmt = select(*_REQ_COLS, hospitals.c.telefono.label("hospital_telefono")) \
        .select_from(j).where(requests.c.id == request_id)
    with engine.connect() as con:
        r = con.execute(stmt).first()
        if not r:
            return None
        d = dict(r._mapping)
    d["objetivo"] = parse_num(d["cantidad"])
    d["comprometido"] = _comprometido_por_request([request_id]).get(request_id, 0)
    return d


def cambiar_estado_request(request_id: int, estado: str) -> None:
    with engine.begin() as con:
        con.execute(requests.update().where(requests.c.id == request_id)
                    .values(estado=estado, actualizado_en=ahora()))


def borrar_request(request_id: int) -> None:
    with engine.begin() as con:
        con.execute(commitments.delete().where(commitments.c.request_id == request_id))
        con.execute(requests.delete().where(requests.c.id == request_id))


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


def _comprometido_por_request(ids: list[int]) -> dict[int, int]:
    """Suma las cantidades numericas comprometidas por cada request (texto libre)."""
    if not ids:
        return {}
    stmt = (select(commitments.c.request_id, commitments.c.cantidad)
            .where(commitments.c.request_id.in_(ids)))
    sumas: dict[int, int] = {}
    with engine.connect() as con:
        for rid, cant in con.execute(stmt):
            n = parse_num(cant)
            if n:
                sumas[rid] = sumas.get(rid, 0) + n
    return sumas


# --- Personas (pacientes que el capitan registra) --------------------------

def crear_patient(hospital_id: int, nombre: str, apellido: str, cedula: str,
                  tipo_sangre: str, edad: str, sexo: str, estado: str,
                  observaciones: str) -> int:
    norm = normalizar(f"{nombre} {apellido}")
    with engine.begin() as con:
        return con.execute(patients.insert().values(
            hospital_id=hospital_id, nombre=nombre, apellido=apellido,
            nombre_normalizado=norm, cedula=cedula, tipo_sangre=tipo_sangre,
            edad=edad, sexo=sexo, estado=estado, observaciones=observaciones,
            creado_en=ahora(),
        )).inserted_primary_key[0]


def crear_patients_bulk(hospital_id: int, personas: list[dict]) -> int:
    """Inserta MUCHAS personas de una vez (rapido para miles). Cada dict acepta
    nombre, apellido, cedula, tipo_sangre, edad, sexo, estado, observaciones."""
    if not personas:
        return 0
    t = ahora()
    filas = []
    for p in personas:
        nombre = (p.get("nombre") or "").strip()
        apellido = (p.get("apellido") or "").strip()
        filas.append({
            "hospital_id": hospital_id, "nombre": nombre, "apellido": apellido,
            "nombre_normalizado": normalizar(f"{nombre} {apellido}"),
            "cedula": (p.get("cedula") or "").strip(),
            "tipo_sangre": (p.get("tipo_sangre") or "").strip(),
            "edad": (p.get("edad") or "").strip(),
            "sexo": (p.get("sexo") or "").strip(),
            "estado": (p.get("estado") or "").strip(),
            "observaciones": (p.get("observaciones") or "").strip(),
            "creado_en": t,
        })
    # insertar en lotes (evita el limite de parametros de Postgres)
    with engine.begin() as con:
        for i in range(0, len(filas), 500):
            con.execute(patients.insert(), filas[i:i + 500])
    return len(filas)


_PAC_COLS = [
    patients.c.id, patients.c.nombre, patients.c.apellido, patients.c.cedula,
    patients.c.tipo_sangre, patients.c.edad, patients.c.sexo, patients.c.estado,
    patients.c.observaciones, patients.c.creado_en, patients.c.hospital_id,
    hospitals.c.nombre.label("hospital_nombre"), hospitals.c.municipio,
    hospitals.c.ciudad,
]


def listar_patients(q: str = "", hospital_id: int | None = None,
                    municipio: str = "", limite: int = 300) -> list[dict]:
    j = patients.join(hospitals, hospitals.c.id == patients.c.hospital_id)
    stmt = select(*_PAC_COLS).select_from(j)
    q = q.strip()
    if q:
        solo = q.replace(".", "").replace("-", "").replace(" ", "")
        if solo.isdigit():   # parece cedula
            limpia = func.replace(func.replace(patients.c.cedula, ".", ""), "-", "")
            stmt = stmt.where(limpia.like(f"%{solo}%"))
        else:
            stmt = stmt.where(patients.c.nombre_normalizado.like(f"%{normalizar(q)}%"))
    if hospital_id is not None:
        stmt = stmt.where(patients.c.hospital_id == hospital_id)
    if municipio.strip():
        stmt = stmt.where(hospitals.c.municipio.ilike(f"%{municipio.strip()}%"))
    stmt = stmt.order_by(patients.c.creado_en.desc()).limit(limite)
    with engine.connect() as con:
        return [dict(r._mapping) for r in con.execute(stmt)]


def obtener_patient(patient_id: int) -> dict | None:
    j = patients.join(hospitals, hospitals.c.id == patients.c.hospital_id)
    stmt = select(*_PAC_COLS, hospitals.c.telefono.label("hospital_telefono")) \
        .select_from(j).where(patients.c.id == patient_id)
    with engine.connect() as con:
        r = con.execute(stmt).first()
        return dict(r._mapping) if r else None


def borrar_patient(patient_id: int) -> None:
    with engine.begin() as con:
        con.execute(patients.delete().where(patients.c.id == patient_id))


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
        n_pac = con.execute(select(func.count()).select_from(patients)).scalar() or 0
    return {"hospitales": n_hosp, "necesidades_activas": n_act,
            "hospitales_criticos": n_crit, "personas": n_pac}
