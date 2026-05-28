# Reporte de migracion en equipo actual

Fecha: 2026-05-27  
Equipo/ruta del proyecto: `C:\Users\salga\OneDrive\Escritorio\Asofamech`

Este documento resume lo que ocurrio al intentar levantar ASOFAMECH en este
equipo siguiendo `docs/MIGRACION_EQUIPOS.md`.

## Estado final

El proyecto quedo levantado con Docker Compose desde el repositorio local.

Servicios verificados:

| Servicio | Estado |
|---|---|
| PostgreSQL | Levantado y saludable |
| Backend | Levantado y saludable |
| Frontend | Levantado en `http://localhost:3000` |
| Ollama | Levantado |
| Modelo Ollama `llama3:8b` | Descargado |
| Histopatologia AI | No listo |

Lectura del estado:

- Despliegue Docker limpio: logrado.
- Migracion completa de datos: no lograda, porque no estaba disponible el backup `asofamech_migration`.
- IA histopatologica: pendiente por dos dependencias: el checkpoint de la cabeza clasificadora y CONCH preparado en el equipo destino.

Verificaciones realizadas:

```powershell
Invoke-RestMethod http://localhost:8001/health
```

Respuesta esperada/obtenida:

```json
{"status":"ok"}
```

Frontend:

```text
http://localhost:3000 -> HTTP 200
```

## Cosas que faltaron para una migracion completa

### 1. No estaba disponible el backup `asofamech_migration`

No se encontro una carpeta de backup con estructura de migracion:

