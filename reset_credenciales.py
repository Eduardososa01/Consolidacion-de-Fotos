"""
Reinicia las contraseñas de TODOS los capitanes y las imprime en una tabla.
Funciona contra la base que indique DATABASE_URL (Supabase en produccion).

Uso (en tu PowerShell, dentro de la carpeta del proyecto):
    $env:DATABASE_URL = "postgresql://...tu cadena de Supabase con tu password..."
    py reset_credenciales.py
"""

from __future__ import annotations

import secrets

from sqlalchemy import select

import auth
import db

def main() -> None:
    db.crear_tablas()
    filas = []
    with db.engine.begin() as con:
        rows = con.execute(
            select(db.captains.c.id, db.captains.c.usuario, db.hospitals.c.nombre)
            .select_from(db.captains.join(db.hospitals,
                                          db.hospitals.c.id == db.captains.c.hospital_id))
            .order_by(db.captains.c.id)
        ).all()
        for cid, usuario, hosp in rows:
            clave = secrets.token_urlsafe(8)
            chash, csalt = auth.hash_clave(clave)
            con.execute(db.captains.update().where(db.captains.c.id == cid)
                        .values(clave_hash=chash, clave_salt=csalt))
            filas.append((hosp, usuario, clave))

    if not filas:
        print("No hay capitanes. Corre primero la app o seed.py.")
        return
    print("\n=== CONTRASEÑAS DE CAPITAN (guardalas) ===\n")
    print(f"{'HOSPITAL':45} {'USUARIO':24} CONTRASEÑA")
    print("-" * 88)
    for hosp, usuario, clave in filas:
        print(f"{hosp[:44]:45} {usuario:24} {clave}")
    print()


if __name__ == "__main__":
    main()
