# Operacion de ASOFAMECH con dos equipos

Esta guia resume como usar el PC de escritorio como servidor principal mediante
Cloudflare Tunnel y el notebook como respaldo local durante la defensa.

## Que se sincroniza con Git

Un commit y `git push` solo transfieren archivos versionados.

| Viaja con Git | No viaja con Git |
|---|---|
| Backend, frontend y scripts | `.env` y secretos |
| Dockerfile y `docker-compose.yml` | Usuarios, historial y contenido de PostgreSQL |
| Migraciones Alembic | Volumen `asofamech_db_data` |
| Pruebas y documentacion | Modelos descargados de Ollama |
| Registro y checkpoint candidato Stage 17 | Cache autorizado de CONCH/HuggingFace |
| Configuracion reproducible | `backend/uploads/`, tiles DZI y archivos subidos |
| | `backend/artifacts/` y checkpoint productivo Stage 16 |
| | Laminas grandes en `backend/data/` |
| | Imagenes Docker construidas localmente |

Las migraciones Alembic actualizan la estructura de una base existente, pero no
copian sus registros. Docker Compose tampoco descarga los volumenes del otro
equipo.

## Rama y commit

Los dos equipos deben usar la misma rama y el mismo commit. Un commit publicado
en una rama `feat/...` no aparece al hacer pull desde `main`.

Comprobar en ambos:

```powershell
git branch --show-current
git rev-parse --short HEAD
git status --short
```

Antes de la defensa, lo mas simple es integrar la version final en `main` o
dejar anotado explicitamente el nombre de la rama que debe usar el notebook.

## Sincronizacion de datos

Elegir un equipo como fuente de verdad. Normalmente sera el PC de escritorio.

Despues de los ultimos cambios de usuarios, imagenes o contenido:

```powershell
.\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration"
```

En el notebook:

```powershell
.\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration"
```

Esto mueve la base, uploads, artifacts, laminas seleccionadas, Ollama e imagenes
Docker segun las opciones del backup. CONCH se incluye solo con autorizacion
explicita; de lo contrario se prepara en el notebook con:

```powershell
.\scripts\prepare_histopathology_model.ps1
```

No existe sincronizacion en vivo entre las dos bases. Si ambos equipos reciben
actividad, sus usuarios, historiales y resultados empezaran a divergir.

## Estrategia para la defensa

1. PC de escritorio: servidor principal y unico acceso para evaluadores.
2. Notebook: respaldo local conectado al proyector o listo para compartir.
3. No publicar ambos equipos simultaneamente con datos modificables.
4. Si falla Internet o Cloudflare, continuar en el notebook por
   `http://localhost:3000`.
5. Si falla el PC principal, cambiar al notebook; no intentar sincronizar bases
   durante la presentacion.

## Dia anterior

1. Hacer commit y push de todos los cambios necesarios.
2. Confirmar misma rama y commit en ambos equipos.
3. Generar un backup nuevo desde la fuente de verdad.
4. Restaurarlo en el notebook.
5. Verificar cuentas conocidas de administrador y estudiante.
6. Ejecutar en ambos:

```powershell
.\scripts\check_presentation_readiness.ps1 -CheckLlmGeneration
```

7. Probar Cloudflare desde un telefono usando datos moviles, no el mismo Wi-Fi.
8. Abrir chat, SCT, imagen DZI, ROI y heatmap.
9. Desactivar suspension automatica y conectar ambos equipos a corriente.
10. Confirmar que Windows Firewall permite a `cloudflared` realizar conexiones
    salientes. PostgreSQL, Ollama y la API quedan ligados solo a localhost.
11. Generar una respuesta de chat entre 5 y 10 minutos antes de comenzar. La
    primera carga de `llama3:8b` puede tardar bastante mas que las siguientes.

## Dia de la defensa

En el PC principal:

```powershell
.\abrir_publicador.cmd
```

Mantener abierta la ventana del publicador. La URL `*.trycloudflare.com` cambia
en cada sesion.

Cuando aparezca la URL:

```powershell
.\scripts\check_presentation_readiness.ps1 `
  -PublicUrl "https://URL-ACTUAL.trycloudflare.com" `
  -CheckLlmGeneration
```

El publicador deja `FRONTEND_API_BASE` vacio para que el navegador use `/api`
en el mismo origen, configura CORS y actualiza los enlaces de recuperacion de
contrasena con la URL publica.

## Verificaciones que no reemplaza un commit

- El archivo `.env` existe y tiene un secreto JWT propio.
- `APP_ENV=production` en el equipo que se publica.
- `llama3:8b` esta dentro del volumen Ollama.
- Histopatologia informa `model_ready=true`.
- El checkpoint Stage 16 existe en `backend/artifacts/`.
- CONCH esta preparado en el volumen HuggingFace.
- Las laminas y tiles usados en la demo existen localmente.
- La base contiene las cuentas y contenidos esperados.