```text
asofamech_migration/
|-- manifest.json
|-- checksums.sha256
|-- volumes/
|-- artifacts/
|-- uploads/
`-- histology_images/
```

Nota: en el flujo actual, el backup de CONCH/HuggingFace es opcional y solo
debe exportarse si se tiene permiso para redistribuir esa cache. Para pruebas en
otros equipos, lo recomendado es preparar CONCH en el destino con
`scripts\prepare_histopathology_model.ps1` usando un token HuggingFace autorizado.

Se buscaron rutas comunes dentro del perfil del usuario, pero no aparecieron:

```text
C:\Users\salga
C:\Users\salga\OneDrive
C:\Users\salga\OneDrive\Escritorio
C:\Users\salga\Downloads
C:\Users\salga\Documents
```

Impacto:

- No se pudo ejecutar `.\scripts\start_presentation.ps1 -BackupPath "<ruta_backup>"`.
- No se restauraron usuarios, imagenes, uploads, artifacts ni volumenes desde un backup formal.
- Se tuvo que levantar el proyecto desde cero con `docker compose up`.

### 2. Faltan artifacts histopatologicos

El backend espera el checkpoint:

```text
backend/artifacts/histopathology/checkpoints/tri_head_camelyon17_stage15_heavy_neg_v1.pt
```

Actualmente no existe en este equipo.

El endpoint:

```powershell
Invoke-RestMethod http://localhost:8001/api/histopathology/status
```

reporto:

```text
model_ready = false
Classifier checkpoint not found
```

Impacto:

- El modulo histopatologico no puede ejecutar inferencia.
- El visor y la plataforma pueden levantarse, pero ROI/heatmap con IA no quedan operativos.

Como resolverlo:

```powershell
New-Item -ItemType Directory -Force backend\artifacts\histopathology\checkpoints
Copy-Item "<ruta_backup>\artifacts\histopathology\checkpoints\tri_head_camelyon17_stage15_heavy_neg_v1.pt" backend\artifacts\histopathology\checkpoints\
.\scripts\prepare_histopathology_model.ps1
Invoke-RestMethod http://localhost:8001/api/histopathology/status
```

Si el archivo no existe en ningun backup, hay que reentrenar la cabeza
clasificadora con los scripts de `backend/histopathology_offline`.

### 3. Falta validar/preparar CONCH

El script correcto para preparar CONCH es:

```powershell
.\scripts\prepare_histopathology_model.ps1
```

En el flujo actual, Docker Compose espera que CONCH quede disponible dentro del
volumen/cache de HuggingFace como:

```text
/root/.cache/huggingface/conch/pytorch_model.bin
```

El script prepara esa ruta usando el token solo durante el proceso, y luego
recrea el backend sin dejar el token persistido en `.env`.

Ese paso requiere un token HuggingFace con acceso aprobado a:

```text
MahmoodLab/conch
```

Impacto:

- Aunque se copie el checkpoint `.pt`, CONCH tambien debe estar disponible para que `model_ready` sea `true`.
- El token no debe guardarse en `.env`, repositorio, capturas ni chats.

### 4. No se restauraron laminas histologicas grandes

Como no se encontro `asofamech_migration`, tampoco se restauraron laminas desde:

```text
<ruta_backup>\histology_images\camelyon17\images\
```

Destino esperado:

```text
backend\data\camelyon17\images\
```

Impacto:

- La biblioteca de imagenes no quedo poblada con las laminas del equipo origen.
- Si se requiere trabajar con laminas locales, hay que copiarlas manualmente o restaurar el backup.

### 5. No se restauraron uploads ni artifacts

No se restauraron estas carpetas desde backup:

```text
backend\uploads\
backend\artifacts\
```

Impacto:

- No se recuperaron imagenes subidas desde la app.
- No se recuperaron tiles DZI, auditorias, checkpoints ni reportes generados previamente.

## Cosas que fallaron durante el levantamiento

### 1. Docker no estaba corriendo al inicio

Al principio `docker info` fallo porque Docker Desktop no estaba activo o el
daemon no era accesible.

Despues de abrir Docker Desktop, Docker quedo validado:

```text
Docker 28.5.1
```

### 2. Comandos Docker requirieron privilegios elevados

Algunos comandos Docker fallaron desde el sandbox por permisos, por ejemplo al
acceder al daemon o a configuracion local de Docker.

Se resolvio ejecutando los comandos Docker con permisos elevados cuando fue
necesario.

### 3. La base de datos existente tenia esquema viejo/incompleto

Al levantar el backend por primera vez, las migraciones fallaron con:

```text
psycopg2.errors.DuplicateTable: relation "users" already exists
```

Causa:

- El volumen `asofamech_db_data` ya tenia tablas antiguas.
- No existia la tabla `alembic_version`.
- El backend actual intento aplicar la migracion inicial sobre una base que ya tenia `users`.

Tablas detectadas antes de recrear la base:

```text
audit_logs
cases
chat_logs
documents
medical_images
rag_documents
sct_test_results
sct_tests
user_activities
users
```

Datos detectados:

```text
users = 1
medical_images = 1
```

Accion tomada:

- Se respaldo el volumen antiguo.
- Se elimino solo el volumen `asofamech_db_data`.
- Se levanto PostgreSQL limpio para que Alembic creara el esquema actual.

Respaldo creado:

```text
backend/artifacts/volume_backups/asofamech_db_data_before_reset_20260526_235756.tar.gz
```

### 4. El backend no arranco hasta recrear la base

Mientras la base antigua existia, el backend salia con codigo `1` y el frontend
no podia iniciar por depender de un backend saludable.

Despues de recrear la base, el backend quedo `healthy` y el frontend arranco.

## Acciones completadas en este equipo

- Se creo `.env` desde `.env.example`.
- Se construyeron imagenes Docker de backend y frontend.
- Se descargaron dependencias pesadas del backend, incluyendo PyTorch/CUDA.
- Se levanto PostgreSQL limpio.
- Se levanto backend en `http://localhost:8001`.
- Se levanto frontend en `http://localhost:3000`.
- Se levanto Ollama en `http://localhost:11434`.
- Se descargo `llama3:8b` dentro de Ollama.
- Se respaldo el volumen PostgreSQL anterior antes de reemplazarlo.

