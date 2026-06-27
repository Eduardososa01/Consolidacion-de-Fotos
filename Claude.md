# Project Context
Eres un agente encargado de identificar personas a partir de imágenes y cruzar esa información con un sitio web.

# Flujo de trabajo
Analiza las imágenes que contienen listas de personas.
Extrae el nombre completo de cada persona que aparezca en las imágenes.
Guarda todos los nombres en una base de datos o en un archivo CSV (puedes elegir el formato que prefieras).
Accede al sitio web que te proporcionaré.
# link: https://desaparecidosterremotovenezuela.com/


# Rules
Busca cada uno de los nombres extraídos dentro del sitio web.
Al finalizar, genera un reporte con el siguiente resumen:
 - Total de personas identificadas en las imágenes.
 - Personas encontradas en el sitio web.
 - Personas que no fueron encontradas en el sitio web.
 - Si aplica, incluye cualquier coincidencia parcial o ambigua para revisión manual.

---

# Plataforma de Coordinación de Ayuda Humanitaria (objetivo actual)

Coordina ayuda en hospitales durante una emergencia. Dos roles:
- **Capitanes** (1 cuenta por hospital): actualizan el estado del hospital
  (semáforo de insumos, capacidad, recibe pacientes, cifras de heridos/fallecidos/UCI)
  y publican **necesidades** (requests de insumos: sangre, antibióticos, etc.).
- **Público/donantes** (sin cuenta): ven hospitales y necesidades en vivo, filtran,
  y se **comprometen** a enviar insumos. El capitán confirma la recepción.
  Estados de cada necesidad: pendiente → en camino → recibido → completado.

## Cómo correrla
```powershell
cd "c:\Users\Eduardo\OneDrive\Desktop\Consolidacion de fotos"
py -m pip install -r requirements.txt
py seed.py                          # crea 10 hospitales + capitanes (anota credenciales)
py -m uvicorn app:app --reload
# abrir http://127.0.0.1:8000
```

## Archivos
- `app.py` — servidor web (FastAPI) + sesiones; rutas públicas y de capitán.
- `db.py` — esquema SQLAlchemy (hospitals, captains, requests, commitments) + consultas.
- `auth.py` — login de capitanes (hash pbkdf2 + sesión por cookie).
- `seed.py` — carga inicial de los 10 hospitales y sus capitanes.
- `config.py` — `DATABASE_URL` (SQLite local / Postgres prod) y `SECRET_KEY`.
- `templates/` — HTML (Tailwind CDN): base, index, hospital, necesidades, necesidad,
  entrar, panel.
- `render.yaml`, `Procfile`, `DESPLIEGUE.md` — despliegue (Render + Supabase).
- `requirements.txt` — dependencias.

## Notas técnicas
- Auth: capitanes con usuario+contraseña (pbkdf2 stdlib), sesión con SessionMiddleware.
  Donantes anónimos (solo dejan nombre + comentario al comprometerse).
- Almacenamiento: SQLite en local, Postgres (Supabase) en producción — mismo código.
- Jinja2 se inicializa con `cache_size=0` por un bug de cache en Python 3.14.
- Alcance v1: núcleo de coordinación. *Fuera de v1:* registro de pacientes
  individuales con foto (los datos de pacientes serían internos).

## Privacidad (antes de desplegar)
Datos sensibles de una emergencia. Para un prototipo está bien; antes de difundir
ampliamente conviene revisar quién puede comprometerse/abusar y proteger los datos.

## Historial del proyecto
1. (Sesión previa) Extracción de listas de hospitales con visión de Claude + cruce
   contra https://desaparecidosterremotovenezuela.com/ (su API pide token reCAPTCHA).
2. Plataforma "Reconexión" (encontrados → familias) — pivote intermedio.
3. **Actual:** coordinación de ayuda humanitaria (capitanes + necesidades + donaciones).
Los archivos de la fase 1-2 (extraer.py, extraccion.py, fotos/, CSV) se retiraron del
flujo activo.
