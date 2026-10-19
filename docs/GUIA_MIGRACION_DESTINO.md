# Guía de migración al equipo destino — ASOFAMECH

> **Para quien lee este archivo (humano o asistente IA)**: este documento describe, en orden, qué hacer en el equipo destino para dejar ASOFAMECH operativo con los datos migrados desde el equipo origen y, al final, como **servidor permanente publicado por Cloudflare Tunnel con autoarranque**. Ejecuta los pasos tal cual aparecen. No omitas verificaciones.

---

## 0. Contexto rápido

- **Origen**: equipo donde se desarrolló el proyecto. Allí se generó un backup con el script [scripts/migrate_export.ps1](../scripts/migrate_export.ps1) en modo `-PresentationLite`.
- **Destino**: el equipo donde estás leyendo esto. Va a quedar como servidor permanente del proyecto.
- **Backup entregado**: una carpeta llamada `asofamech_migration_lite` (~23 MB) que contiene la base de datos exportada, los checkpoints del modelo histopatológico y los manifiestos DZI mínimos. **No incluye** láminas CAMELYON17, imágenes Docker, cache HuggingFace ni modelos Ollama — todo eso se descarga/construye en destino.
- **Lo que SÍ viaja por Git**: el código, el `docker-compose.yml`, las migraciones Alembic y el checkpoint `tri_head_stage17_variant_c_augmented.pt` ubicado en [backend/model_registry/checkpoints/](../backend/model_registry/checkpoints/).

---

## 1. Requisitos del equipo destino

Antes de empezar comprueba que tienes:

| Requisito | Verificación |
|---|---|
| Windows 10/11 con PowerShell | `powershell -Command "$PSVersionTable.PSVersion"` |
| Docker Desktop instalado y corriendo | `docker info` |
| GPU NVIDIA con drivers | `nvidia-smi` |
| Runtime CUDA en Docker | `docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi` |
| Git instalado | `git --version` |
| Puertos libres | `3000`, `8001`, `5432`, `11434` sin uso |
| Espacio en disco | **mínimo 60 GB libres** (imágenes Docker + CONCH + LLaMA + eventuales láminas) |
| Internet funcional | Primera ejecución descarga Docker Hub, HuggingFace y Ollama |
| Token HuggingFace | Con acceso aceptado al repo `MahmoodLab/conch` |

**Secretos que vas a necesitar y NO viajan en el backup:**

- `HISTO_HF_TOKEN` — token personal HuggingFace del responsable (empieza con `hf_...`).
- `LLM_API_KEY` *(opcional)* — solo si usarás Groq o API externa en vez de Ollama local.
- `SMTP_*` *(opcional)* — solo si quieres envío real de correos; sin esto queda `email_outbox.jsonl` como simulación.

> **Importante**: nunca escribas estos secretos dentro del repo, el backup, capturas de pantalla ni mensajes de chat.

---

## 2. Clonar el repositorio

```powershell
# Elige dónde dejar el proyecto. Ejemplo:
cd C:\
git clone <URL_DEL_REPO> Asofamech
cd Asofamech

# Confirma rama/commit igual al origen (consulta al responsable si no estás seguro)
git status
git log -1 --oneline
```

El clone trae automáticamente:

- Todo el código backend/frontend.
- `docker-compose.yml` y los Dockerfiles.
- Las 20 migraciones Alembic (`backend/alembic/versions/0001…0020`).
- El checkpoint del clasificador histopatológico (`backend/model_registry/checkpoints/tri_head_stage17_variant_c_augmented.pt`).
- Los scripts de migración y publicación en [scripts/](../scripts/).

---

## 3. Verificar entorno

```powershell
# 3.1 Docker vivo
docker info

# 3.2 GPU detectada
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi

# 3.3 Puertos libres (deberían dar vacío o cero resultados)
netstat -ano | findstr ":3000 :8001 :5432 :11434"
```

Si Docker no arranca con GPU, revisa que Docker Desktop tenga **Settings → Resources → WSL integration → Use GPU** activo y que esté instalado el **NVIDIA Container Toolkit**.

---

## 4. Preparar `.env` con los secretos reales

