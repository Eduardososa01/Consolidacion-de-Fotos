"""
Autenticacion de capitanes: hash de contrasena (stdlib) y sesion por cookie.
"""

from __future__ import annotations

import hashlib
import secrets

from sqlalchemy import select

import db

_ITERACIONES = 200_000


def hash_clave(clave: str, salt: str | None = None) -> tuple[str, str]:
    """Devuelve (hash_hex, salt_hex). Si no se pasa salt, se genera uno nuevo."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"),
                             bytes.fromhex(salt), _ITERACIONES)
    return dk.hex(), salt


def verificar_clave(clave: str, hash_hex: str, salt: str) -> bool:
    calc, _ = hash_clave(clave, salt)
    return secrets.compare_digest(calc, hash_hex)


def autenticar(usuario: str, clave: str) -> dict | None:
    """Si las credenciales son correctas, devuelve {captain_id, hospital_id, usuario}."""
    with db.engine.connect() as con:
        r = con.execute(
            select(db.captains).where(db.captains.c.usuario == usuario.strip())
        ).first()
    if not r:
        return None
    fila = dict(r._mapping)
    if not verificar_clave(clave, fila["clave_hash"], fila["clave_salt"]):
        return None
    return {"captain_id": fila["id"], "hospital_id": fila["hospital_id"],
            "usuario": fila["usuario"]}


def capitan_actual(request) -> dict | None:
    """Lee la sesion y devuelve los datos del capitan logueado, o None."""
    cid = request.session.get("captain_id")
    hid = request.session.get("hospital_id")
    if cid is None or hid is None:
        return None
    return {"captain_id": cid, "hospital_id": hid,
            "usuario": request.session.get("usuario", "")}
