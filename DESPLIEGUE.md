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

1. Entra a https://render.com → **New → Web Service** → conecta tu GitHub y elige el
   repo `reconexion`.
2. Render detecta el `render.yaml`. Si te pide los datos a mano:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Instance type:** Free
3. En **Environment** agrega dos variables:
   - `DATABASE_URL` = la cadena de Supabase del Paso 2
   - `ANTHROPIC_API_KEY` = tu clave de Anthropic
4. **Create Web Service**. En 1–2 minutos te da una URL como
   `https://reconexion.onrender.com` → **ese es el link** para tus amigos.

---

## Listo

- Cualquiera con el link puede **buscar** y **subir** (subida abierta, como pediste).
- Las fotos y los nombres quedan guardados en Supabase (no se borran).
- Para actualizar el sitio: `git push` y Render redepliega solo.

### Notas
- En el plan gratis de Render, la app "se duerme" tras un rato sin uso y la **primera
  visita tarda ~30 s** en despertar. Normal.
- Cada lista que se sube consume tu **cuota de la API** de Anthropic.
- Antes de compartirlo ampliamente, conviene revisar **privacidad** (son datos de
  personas vulnerables) y quizá poner una clave para subir.
