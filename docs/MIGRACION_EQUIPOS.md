# Manual de transferencia e instalacion en otros equipos

Este manual explica como mover ASOFAMECH desde un equipo origen hacia uno o mas
equipos destino para pruebas, presentaciones o validacion funcional.

La idea central es:

```text
Docker mueve el software.
El backup mueve los datos pesados, modelos y volumenes.
```

Las laminas histologicas grandes, por ejemplo archivos `.tif`, `.tiff` o `.svs`
de varios GB, no se suben por navegador ni se guardan dentro de la imagen
Docker. Se copian como archivos locales y Docker las monta en el backend.

---

## 1. Que incluye la transferencia

El script `migrate_export.ps1` prepara un backup con:

```text
asofamech_migration/
|-- artifacts/
|-- histology_images/
|   `-- camelyon17/
|       `-- images/
|-- uploads/
|-- volumes/
|   |-- db_backup.tar.gz
|   |-- hf_backup.tar.gz
|   |-- ollama_backup.tar.gz
|   `-- compose_images.tar
|-- checksums.sha256
`-- manifest.json
```

Contenido principal:

| Elemento | Para que sirve |
|---|---|
| `db_backup.tar.gz` | Base de datos PostgreSQL con usuarios, imagenes registradas, historial, SCT, RAG, etc. |
| `hf_backup.tar.gz` | Cache HuggingFace/CONCH usada por el modelo histopatologico. |
| `ollama_backup.tar.gz` | Modelos descargados de Ollama, por ejemplo `llama3:8b`. |
| `compose_images.tar` | Imagenes Docker disponibles para evitar recompilar o descargar en destino. |
| `histology_images/` | Laminas histologicas grandes copiadas desde `backend/data/camelyon17/images`. |
| `uploads/` | Imagenes subidas desde la app y tiles DZI generados. |
| `artifacts/` | Checkpoints, heatmaps, auditorias y archivos del modelo histopatologico. |
| `checksums.sha256` | Verificacion de integridad de los archivos transferidos. |
| `manifest.json` | Inventario del backup. |

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
.\migrate_export.ps1 -BackupPath "E:\asofamech_migration"
```

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

7. Exporta volumenes de HuggingFace y Ollama.
8. Guarda imagenes Docker disponibles en `compose_images.tar`.
9. Genera `manifest.json` y `checksums.sha256`.

Si no se quieren exportar las imagenes Docker:

```powershell
.\migrate_export.ps1 -BackupPath "E:\asofamech_migration" -SkipDockerImages
```

Eso reduce el peso del backup, pero el equipo destino necesitara internet o
tiempo para construir/descargar imagenes.

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
.\start_presentation.ps1 -BackupPath "E:\asofamech_migration"
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
7. Restaura volumenes de HuggingFace y Ollama.
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
.\start_presentation.ps1 -BackupPath "E:\asofamech_migration" -SkipChecksum
```

Usar esto solo si el archivo `checksums.sha256` no existe o si se esta haciendo
una prueba controlada.

---

## 7. Como se transfieren las imagenes histologicas grandes

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

## 8. Verificacion despues de restaurar

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

Ver logs si algo falla:

```powershell
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f ollama
docker compose logs -f db
```

---

## 9. Problemas comunes

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

---

## 10. Checklist para entregar a otro equipo

Antes de enviar:

- [ ] Ejecutar `.\migrate_export.ps1 -BackupPath "<ruta>"`.
- [ ] Confirmar que el backup tiene `manifest.json`.
- [ ] Confirmar que existe `checksums.sha256`.
- [ ] Confirmar que `volumes/db_backup.tar.gz` existe.
- [ ] Confirmar que `volumes/ollama_backup.tar.gz` existe si se requiere LLaMA local.
- [ ] Confirmar que `volumes/hf_backup.tar.gz` existe si se requiere histopatologia.
- [ ] Confirmar que las laminas estan en `histology_images/camelyon17/images/`.
- [ ] Confirmar que el disco externo usa NTFS o exFAT.
- [ ] Probar restauracion en al menos un equipo limpio antes de las pruebas.

En el equipo destino:

- [ ] Docker Desktop abierto.
- [ ] Ejecutar `.\start_presentation.ps1 -BackupPath "<ruta_backup>"`.
- [ ] Abrir `http://localhost:3000`.
- [ ] Verificar login.
- [ ] Verificar biblioteca de imagenes.
- [ ] Abrir una lamina histologica.
- [ ] Probar un ROI o heatmap si corresponde.
- [ ] Probar chatbot/SCT si corresponde.

---

## 11. Resumen rapido

En el equipo origen:

```powershell
.\migrate_export.ps1 -BackupPath "E:\asofamech_migration"
```

Mover `E:\asofamech_migration` al equipo destino.

En el equipo destino:

```powershell
.\start_presentation.ps1 -BackupPath "E:\asofamech_migration"
```

Abrir:

```text
http://localhost:3000
```