El script restaurador generará un `.env` desde `.env.example` con un **JWT nuevo seguro**, pero debes añadir el token HuggingFace a mano **antes** de pasar al paso 6 (preparación de CONCH):

```powershell
# Si no existe .env todavía, copia la plantilla
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# Edita el archivo
notepad .env
```

Claves obligatorias/recomendadas a revisar en [.env.example](../.env.example):

```ini
# Secreto JWT: el restaurador lo genera si está vacío o es la plantilla; déjalo así
ASOFAMECH_JWT_SECRET=

# Token HuggingFace del responsable (OBLIGATORIO para CONCH)
HISTO_HF_TOKEN=hf_...

# Checkpoint del clasificador (ya viene en el repo)
HISTO_CLASSIFIER_CHECKPOINT=/app/model_registry/checkpoints/tri_head_stage17_variant_c_augmented.pt

# Modo de operación
APP_ENV=production

# Proveedor LLM (deja ollama a menos que uses Groq)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
# LLM_API_KEY=   # solo si usas Groq o similar

# CORS: el publicador lo actualizará automáticamente al añadir el dominio Cloudflare
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001
ASOFAMECH_PLATFORM_URL=http://localhost:3000/auth
FRONTEND_API_BASE=
```

Guarda el archivo. **No lo commites a git.**

---

## 5. Restaurar el backup y levantar servicios

Conecta el disco externo con el backup. Ubica la carpeta `asofamech_migration_lite` (ejemplo: `E:\asofamech_migration_lite`).

Desde la raíz del proyecto:

```powershell
.\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration_lite" -PullOllamaModel
```

Lo que hace [scripts/start_presentation.ps1](../scripts/start_presentation.ps1):

1. Verifica Docker, GPU y existencia del backup.
2. Verifica el `checksums.sha256` del backup (si falla, repite la copia desde origen — no uses `-SkipChecksum` salvo emergencia).
3. Detiene cualquier stack ASOFAMECH previo.
4. Restaura el volumen Docker `asofamech_db_data` con `volumes/db_backup.tar.gz` (incluye las 20 migraciones Alembic ya aplicadas).
5. Copia láminas desde `histology_images/` a `backend/data/camelyon17/images/`. **En este backup Lite irá vacío**.
6. Reemplaza `backend/artifacts/` y `backend/uploads/` por el contenido mínimo del backup.
7. Construye las imágenes Docker con `docker compose build` (puede tardar **20–40 minutos** la primera vez: Torch, HuggingFace, OpenSlide, OpenCV).
8. Levanta BD, backend, frontend y Ollama.
9. Descarga el modelo `llama3.1:8b` en Ollama gracias al flag `-PullOllamaModel`.
10. Abre `http://localhost:3000` en el navegador.

Espera a que los cuatro contenedores estén `running` / `healthy`:

```powershell
docker compose ps
```

---

## 6. Preparar el modelo histopatológico (CONCH)

El backbone CONCH de MahmoodLab es un modelo con licencia controlada: se descarga en destino con el token HuggingFace del responsable, **nunca** se guarda en el repo.

```powershell
# Opción 1: pasar el token por parámetro (más rápido para un responsable solo)
.\scripts\prepare_histopathology_model.ps1 -Token "hf_xxx"

# Opción 2: dejar que el script lo pida interactivamente (más seguro frente a historial PowerShell)
.\scripts\prepare_histopathology_model.ps1
```

Lo que hace [scripts/prepare_histopathology_model.ps1](../scripts/prepare_histopathology_model.ps1):

1. Lanza un contenedor temporal con tu token y descarga CONCH desde HuggingFace (~1.5 GB).
2. Cachea los pesos en el volumen Docker `asofamech_huggingface_cache` (persistente).
3. Deja un symlink/copia estable en `/root/.cache/huggingface/conch/pytorch_model.bin`.
4. Recrea el backend **sin exponer el token** en variables de entorno.
5. Verifica `GET /api/histopathology/status` hasta ver `model_ready = true`.
6. Elimina el token de la sesión actual de PowerShell.

