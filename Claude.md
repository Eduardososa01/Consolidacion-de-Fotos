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

# Plataforma "Reconexión" (objetivo actual)

Invertimos el modelo: en vez de que las familias reporten desaparecidos,
**cualquiera sube la foto de una lista de hospital** (se leen los nombres
automáticamente con la visión de Claude) o la foto de una persona encontrada, y
**las familias buscan** por nombre o cédula para ver si su familiar está.

## Cómo correrla
```powershell
cd "c:\Users\Eduardo\OneDrive\Desktop\Consolidacion de fotos"
$env:ANTHROPIC_API_KEY = "tu-clave"     # necesaria para leer listas
py -m pip install -r requirements.txt
py -m uvicorn app:app --reload
# abrir http://127.0.0.1:8000
```

## Archivos
- `app.py` — servidor web (FastAPI) con las rutas `/`, `/subir`, `/persona/{id}`.
- `extraccion.py` — lógica de visión reusable (modelos, `extraer_pizarra`, `normalizar`).
- `db.py` — base de datos SQLite (tablas `registros` y `personas`) + búsqueda.
- `templates/` — páginas HTML (Tailwind por CDN): `base`, `index`, `subir`, `persona`.
- `media/` — fotos subidas por la gente (se crea sola).
- `extraer.py` — CLI opcional para procesar en lote las fotos de `fotos/`.
- `base_datos.sqlite` — base de datos (se crea sola).
- `requirements.txt` — dependencias.

## Notas técnicas
- Modelo de visión: `claude-opus-4-8` con salida estructurada (`messages.parse`).
- Búsqueda por nombre (normalizado, sin acentos/mayúsculas) o por cédula.
- Almacenamiento: **SQLite + carpeta `media/` local** (decisión para el prototipo).
  Pendiente opcional: export/respaldo a Google Drive/Sheets para compartir
  (Sheets NO como motor de búsqueda: lento y con datos sensibles).
- Jinja2 se inicializa con `cache_size=0` por un bug de cache en Python 3.14.

## Privacidad (antes de desplegar)
Maneja datos sensibles de personas vulnerables. Para un prototipo local está bien;
antes de publicarlo hay que revisar consentimiento, moderación de subidas
(ahora la subida es abierta) y protección de datos.

## Trabajo previo (sesión anterior)
Antes exploramos el cruce contra https://desaparecidosterremotovenezuela.com/
(su API pide token reCAPTCHA → solo se consulta por el buscador del navegador).
Quedó el script de extracción y el CSV `lista_hospital_perez_carreno.csv`.
