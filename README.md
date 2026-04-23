# Mama's Fish House — Reservation Watcher

Sistema automático que chequea disponibilidad en Mama's Fish House (plataforma SevenRooms) cada 5 minutos y manda email apenas aparece un slot que cumpla los criterios.

**Criterios fijos en este build:**
- Fechas: **10–13 Mayo 2026**
- Party size: **6, 7 u 8 personas**
- Horario: **6:00 PM HST en adelante**

Todo corre gratis en GitHub Actions. Tiempo total de setup: ~20 minutos. No hay que instalar nada en tu compu.

---

## Paso 0 — Pre-requisitos

- Cuenta de GitHub. Si no tenés: [github.com/signup](https://github.com/signup)
- Cuenta de Gmail con **2-Factor Authentication activado** (requisito de Google para app passwords)
- Si el 2FA no está activo: [myaccount.google.com/security](https://myaccount.google.com/security) → "2-Step Verification" → On

---

## Paso 1 — Crear el repo

1. Entrá a [github.com/new](https://github.com/new)
2. **Repository name:** `mamas-fish-watcher`
3. Marcá **Private** (importante, no queremos que sea público)
4. **NO** marques "Add a README file"
5. Click **Create repository**

En la pantalla que te muestra después, buscá el link **"uploading an existing file"** (está en el texto chiquito cerca de "push an existing repository").

Descomprimí el zip que te pasé. Vas a ver esta estructura:

```
mamas-fish-watcher/
├── poll.py
├── requirements.txt
├── state.json
├── README.md
├── .gitignore
└── .github/
    └── workflows/
        └── poll.yml
```

Seleccioná **todos** los archivos y carpetas (incluyendo `.github` — IMPORTANTE que se suba la carpeta completa con su estructura) y arrastralos a la zona de upload de GitHub. Esperá a que todos aparezcan en la lista, después scroll hacia abajo y click **Commit changes**.

**Verificá:** en tu repo, navegá a `.github/workflows/poll.yml`. Si el archivo existe ahí, la estructura subió bien. Si no lo ves, la carpeta `.github` no subió — repetí el upload.

---

## Paso 2 — Generar un Gmail App Password

GitHub va a usar Gmail para mandar los emails de alerta. Por seguridad no usamos tu password real, generamos una "app password" de 16 caracteres específica para este uso.

1. Andá a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Si te pide re-login, hacelo
3. **App name:** `mamas-fish-watcher`
4. Click **Create**
5. Copiá los **16 caracteres** que te muestra (sin espacios). **Guardalos ya** — Google no te los muestra de nuevo.

---

## Paso 3 — Agregar secrets al repo

1. En tu repo de GitHub, click **Settings** (arriba a la derecha del repo, NO de tu cuenta)
2. Sidebar izquierdo: **Secrets and variables** → **Actions**
3. Click **New repository secret** y agregá estos tres (uno por uno, click "Add secret" entre cada uno):

| Name | Value |
|------|-------|
| `SMTP_USER` | Tu dirección de Gmail (ej: `camilo@gmail.com`) |
| `SMTP_PASS` | Los 16 caracteres del app password (sin espacios) |
| `ALERT_TO` | Email donde querés recibir alertas (puede ser el mismo de arriba) |

**Importante:** los nombres deben ser exactamente así, en MAYÚSCULAS.

---

## Paso 4 — Activar Actions y correr por primera vez

1. Click en la pestaña **Actions** (arriba del repo)
2. Si aparece un warning tipo *"Workflows aren't being run on this repository"*, click **I understand my workflows, go ahead and enable them**
3. En el sidebar izquierdo, click **Poll Mama's Fish House**
4. Arriba a la derecha: botón **Run workflow** → dejá la branch en `main` → click **Run workflow**
5. Esperá ~30 segundos, refrescá la página. Vas a ver un run nuevo en la lista.
6. Click en ese run → click en el job **poll** → expandí el paso **"Run poller"** para ver los logs.

Si todo está OK, vas a ver algo como:

```
=== Poll started 2026-04-21T...Z ===
party_size=6: 0 matching slot(s)
party_size=7: 0 matching slot(s)
party_size=8: 0 matching slot(s)
No new slots this run.
=== Done. Known: 0 | new: 0 | errors: 0 ===
```

**Cero slots es lo esperado** — Mama's está completamente booked. Lo que importa es que el script corre sin errores.

De acá en adelante, Actions corre automáticamente cada 5 minutos. No tocás nada más.

---

## Paso 5 — Cuándo llegue una alerta

Vas a recibir email con asunto: `[MAMA'S] X slot(s) open — BOOK NOW`

**Protocolo de respuesta rápida:**

1. Abrí el email. Anotá **fecha + hora + party size**.
2. Andá YA a: [sevenrooms.com/reservations/mamasfishhouserestaurantinn](https://www.sevenrooms.com/reservations/mamasfishhouserestaurantinn)
3. Seleccioná la fecha y el party size del email
4. Click en el slot que apareció
5. Completá la reserva con la tarjeta de K/J
6. Confirmada → apagá el watcher (Paso 6)

**Velocidad es crítica.** Un slot que aparece por cancelación puede desaparecer en <10 min. Meta: confirmar la reserva en menos de 5 min desde que llegó el email. Tené la app de email con push notifications en el celular.

---

## Paso 6 — Apagar el sistema cuando reservaste

1. Pestaña **Actions**
2. Sidebar izquierdo: **Poll Mama's Fish House**
3. Arriba a la derecha: menu `⋯` → **Disable workflow**

Listo, dejó de correr.

Para reactivarlo después (otro restaurante, otras fechas): mismo menu → **Enable workflow**, y editás la config en `poll.py`.

---

## Ajustar criterios más adelante

Todas las variables están al tope de `poll.py`:

```python
VENUE_SLUG = "mamasfishhouserestaurantinn"
START_DATE = "2026-05-10"
END_DATE = "2026-05-13"
PARTY_SIZES = [6, 7, 8]
MIN_HOUR_HST = 18
```

Para editar desde la web de GitHub: abrí `poll.py` en el repo → ícono del lápiz (arriba derecha) → cambiá los valores → scroll down → **Commit changes**.

Para otro restaurante en SevenRooms: andá a la URL de reserva del restaurante (ej: `sevenrooms.com/reservations/<slug>`), el slug que aparece es el nuevo `VENUE_SLUG`.

---

## Troubleshooting

**Run falla con `KeyError: 'SMTP_USER'`**
Los secrets no están cargados, o tienen otro nombre. Revisá Paso 3: Settings → Secrets and variables → Actions. Los nombres deben ser exactos.

**Run falla con `SMTPAuthenticationError: Username and Password not accepted`**
App password mal copiado o 2FA no estaba activo cuando lo generaste. Regeneralo (Paso 2) y actualizá el secret `SMTP_PASS`.

**Logs muestran `HTTP 403` o `HTTP 429`**
SevenRooms bloqueó la IP de GitHub Actions (raro, pero posible con volumen). Mandame los logs y cambio user-agent / ajusto frecuencia.

**Logs muestran `HTTP 400` o `no 'availability' key`**
SevenRooms cambió el schema. Mandame los logs (especialmente la línea `[debug] top keys:`) y lo actualizo.

**Logs dicen "Alert email sent" pero no llegó email**
Chequeá spam/promotions. Marcá el sender como "Not spam" para que los siguientes lleguen a inbox.

**No sé si está corriendo**
Andá a **Actions** → deberías ver runs nuevos cada 5 min. Si no, el workflow está disabled — re-habilitalo.

---

## Costos

- GitHub Actions: gratis (free tier incluye 2,000 min/mes para repos privados; este script usa ~1 min/run × 288 runs/día × 30 días = ~8,640 min. **Acá viene un issue** — ver abajo).
- Gmail SMTP: gratis.
- **Total:** $0/mes si usás una org pública o cuenta Pro. Si usás cuenta Free privada, ver nota abajo.

**Nota sobre GitHub free tier:** el límite de 2,000 min/mes se puede pasar con polling cada 5 min. Opciones:
1. Hacer el repo **público** en vez de privado → minutos ilimitados. El código no tiene credenciales sensibles (todo vive en Secrets), así que es seguro hacerlo público.
2. Dejar privado y subir a cada 10 min (cambiás `*/5` a `*/10` en `poll.yml`) → ~4,320 min/mes, todavía se pasa un poco.
3. Plan GitHub Pro ($4/mes) → 3,000 min, tampoco alcanza.
4. Repo público (opción 1) es lo más simple. **Recomendado.**

Para hacerlo público: Settings → scroll to bottom → Danger Zone → Change repository visibility → Public.