Si el script termina con error de permisos HuggingFace, abre [huggingface.co/MahmoodLab/conch](https://huggingface.co/MahmoodLab/conch) con la cuenta del token, acepta los términos de uso y vuelve a correr el script.

---

## 7. Verificación funcional

```powershell
# 7.1 Contenedores sanos
docker compose ps
# Esperado:
#   asofamech_db        running/healthy
#   asofamech_backend   running/healthy
#   asofamech_frontend  running
#   asofamech_ollama    running

# 7.2 Backend responde
Invoke-RestMethod http://localhost:8001/health
# Esperado: @{status=ok}

# 7.3 Modelo histopatológico cargado
Invoke-RestMethod http://localhost:8001/api/histopathology/status
# Esperado: model_ready = True

# 7.4 Datos migrados: conteos deben coincidir con origen
docker exec asofamech_db psql -U app_user -d app_db -c `
  "SELECT (SELECT COUNT(*) FROM users) AS users, (SELECT COUNT(*) FROM medical_images) AS imgs, (SELECT COUNT(*) FROM image_annotations) AS anotaciones, (SELECT COUNT(*) FROM cases) AS casos;"
# Esperado al momento del export:
#   users=10, imgs=53, anotaciones=1, casos=7

# 7.5 Migraciones Alembic en head
docker exec asofamech_db psql -U app_user -d app_db -c "SELECT version_num FROM alembic_version;"
# Esperado: b0c1d2e3f4a5 (= 0020_mcq_tests)

# 7.6 Modelo LLM descargado
docker exec asofamech_ollama ollama list
# Esperado: llama3.1:8b

# 7.7 Prueba manual en el navegador (http://localhost:3000)
#     - Login con un usuario existente de la BD migrada
#     - Entrar a la biblioteca de imágenes
#     - Verificar que el chatbot responde
#     - Si subes una lámina CAMELYON17 nueva: abrir visor DZI y disparar heatmap
```

> **Nota sobre las 3 láminas CAMELYON17 registradas en BD** (`patient_004_node_0.tif`, `patient_012_node_1.tif`, `patient_017_node_2.tif`): aparecerán en la biblioteca pero sin archivo físico. Si un usuario intenta abrirlas, dará "no encontrado". Es esperado — el responsable las subirá después o las desactivará con un UPDATE en `medical_images`.

---

## 8. Dejar el sistema publicado permanentemente (Cloudflare Tunnel)

Este equipo va a quedar como servidor del proyecto, publicado por **Cloudflare Quick Tunnel** y arrancando automáticamente al iniciar sesión Windows.

### 8.1 Instalar cloudflared

```powershell
# Opción recomendada: winget
winget install --id Cloudflare.cloudflared

# Verifica que quedó en el PATH o en una de las rutas conocidas
Get-Command cloudflared -ErrorAction SilentlyContinue
# o
Test-Path "C:\Program Files\cloudflared\cloudflared.exe"
```

Si `winget` no está disponible, descarga el instalador directamente desde [github.com/cloudflare/cloudflared/releases](https://github.com/cloudflare/cloudflared/releases) (archivo `cloudflared-windows-amd64.msi`).

### 8.2 Prueba manual el publicador (opcional pero recomendado)

Antes de automatizar, verifica que todo funciona a mano con la GUI de [scripts/start_public_server.ps1](../scripts/start_public_server.ps1):

```powershell
.\scripts\start_public_server.ps1
```

Se abre una ventana con botones. Flujo:

1. **"Levantar/reconstruir"** → confirma que el stack sube bien.
2. **"Publicar con Cloudflare"** → crea un quick tunnel, detecta la URL `https://*.trycloudflare.com`, actualiza `.env` (`CORS_ORIGINS` + `ASOFAMECH_PLATFORM_URL`) y recrea backend/frontend.
3. **"Copiar URL"** → pega la URL en el navegador desde otro equipo y confirma que carga el frontend.
4. **"Detener túnel"** → cierra cloudflared cuando quieras.

Si todo funciona, pasa al autoarranque.

### 8.3 Registrar autoarranque al iniciar sesión Windows

Abre PowerShell **como Administrador** (clic derecho → "Ejecutar como administrador"):

```powershell
cd C:\Asofamech
.\scripts\register_startup_task.ps1
```

Esto registra la tarea programada `ASOFAMECH_Startup` que ejecuta [scripts/startup_auto.ps1](../scripts/startup_auto.ps1) al logon. Esa tarea, cada vez que inicies sesión:

1. Espera 30s a que Windows termine de arrancar.
2. Lanza Docker Desktop si no corre.
3. Espera el daemon Docker hasta 5 min.
4. Ejecuta `docker compose up -d`.
5. Espera el health del backend hasta 3 min.
6. Lanza `cloudflared tunnel --url http://localhost:3000` como proceso persistente.
7. Captura la URL `https://*.trycloudflare.com` del log.
8. Actualiza `.env` con el nuevo CORS y la nueva URL pública.
9. Recrea backend y frontend para aplicar la configuración.
10. Deja logs en [logs/startup_auto.log](../logs/startup_auto.log) y [logs/cloudflared.stdout.log](../logs/cloudflared.stdout.log).

**Comprobar el autoarranque:**

```powershell
# Ver tarea registrada
Get-ScheduledTask -TaskName ASOFAMECH_Startup | Format-List

# Lanzarla manualmente para probar
Start-ScheduledTask -TaskName ASOFAMECH_Startup

# Ver logs mientras se ejecuta
Get-Content .\logs\startup_auto.log -Wait
```

Cuando aparezca `URL publica: https://...trycloudflare.com` en el log, el servidor está listo para recibir tráfico externo.

**Para desinstalar el autoarranque** (si algún día cambias de equipo):

```powershell
# Como Administrador
.\scripts\register_startup_task.ps1 -Remove
```

### 8.4 Nota sobre la URL de Cloudflare Quick Tunnel

Los Quick Tunnels generan una **URL distinta cada vez** que se reinicia cloudflared (ej. `https://humanity-asset-named-particle.trycloudflare.com`). Si necesitas una URL fija y compartible, hay que configurar un **Named Tunnel** con una cuenta de Cloudflare y un dominio propio. Eso queda fuera de esta guía automatizada; mientras tanto, cada reinicio del equipo publica una URL nueva que queda registrada en `.env` y en `logs/startup_auto.log`.

---

## 9. Operación diaria

```powershell
# Ver estado
docker compose ps

# Ver logs en vivo
docker compose logs -f backend
docker compose logs -f frontend

# Reiniciar sin tocar datos
docker compose restart backend

# Actualizar código desde git (preserva BD y volúmenes)
.\scripts\update_from_git.ps1

# Apagar todo manualmente (el autoarranque lo volverá a subir al próximo logon)
docker compose down

# Reiniciar cloudflared manualmente si cae
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process
Start-ScheduledTask -TaskName ASOFAMECH_Startup
```

---

## 10. Troubleshooting

| Síntoma | Causa probable | Acción |
|---|---|---|
| `docker compose build` falla descargando paquetes | Sin internet / firewall / proxy | Reintenta con red cableada o configura proxy en Docker Desktop |
| `model_ready = False` después del paso 6 | Token HF sin acceso aceptado a `MahmoodLab/conch` o checkpoint `.pt` ausente | Entra a [huggingface.co/MahmoodLab/conch](https://huggingface.co/MahmoodLab/conch) y acepta términos; confirma que existe `backend/model_registry/checkpoints/tri_head_stage17_variant_c_augmented.pt` |
| Checksum inválido en paso 5 | Backup se copió incompleto | Vuelve a copiar la carpeta `asofamech_migration_lite` desde el disco externo; evita `-SkipChecksum` |
| Puerto 3000/8001/5432/11434 ocupado | Otro proceso usa esos puertos | `netstat -ano \| findstr ":3000"` → detén el proceso o cambia el mapeo en [docker-compose.yml](../docker-compose.yml) |
| `nvidia-smi` dentro de Docker falla | Falta NVIDIA Container Toolkit o GPU no compartida | Instala el toolkit y reinicia Docker Desktop con integración CUDA activa |
| Ollama no responde | Modelo no descargado | `docker exec asofamech_ollama ollama pull llama3.1:8b` |
| El publicador no obtiene URL | cloudflared no está en PATH / log de cloudflared vacío | Revisa [logs/cloudflared.stderr.log](../logs/cloudflared.stderr.log). Verifica `Get-Command cloudflared` |
| Al reiniciar la URL pública cambió | Es un Quick Tunnel (comportamiento esperado) | Compártela nuevamente; para URL fija configura Named Tunnel con dominio propio |
| Backend no arranca por falta de secreto JWT | `.env` sin `ASOFAMECH_JWT_SECRET` | El script restaurador lo genera automáticamente si está vacío; si lo editaste, borra la línea y vuelve a correr `start_presentation.ps1` |

---

## 11. Mapa de archivos clave en este repositorio

- [docker-compose.yml](../docker-compose.yml) — definición de los 4 servicios (db, backend, frontend, ollama).
- [.env.example](../.env.example) — plantilla con todas las variables documentadas.
- [backend/alembic/versions/](../backend/alembic/versions/) — 20 migraciones; `alembic upgrade head` corre automático al arrancar el backend.
- [backend/model_registry/checkpoints/](../backend/model_registry/checkpoints/) — clasificador histopatológico versionado en git.
- [scripts/migrate_export.ps1](../scripts/migrate_export.ps1) — exportador del backup (se usó en origen).
- [scripts/start_presentation.ps1](../scripts/start_presentation.ps1) — restaurador del backup (paso 5).
- [scripts/prepare_histopathology_model.ps1](../scripts/prepare_histopathology_model.ps1) — descarga CONCH (paso 6).
- [scripts/start_public_server.ps1](../scripts/start_public_server.ps1) — publicador GUI manual (paso 8.2).
- [scripts/startup_auto.ps1](../scripts/startup_auto.ps1) — publicador automático al logon (paso 8.3).
- [scripts/register_startup_task.ps1](../scripts/register_startup_task.ps1) — registra la tarea programada (paso 8.3).
- [scripts/update_from_git.ps1](../scripts/update_from_git.ps1) — pull + rebuild + Alembic head (operación diaria).

Documentación complementaria del proyecto:

- [docs/MIGRACION_EQUIPOS.md](MIGRACION_EQUIPOS.md) — manual general de migración entre equipos.
- [docs/DEFENSA_DOS_EQUIPOS.md](DEFENSA_DOS_EQUIPOS.md) — operación con PC principal + notebook de respaldo.
- [docs/DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — guía de desarrollo.
- [docs/MANUAL_DOCENTE_ADMIN.md](MANUAL_DOCENTE_ADMIN.md) — flujos del rol docente/administrador.
- [docs/MANUAL_ESTUDIANTE.md](MANUAL_ESTUDIANTE.md) — flujos del rol estudiante.

---

## 12. Checklist final de entrega

Marca cada ítem a medida que lo completes:

- [ ] Repositorio clonado en destino, mismo commit que el origen.
- [ ] Docker Desktop corriendo con integración GPU NVIDIA.
- [ ] `.env` creado y con `HISTO_HF_TOKEN` real.
- [ ] `start_presentation.ps1 -PullOllamaModel` completado sin errores de checksum.
- [ ] `docker compose ps` muestra los 4 contenedores sanos.
- [ ] `prepare_histopathology_model.ps1` completado y `/api/histopathology/status` responde `model_ready=True`.
- [ ] `ollama list` incluye `llama3.1:8b`.
- [ ] Conteos de `users`, `medical_images`, `image_annotations`, `cases` coinciden con el origen.
- [ ] Login y chatbot funcionan desde `http://localhost:3000`.
- [ ] `cloudflared` instalado y probado manualmente desde `start_public_server.ps1`.
- [ ] Tarea programada `ASOFAMECH_Startup` registrada como Administrador.
- [ ] Reiniciaste sesión Windows y en [logs/startup_auto.log](../logs/startup_auto.log) aparece una URL pública `https://*.trycloudflare.com` operativa.
- [ ] Confirmado desde otro equipo/red que la URL pública abre el frontend.

Cuando todo esté marcado, el equipo destino ya está operando como servidor permanente del proyecto.
