---
title: Coordinación de Ayuda
emoji: 🏥
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Coordinación de Ayuda Humanitaria

Plataforma para coordinar ayuda en hospitales durante una emergencia.

- **Capitanes** (1 por hospital): actualizan el estado del hospital, publican
  necesidades (insumos) y registran personas que ingresan (a mano o subiendo la
  foto de una lista).
- **Público / donantes**: ven hospitales y necesidades en tiempo real, se
  comprometen a enviar insumos, y buscan personas por nombre o cédula.

## Variables de entorno (secrets)
- `DATABASE_URL` — Postgres (Supabase). Sin ella usa SQLite local (efímero).
- `SECRET_KEY` — clave para las sesiones de los capitanes.
- `ANTHROPIC_API_KEY` — para leer fotos de listas (opcional).

Tras el primer despliegue, correr `python seed.py` (apuntando `DATABASE_URL` a
la base real) para crear los 10 hospitales y sus capitanes.
