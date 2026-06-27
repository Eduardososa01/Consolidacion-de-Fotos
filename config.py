"""
Configuracion central de la plataforma.

- En tu PC (desarrollo): si no defines DATABASE_URL, usa SQLite local.
- En produccion (Render): define DATABASE_URL con la cadena de Supabase/Postgres.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE = Path(__file__).parent

# --- Base de datos ---------------------------------------------------------
# Por defecto SQLite local; en produccion se define DATABASE_URL (Postgres).
_default_sqlite = f"sqlite:///{(BASE / 'base_datos.sqlite').as_posix()}"
DATABASE_URL = os.environ.get("DATABASE_URL", _default_sqlite)

# Render/Supabase a veces entregan la URL como "postgres://"; SQLAlchemy
# necesita "postgresql+psycopg://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

ES_SQLITE = DATABASE_URL.startswith("sqlite")

# --- Sesiones (login de capitanes) -----------------------------------------
# Clave para firmar las cookies de sesion. En produccion se define SECRET_KEY;
# en local hay un valor por defecto (no usar el default en produccion).
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-cambia-esto-en-produccion")

# --- API de vision (leer fotos de listas) ----------------------------------
# Necesaria para el feature de "subir foto de lista" en el panel del capitan.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
