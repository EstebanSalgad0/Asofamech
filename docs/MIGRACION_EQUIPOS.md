# Manual de transferencia e instalacion en otros equipos

Este manual explica como mover ASOFAMECH desde un equipo origen hacia uno o mas
equipos destino para pruebas, presentaciones o validacion funcional.

La idea central es:

```text
Docker mueve el software.
El backup mueve los datos pesados, checkpoints propios y volumenes permitidos.
```

Para actualizaciones normales entre equipos, Git mueve el codigo y Alembic
mueve la estructura de la base de datos. Despues de un `git pull`, el backend
ejecuta `alembic upgrade head` al iniciar el contenedor; asi se aplican cambios
como nuevas tablas, por ejemplo `audit_logs`. Los datos reales siguen viajando
por backup/restauracion o por seeders/migraciones de datos especificas.

Flujo automatizado recomendado:

| Necesidad | Script | Que mueve |
|---|---|---|
| Actualizacion normal | `scripts\update_from_git.ps1` | Codigo, frontend/backend reconstruidos y migraciones Alembic. |
| Sincronizacion de datos | `scripts\migrate_export.ps1` + `scripts\start_presentation.ps1` | Base de datos, uploads, artifacts, laminas y volumenes permitidos. |
| Modelos IA pesados | `scripts\prepare_histopathology_model.ps1` | Cache autorizado de CONCH en el equipo destino. |

Uso normal en el equipo destino cuando solo cambiaron codigo, migraciones o
frontend:

```powershell
.\scripts\update_from_git.ps1
```

Ese comando hace `git pull --ff-only`, reconstruye `backend` y `frontend`,
espera el `health` del backend y abre el frontend. No reemplaza datos reales
de la base; para eso se usa el backup.

Las laminas histologicas grandes, por ejemplo archivos `.tif`, `.tiff` o `.svs`
de varios GB, no se suben por navegador ni se guardan dentro de la imagen
Docker. Se copian como archivos locales y Docker las monta en el backend.

---

## 1. Que incluye la transferencia

El script `scripts\migrate_export.ps1` prepara un backup con:

```text
asofamech_migration/
|-- artifacts/
|-- histology_images/
|   `-- camelyon17/
|       `-- images/
|-- uploads/
|-- volumes/
|   |-- db_backup.tar.gz
|   |-- hf_backup.tar.gz  (opcional, solo con -IncludeRestrictedModelCache)
|   |-- ollama_backup.tar.gz
|   `-- compose_images.tar
|-- checksums.sha256
`-- manifest.json
```

Contenido principal:

| Elemento | Para que sirve |
|---|---|
| `db_backup.tar.gz` | Base de datos PostgreSQL con usuarios, imagenes registradas, historial, SCT, RAG, etc. |
| `hf_backup.tar.gz` | Opcional. Cache HuggingFace/CONCH; no se exporta por defecto por restricciones de acceso/licencia. |
| `ollama_backup.tar.gz` | Modelos descargados de Ollama, por ejemplo `llama3:8b`. |
| `compose_images.tar` | Imagenes Docker disponibles para evitar recompilar o descargar en destino. |
| `histology_images/` | Laminas histologicas grandes copiadas desde `backend/data/camelyon17/images`. |
| `uploads/` | Imagenes subidas desde la app y tiles DZI generados. |
| `artifacts/` | Checkpoints propios, heatmaps, auditorias y archivos del modulo histopatologico. |
| `checksums.sha256` | Verificacion de integridad de los archivos transferidos. |
| `manifest.json` | Inventario del backup. |

Nota sobre CONCH:

El backbone CONCH de MahmoodLab se obtiene desde HuggingFace y requiere aceptar
sus terminos. Para pruebas cerradas en equipos controlados, el responsable puede
usar su token para preparar el equipo destino con `scripts\prepare_histopathology_model.ps1`.
El token no se entrega a estudiantes ni se guarda en el repositorio.

---

## 2. Requisitos del equipo destino

Antes de transferir, verificar:

