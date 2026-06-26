"""
Base de datos de la plataforma (SQLAlchemy Core).

Funciona igual con SQLite (tu PC) y Postgres (produccion en la nube).

Tablas:
  - registros: cada foto subida (una "lista" de hospital, o una "persona").
                La imagen se guarda AQUI mismo (columna binaria 'foto'), reducida.
  - personas:  cada persona; una lista tiene muchas, una persona tiene una.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from sqlalchemy import (
    LargeBinary, Integer, MetaData, String, Table, Column, ForeignKey,
    create_engine, func, select, text,
)

import config
from extraccion import Pizarra, normalizar

try:
    from PIL import Image
    _HAY_PIL = True
except Exception:  # noqa: BLE001
    _HAY_PIL = False

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
metadata = MetaData()

registros = Table(
    "registros", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tipo", String(20), nullable=False),          # 'lista' | 'persona'
    Column("foto", LargeBinary),                          # imagen (jpeg reducido)
    Column("foto_mime", String(40), default="image/jpeg"),
    Column("hospital", String(300), default=""),
    Column("ciudad", String(200), default=""),
    Column("fecha", String(100), default=""),
    Column("observaciones", String(2000), default=""),
    Column("fecha_subida", String(40), nullable=False),
)

personas = Table(
    "personas", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("registro_id", Integer, ForeignKey("registros.id", ondelete="CASCADE"), nullable=False),
    Column("nombre", String(300), default=""),
    Column("nombre_normalizado", String(300), default=""),
    Column("cedula", String(60), default=""),
    Column("estado", String(120), default=""),
    Column("notas", String(1000), default=""),
)


def crear_tablas() -> None:
    metadata.create_all(engine)


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def reducir_imagen(datos: bytes) -> tuple[bytes, str]:
    """Reduce la imagen a JPEG pequeno. Si no hay Pillow, guarda tal cual."""
    if not _HAY_PIL:
        return datos, "image/jpeg"
    try:
        img = Image.open(io.BytesIO(datos))
        img = img.convert("RGB")
        img.thumbnail((config.IMG_LADO_MAX, config.IMG_LADO_MAX))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=config.IMG_CALIDAD, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception:  # noqa: BLE001
        return datos, "image/jpeg"


def guardar_lista(datos_foto: bytes, pizarra: Pizarra, ciudad: str = "") -> tuple[int, int]:
    """Guarda un registro 'lista' (con su foto) y todas sus personas."""
    foto, mime = reducir_imagen(datos_foto)
    with engine.begin() as con:
        rid = con.execute(registros.insert().values(
            tipo="lista", foto=foto, foto_mime=mime,
            hospital=pizarra.hospital or "", ciudad=ciudad,
            fecha=pizarra.fecha or "", observaciones="", fecha_subida=_ahora(),
        )).inserted_primary_key[0]
        if pizarra.personas:
            con.execute(personas.insert(), [
                {"registro_id": rid, "nombre": p.nombre,
                 "nombre_normalizado": normalizar(p.nombre), "cedula": p.cedula,
                 "estado": p.estado, "notas": p.notas}
                for p in pizarra.personas
            ])
    return rid, len(pizarra.personas)


def guardar_persona(datos_foto: bytes, nombre: str = "", cedula: str = "",
                    hospital: str = "", ciudad: str = "", fecha: str = "",
                    observaciones: str = "") -> int:
    """Guarda un registro 'persona' (foto + una sola persona)."""
    foto, mime = reducir_imagen(datos_foto)
    with engine.begin() as con:
        rid = con.execute(registros.insert().values(
            tipo="persona", foto=foto, foto_mime=mime, hospital=hospital,
            ciudad=ciudad, fecha=fecha, observaciones=observaciones, fecha_subida=_ahora(),
        )).inserted_primary_key[0]
        con.execute(personas.insert().values(
            registro_id=rid, nombre=nombre, nombre_normalizado=normalizar(nombre),
            cedula=cedula, estado="", notas="",
        ))
    return rid


_COLS = [
    personas.c.id, personas.c.nombre, personas.c.cedula, personas.c.estado,
    personas.c.notas, registros.c.id.label("registro_id"), registros.c.tipo,
    registros.c.hospital, registros.c.ciudad, registros.c.fecha,
    registros.c.observaciones, registros.c.fecha_subida,
]


def buscar(q: str = "", hospital: str = "", ciudad: str = "", limite: int = 200) -> list[dict]:
    """Busca personas por nombre/cedula (q) y filtros. Vacio = ultimos registros."""
    j = personas.join(registros, registros.c.id == personas.c.registro_id)
    stmt = select(*_COLS).select_from(j)
    q = q.strip()
    if q:
        solo = q.replace(".", "").replace("-", "").replace(" ", "")
        if solo.isdigit():
            limpia = func.replace(func.replace(personas.c.cedula, ".", ""), "-", "")
            stmt = stmt.where(limpia.like(f"%{solo}%"))
        else:
            stmt = stmt.where(personas.c.nombre_normalizado.like(f"%{normalizar(q)}%"))
    if hospital.strip():
        stmt = stmt.where(registros.c.hospital.ilike(f"%{hospital.strip()}%"))
    if ciudad.strip():
        stmt = stmt.where(registros.c.ciudad.ilike(f"%{ciudad.strip()}%"))
    stmt = stmt.order_by(registros.c.fecha_subida.desc(), personas.c.id.desc()).limit(limite)
    with engine.connect() as con:
        return [dict(r._mapping) for r in con.execute(stmt)]


def obtener_persona(persona_id: int) -> dict | None:
    j = personas.join(registros, registros.c.id == personas.c.registro_id)
    stmt = select(*_COLS).select_from(j).where(personas.c.id == persona_id)
    with engine.connect() as con:
        r = con.execute(stmt).first()
        return dict(r._mapping) if r else None


def obtener_foto(registro_id: int) -> tuple[bytes, str] | None:
    stmt = select(registros.c.foto, registros.c.foto_mime).where(registros.c.id == registro_id)
    with engine.connect() as con:
        r = con.execute(stmt).first()
        if not r or r[0] is None:
            return None
        return bytes(r[0]), r[1] or "image/jpeg"


def contar() -> dict:
    with engine.connect() as con:
        p = con.execute(select(func.count()).select_from(personas)).scalar() or 0
        listas = con.execute(
            select(func.count()).select_from(registros).where(registros.c.tipo == "lista")
        ).scalar() or 0
    return {"personas": p, "listas": listas}
