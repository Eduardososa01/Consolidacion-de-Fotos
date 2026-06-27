# Guía para publicar la plataforma (link final)

Stack: **Render** (la app, gratis) + **Supabase** (base de datos Postgres, gratis).
Las fotos se guardan dentro de la base de datos (no hace falta otra cuenta).

Necesitas: cuenta de **GitHub** (ya tienes), y crear cuenta en **Supabase** y **Render**
(ambas gratis, puedes entrar con GitHub).

---

## Paso 1 — Subir el código a GitHub

Desde la carpeta del proyecto, en PowerShell:

```powershell
cd "c:\Users\Eduardo\OneDrive\Desktop\Consolidacion de fotos"
git init
git add .
git commit -m "Plataforma Reconexion"
```

Luego crea un repositorio nuevo en https://github.com/new (por ejemplo `reconexion`,
**privado** está bien) y conecta:

```powershell
git branch -M main
git remote add origin https://github.com/TU_USUARIO/reconexion.git
git push -u origin main
```

> El `.gitignore` ya evita subir la base local y las fotos de prueba.

---

## Paso 2 — Crear la base de datos en Supabase

1. Entra a https://supabase.com → **New project** (elige una contraseña para la base
   y guárdala).
2. Cuando termine de crearse, ve a **Project Settings → Database → Connection string**
   → pestaña **URI**.
3. Copia la cadena. Se ve así:
   `postgresql://postgres:[TU-PASSWORD]@db.xxxxx.supabase.co:5432/postgres`
   Reemplaza `[TU-PASSWORD]` por la contraseña que pusiste. **Esa cadena es tu
   `DATABASE_URL`.**

---

## Paso 3 — Desplegar la app en Render

## Opción B (recomendada si Render/Koyeb piden verificar identidad) — Hugging Face Spaces

Gratis, 24/7, normalmente **sin verificación de identidad ni tarjeta**.

1. Crea cuenta en https://huggingface.co/join (con email o GitHub).
2. **New → Space** → nombre `coordinacion-ayuda`, **SDK: Docker**, visibilidad Public.
3. El repo ya tiene `Dockerfile` y `README.md` listos. Sube el código al Space:
   - En la pestaña **Files** del Space puedes arrastrar los archivos, **o**
   - Con git: `git remote add space https://huggingface.co/spaces/TU_USUARIO/coordinacion-ayuda`
     y `git push space main`.
4. En **Settings → Variables and secrets** agrega:
   - `DATABASE_URL` = cadena del Session pooler de Supabase
   - `SECRET_KEY` = texto largo al azar
   - `ANTHROPIC_API_KEY` = tu clave (para leer fotos de listas)
5. El Space construye solo y te da una URL pública `https://TU_USUARIO-coordinacion-ayuda.hf.space`.
6. Crea los hospitales/capitanes corriendo en tu PC: `py seed.py` con `DATABASE_URL`
   apuntando a Supabase (así la base que usa el Space queda cargada).

---

## Opción A — Render

1. Entra a https://render.com → **New → Web Service** → conecta tu GitHub y elige el
   repo `Consolidacion-de-Fotos`.
2. Render detecta el `render.yaml`. Si te pide los datos a mano:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Instance type:** Free
3. En **Environment** agrega la variable:
   - `DATABASE_URL` = la cadena de Supabase del Paso 2 (Session pooler)
   - (`SECRET_KEY` la genera Render solo, por el `render.yaml`.)
4. **Create Web Service**. En 1–2 minutos te da una URL como
   `https://coordinacion-ayuda.onrender.com` → **ese es el link**.

---

## Paso 4 — Cargar los hospitales (una vez)

La primera vez hay que crear los 10 hospitales y los capitanes en la base. En Render,
ve a tu servicio → pestaña **Shell** y ejecuta:

```bash
python seed.py
```

Esto imprime el **usuario y contraseña de cada capitán** — guárdalos y repártelos a
cada hospital. (Alternativa: correr `py seed.py` en tu PC apuntando `DATABASE_URL` a
Supabase.)

---

## Listo

- Cualquiera con el link **ve hospitales y necesidades** y puede **comprometerse a
  ayudar** (sin cuenta).
- Los **capitanes** entran con su usuario/contraseña y gestionan su hospital.
- Todo queda guardado en Supabase (no se borra).
- Para actualizar el sitio: `git push` y Render redepliega solo.

### Notas
- En el plan gratis de Render, la app "se duerme" tras un rato sin uso y la **primera
  visita tarda ~30 s** en despertar. Normal.
- Antes de difundirlo ampliamente, revisa **privacidad** y posible abuso (cualquiera
  puede comprometerse a donar).