- Windows con PowerShell.
- Docker Desktop instalado y corriendo.
- Al menos 30 GB libres; recomendado 60 GB o mas si se llevan muchas laminas.
- Puertos libres: `3000`, `8001`, `5432`, `11434`.
- GPU NVIDIA recomendada para histopatologia y LLM.
- Disco externo o pendrive en formato NTFS o exFAT. Evitar FAT32 porque limita archivos a 4 GB.

Nota sobre GPU:

El `docker-compose.yml` actual reserva GPU para backend y Ollama. Si el equipo
destino no tiene NVIDIA, Docker puede fallar por las lineas `gpus: all` y los
bloques `deploy.resources.reservations.devices`. En ese caso se debe usar un
compose/override CPU o quitar temporalmente esas secciones.

---

## 3. Exportar desde el equipo origen

Desde la raiz del proyecto:

```powershell
.\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration"
```

Si solo se quieren mover laminas especificas para una prueba, pasar los nombres
exactos:

```powershell
.\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration" -HistologyImageNames "patient_017_node_2.tif","patient_012_node_1.tif"
```

Ese modo copia solo esas laminas desde `backend/data/camelyon17/images/` y evita
llevar todo el dataset local. Al restaurar, `scripts\start_presentation.ps1` sincroniza
la biblioteca para que no queden visibles laminas CAMELYON17 no incluidas en el
backup.

El script hace lo siguiente:

1. Verifica Docker.
2. Levanta la base de datos si es necesario.
3. Detiene el stack para respaldar volumenes de forma consistente.
4. Exporta la base de datos.
5. Copia laminas desde:

```text
backend/data/camelyon17/images/
```

6. Copia:

```text
backend/uploads/
backend/artifacts/
```

7. Exporta el volumen de Ollama.
8. No exporta HuggingFace/CONCH por defecto; se prepara en destino con token.
9. Guarda imagenes Docker disponibles en `compose_images.tar`.
10. Genera `manifest.json` y `checksums.sha256`.

Si no se quieren exportar las imagenes Docker:

```powershell
.\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration" -SkipDockerImages
```

Eso reduce el peso del backup, pero el equipo destino necesitara internet o
tiempo para construir/descargar imagenes.

### Modo recomendado si el disco externo es lento

Para presentacion o pruebas con pocas laminas, conviene usar el modo liviano.
Este modo deja que Docker reconstruya/descargue lo que pueda en el equipo
destino y evita mover por disco:

- `compose_images.tar`;
- volumen de Ollama;
- artifacts de entrenamiento, embeddings, patches y debug pesados;
- tiles DZI pregenerados.

Si solo se quieren mover las dos laminas de validacion actuales:

