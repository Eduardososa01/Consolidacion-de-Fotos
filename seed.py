"""
Carga inicial: crea los 10 hospitales y una cuenta de capitan por hospital.

Idempotente: si un hospital ya existe (por nombre), no lo duplica. Para los
capitanes, crea el que falte. Imprime las credenciales generadas.

Uso:
    py seed.py
"""

from __future__ import annotations

import secrets
import unicodedata

from sqlalchemy import select

import auth
import db

# 10 hospitales importantes (datos base; el capitan los puede ajustar luego).
HOSPITALES = [
    {"nombre": "Hospital J. M. de los Ríos", "tipo": "publico", "municipio": "Libertador", "sector": "San Bernardino", "ciudad": "Caracas"},
    {"nombre": "Hospital Universitario de Caracas", "tipo": "publico", "municipio": "Libertador", "sector": "Ciudad Universitaria", "ciudad": "Caracas"},
    {"nombre": "Hospital Vargas de Caracas", "tipo": "publico", "municipio": "Libertador", "sector": "San José", "ciudad": "Caracas"},
    {"nombre": "Hospital Dr. Miguel Pérez Carreño", "tipo": "publico", "municipio": "Libertador", "sector": "La Yaguara", "ciudad": "Caracas"},
    {"nombre": "Hospital Domingo Luciani (El Llanito)", "tipo": "publico", "municipio": "Sucre", "sector": "El Llanito", "ciudad": "Caracas"},
    {"nombre": "Hospital Pérez de León II", "tipo": "publico", "municipio": "Sucre", "sector": "Petare", "ciudad": "Caracas"},
    {"nombre": "Hospital Militar Dr. Carlos Arvelo", "tipo": "militar", "municipio": "Libertador", "sector": "San Martín", "ciudad": "Caracas"},
    {"nombre": "Hospital General del Oeste (Los Magallanes)", "tipo": "publico", "municipio": "Libertador", "sector": "Catia", "ciudad": "Caracas"},
    {"nombre": "Hospital Dr. José María Vargas (La Guaira)", "tipo": "publico", "municipio": "Vargas", "sector": "Macuto", "ciudad": "La Guaira"},
    {"nombre": "Maternidad Concepción Palacios", "tipo": "publico", "municipio": "Libertador", "sector": "San Martín", "ciudad": "Caracas"},
]


def _usuario_desde(nombre: str, n: int) -> str:
    base = "".join(c for c in unicodedata.normalize("NFD", nombre)
                   if unicodedata.category(c) != "Mn").lower()
    palabra = "".join(ch for ch in base if ch.isalnum() or ch == " ").split()
    corto = palabra[1] if len(palabra) > 1 else palabra[0]
    return f"capitan_{corto}{n}"


def main() -> None:
    db.crear_tablas()
    credenciales = []

    with db.engine.begin() as con:
        existentes = {r[0] for r in con.execute(select(db.hospitals.c.nombre))}

        for i, h in enumerate(HOSPITALES, 1):
            if h["nombre"] in existentes:
                hid = con.execute(
                    select(db.hospitals.c.id).where(db.hospitals.c.nombre == h["nombre"])
                ).scalar()
            else:
                hid = con.execute(db.hospitals.insert().values(
                    nombre=h["nombre"], tipo=h["tipo"], municipio=h["municipio"],
                    sector=h["sector"], ciudad=h["ciudad"],
                    semaforo_insumos="estable", recibiendo_pacientes="si",
                    capacidad="con_capacidad", heridos_activos="N/D",
                    es_estimado_heridos=False, fallecidos="N/D",
                    en_terapia_intensiva="N/D", ultima_actualizacion="",
                )).inserted_primary_key[0]

            # capitan para este hospital (si no tiene)
            ya = con.execute(
                select(db.captains.c.id).where(db.captains.c.hospital_id == hid)
            ).first()
            if ya:
                continue
            usuario = _usuario_desde(h["nombre"], i)
            clave = secrets.token_urlsafe(8)
            chash, csalt = auth.hash_clave(clave)
            con.execute(db.captains.insert().values(
                hospital_id=hid, usuario=usuario, clave_hash=chash, clave_salt=csalt,
            ))
            credenciales.append((h["nombre"], usuario, clave))

    print("\n=== Hospitales y capitanes listos ===")
    if credenciales:
        print("\nCredenciales de capitanes (GUARDA ESTO, no se vuelve a mostrar):\n")
        print(f"{'HOSPITAL':45} {'USUARIO':28} CONTRASEÑA")
        print("-" * 90)
        for nombre, usuario, clave in credenciales:
            print(f"{nombre[:44]:45} {usuario:28} {clave}")
    else:
        print("Los capitanes ya existían; no se generaron credenciales nuevas.")
    print()


if __name__ == "__main__":
    main()