## Como completar lo que falta

### Opcion recomendada: migrar desde el equipo origen

En el equipo que tiene los datos correctos, generar un backup completo:

```powershell
.\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration"
```

Luego copiar la carpeta `E:\asofamech_migration` al equipo destino, usando disco
externo, red local u otro medio con espacio suficiente.

En el equipo destino, restaurar ese backup:

```powershell
.\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration"
```

Ese paso debe restaurar:

- Base de datos.
- Imagenes histologicas grandes.
- `backend\uploads\`.
- `backend\artifacts\`.
- Volumenes Docker necesarios.

### Completar el modelo histopatologico

Despues de restaurar el backup, verificar que existe el checkpoint de la cabeza
clasificadora:

```powershell
Test-Path backend\artifacts\histopathology\checkpoints\tri_head_camelyon17_stage15_heavy_neg_v1.pt
```

Si el resultado es `False`, copiarlo manualmente desde el backup o desde el
equipo origen:

```powershell
New-Item -ItemType Directory -Force backend\artifacts\histopathology\checkpoints
Copy-Item "E:\asofamech_migration\artifacts\histopathology\checkpoints\tri_head_camelyon17_stage15_heavy_neg_v1.pt" backend\artifacts\histopathology\checkpoints\
```

Luego preparar CONCH en el equipo destino:

```powershell
.\scripts\prepare_histopathology_model.ps1
```

Este script pide un token HuggingFace con acceso a `MahmoodLab/conch`. El token
solo se usa para preparar el modelo y no debe quedar guardado en `.env`.

Finalmente, verificar que el modulo quedo listo:

```powershell
Invoke-RestMethod http://localhost:8001/api/histopathology/status
```

El estado esperado es:

```text
model_ready = true
```

### Verificar imagenes, uploads y artifacts

Comprobar que las imagenes grandes quedaron en su ruta local:

```powershell
Test-Path backend\data\camelyon17\images
Get-ChildItem backend\data\camelyon17\images | Select-Object -First 5
```

Comprobar que `uploads` y `artifacts` fueron restaurados:

```powershell
Test-Path backend\uploads
Test-Path backend\artifacts
```

### Si no existe backup

Si no se consigue `asofamech_migration`, este equipo solo puede quedar como
instalacion limpia. En ese caso hay que:

1. Registrar el primer usuario administrador.
2. Copiar manualmente las laminas a `backend\data\camelyon17\images`.
3. Copiar manualmente el checkpoint `.pt` a `backend\artifacts\histopathology\checkpoints`.
4. Ejecutar `.\scripts\prepare_histopathology_model.ps1`.
5. Volver a probar `/api/histopathology/status`.

## Pendientes recomendados

1. Ubicar o generar el backup `asofamech_migration` desde el equipo origen.
2. Restaurar el backup en este equipo con `.\scripts\start_presentation.ps1 -BackupPath "<ruta_backup>"`.
3. Confirmar que existe el checkpoint `tri_head_camelyon17_stage15_heavy_neg_v1.pt`.
4. Ejecutar `.\scripts\prepare_histopathology_model.ps1` con token HuggingFace autorizado.
5. Verificar `model_ready = true` en `/api/histopathology/status`.
6. Registrar el primer usuario en la app para crear el administrador inicial.
7. Probar login, chatbot/SCT, biblioteca de imagenes y modulo ROI.

## Comandos utiles

Estado de contenedores:

```powershell
docker compose ps
```

Logs del backend:

```powershell
docker compose logs -f backend
```

Verificar backend:

```powershell
Invoke-RestMethod http://localhost:8001/health
```

Verificar histopatologia:

```powershell
Invoke-RestMethod http://localhost:8001/api/histopathology/status
```

Ver modelos Ollama:

```powershell
docker exec asofamech_ollama ollama list
```