```powershell
& {
  $names = @("patient_017_node_2.tif", "patient_012_node_1.tif")
  .\scripts\migrate_export.ps1 `
    -BackupPath "E:\asofamech_migration_lite" `
    -PresentationLite `
    -HistologyImageNames $names
}
```

El backup liviano conserva:

- base de datos;
- laminas seleccionadas;
- checkpoints/reportes/heatmaps minimos del modelo histopatologico;
- manifiestos `.dzi` necesarios para abrir WSI con tiles dinamicos.

En destino se restaura igual:

```powershell
.\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration_lite"
```

Si tambien se quiere descargar el modelo de chat local durante la restauracion:

```powershell
.\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration_lite" -PullOllamaModel
```

Este modo requiere que el equipo destino pueda construir/descargar imagenes
Docker o que ya las tenga en cache. Si el destino no tiene internet, usar el
modo normal con `compose_images.tar` sigue siendo mas autonomo, pero mas pesado.

Si existe autorizacion explicita para mover el cache de CONCH, se puede incluir:

```powershell
.\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration" -IncludeRestrictedModelCache
```

Para las pruebas con estudiantes, la recomendacion es no usar esa opcion y
preparar CONCH en el equipo destino con tu token.

Si se quiere forzar la exportacion de todas las laminas locales disponibles:

```powershell
.\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration" -AllHistologyImages
```

Usar esa opcion solo cuando realmente se quiera mover toda la carpeta
`backend/data/camelyon17/images/`, porque puede pesar cientos de GB.

---

## 4. Copiar el backup al equipo destino

Copiar la carpeta completa:

```text
E:\asofamech_migration
```

al otro equipo usando disco externo, red local o almacenamiento seguro.

No copiar archivos sueltos. La carpeta debe conservar:

```text
manifest.json
checksums.sha256
volumes/
artifacts/
uploads/
histology_images/
```

Para laminas histologicas grandes, usar NTFS o exFAT. Si se usa un servicio de
nube, comprobar que termino de sincronizar todos los archivos antes de restaurar.

---

## 5. Preparar el equipo destino

En el equipo destino:

1. Clonar o copiar el repositorio ASOFAMECH.
2. Abrir PowerShell en la raiz del proyecto.
3. Verificar que Docker Desktop este corriendo:

```powershell
docker info
```

4. Tener el backup accesible, por ejemplo:

```text
E:\asofamech_migration
```

---

## 6. Restaurar e iniciar en el equipo destino

Desde la raiz del proyecto:

```powershell
.\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration"
```

El script hace lo siguiente:

1. Verifica Docker.
2. Verifica `checksums.sha256`.
3. Detiene un stack activo de ASOFAMECH.
4. Restaura la base de datos.
5. Copia laminas a:

```text
backend/data/camelyon17/images/
```

6. Copia `artifacts/` y `uploads/`.
7. Restaura Ollama y HuggingFace/CONCH solo si ese cache venia incluido.
8. Carga imagenes Docker desde `compose_images.tar`, si existe.
9. Levanta:

```text
db
backend
frontend
ollama
```

10. Abre:

```text
http://localhost:3000
```

Si se necesita omitir la verificacion de hashes:

```powershell
.\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration" -SkipChecksum
```

Usar esto solo si el archivo `checksums.sha256` no existe o si se esta haciendo
una prueba controlada.

---

## 7. Preparar CONCH en el equipo destino

Si el backup no incluye `volumes/hf_backup.tar.gz`, preparar el backbone
preentrenado CONCH en el equipo destino con:

```powershell
.\scripts\prepare_histopathology_model.ps1
```

El script:

1. Pide tu token HuggingFace con acceso a `MahmoodLab/conch`.
2. Usa un contenedor temporal para descargar/cachear CONCH.
3. Deja una ruta local estable dentro del volumen Docker:

```text
/root/.cache/huggingface/conch/pytorch_model.bin
```

4. Recrea el backend sin token.
5. Verifica `GET /api/histopathology/status`.
6. Elimina el token de la sesion PowerShell.
7. Deja el equipo listo para que los estudiantes usen la plataforma.

Tambien se puede pasar el token como parametro si estas solo en el equipo:

```powershell
.\scripts\prepare_histopathology_model.ps1 -Token "hf_xxx"
```

No guardar el token en `.env`, README, backups, capturas de pantalla ni chats.
Los estudiantes solo deben acceder a la plataforma, no al token ni a los pesos.

---

## 8. Como se transfieren las imagenes histologicas grandes

Las imagenes pesadas se tratan como datos externos.

En origen viven en:

```text
backend/data/camelyon17/images/
```

El exportador las copia a:

```text
backup/histology_images/camelyon17/images/
```

El restaurador las copia en destino a:

```text
backend/data/camelyon17/images/
```

Docker monta esa carpeta dentro del backend como:

```text
/app/data/camelyon17/images/
```

Si tambien se restaura la base de datos, las laminas ya importadas deberian
aparecer directamente en la biblioteca.

Si no se restaura la base de datos, o si se quiere registrar una lamina nueva:

1. Copiar el archivo a `backend/data/camelyon17/images/`.
2. Levantar Docker.
3. Entrar como docente o administrador.
4. Ir a `Configuracion -> Imagenes`.
5. Usar `Importar CAMELYON17 local`.

Esto no sube el archivo otra vez. Solo registra metadata y prepara el visor DZI.

---

## 9. Verificacion despues de restaurar

Ejecutar:

```powershell
docker compose ps
```

Esperado:

```text
asofamech_db        running/healthy
asofamech_backend   running/healthy
asofamech_frontend  running
asofamech_ollama    running
```

Verificar backend:

```powershell
Invoke-RestMethod http://localhost:8001/health
```

Respuesta esperada:

```json
{"status":"ok"}
```

Verificar frontend:

```text
http://localhost:3000
```

Verificar modelo histopatologico:

```powershell
Invoke-RestMethod http://localhost:8001/api/histopathology/status
```

Esperado:

```text
model_ready = True
```

Ver logs si algo falla:

```powershell
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f ollama
docker compose logs -f db
```

---

## 10. Problemas comunes

### Docker no esta corriendo

Abrir Docker Desktop y esperar a que termine de iniciar. Luego repetir:

```powershell
docker info
```

### Puerto ocupado

Si `3000`, `8001`, `5432` o `11434` estan ocupados, detener el proceso que usa
ese puerto o cambiar el mapeo en `docker-compose.yml`.

### Error por GPU

Si aparece un error relacionado con `gpus: all` o NVIDIA:

- Confirmar que hay GPU NVIDIA y drivers instalados.
- Si el equipo no tiene GPU, usar un override CPU o quitar temporalmente las
  secciones GPU del compose.

### No aparecen las laminas

Revisar:

```text
backend/data/camelyon17/images/
```

Si los archivos estan ahi pero no aparecen en biblioteca, entrar a:

```text
Configuracion -> Imagenes -> Importar CAMELYON17 local
```

### Checksum invalido

El archivo se copio incompleto o se modifico. Volver a copiar el backup desde el
origen. En caso de emergencia se puede usar `-SkipChecksum`, pero no es lo ideal.

### Modelo Ollama no responde

Verificar:

```powershell
docker compose logs -f ollama
docker exec -it asofamech_ollama ollama list
```

Si no esta `llama3:8b`, descargarlo:

```powershell
docker exec -it asofamech_ollama ollama pull llama3:8b
```

### Modelo histopatologico no disponible

Revisar que exista el checkpoint:

```text
backend/artifacts/histopathology/checkpoints/
```

Y revisar logs:

```powershell
docker compose logs -f backend
```

Si el error menciona CONCH, HuggingFace o autenticacion:

```powershell
.\scripts\prepare_histopathology_model.ps1
```

---

## 11. Checklist para entregar a otro equipo

Antes de enviar:

- [ ] Ejecutar `.\scripts\migrate_export.ps1 -BackupPath "<ruta>"`.
- [ ] Confirmar que el backup tiene `manifest.json`.
- [ ] Confirmar que existe `checksums.sha256`.
- [ ] Confirmar que `volumes/db_backup.tar.gz` existe.
- [ ] Confirmar que `volumes/ollama_backup.tar.gz` existe si se requiere LLaMA local.
- [ ] Confirmar que `backend/artifacts/histopathology/checkpoints/` contiene la cabeza clasificadora.
- [ ] Preparar CONCH en destino con `scripts\prepare_histopathology_model.ps1` si no se incluyo `hf_backup.tar.gz`.
- [ ] Confirmar que las laminas estan en `histology_images/camelyon17/images/`.
- [ ] Confirmar que el disco externo usa NTFS o exFAT.
- [ ] Probar restauracion en al menos un equipo limpio antes de las pruebas.

En el equipo destino:

- [ ] Docker Desktop abierto.
- [ ] Ejecutar `.\scripts\start_presentation.ps1 -BackupPath "<ruta_backup>"`.
- [ ] Abrir `http://localhost:3000`.
- [ ] Verificar login.
- [ ] Verificar biblioteca de imagenes.
- [ ] Abrir una lamina histologica.
- [ ] Ejecutar `.\scripts\prepare_histopathology_model.ps1` si `model_ready` es `False`.
- [ ] Probar un ROI o heatmap si corresponde.
- [ ] Probar chatbot/SCT si corresponde.

---

## 12. Resumen rapido

Para una actualizacion normal desde GitHub, sin reemplazar datos:

```powershell
.\scripts\update_from_git.ps1
```

Esto actualiza codigo, reconstruye backend/frontend y aplica migraciones al
arrancar el backend.

Para copiar datos reales desde un equipo origen:

En el equipo origen:

```powershell
.\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration"
```

Mover `E:\asofamech_migration` al equipo destino.

En el equipo destino:

```powershell
.\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration"
```

Preparar CONCH una vez, solo por el responsable:

```powershell
.\scripts\prepare_histopathology_model.ps1
```

Abrir:

```text
http://localhost:3000
```
