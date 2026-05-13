# Levantamiento tecnico-operativo para Capitulo IV

Fecha de revision: 2026-05-11  
Proyecto: ASOFAMECH / plataforma educativa medica  
Caracter: prototipo academico educativo, no diagnostico clinico.

## Resumen de estado real

| Area | Estado | Evidencia principal | Observacion |
|---|---|---|---|
| Frontend React/Vite | Implementado | `frontend/src/app.jsx`, `frontend/src/pages/*`, `frontend/src/components/*` | Build exitoso con `npm.cmd run build`; advertencia de bundle JS grande. |
| Backend FastAPI | Implementado/parcial | `backend/app/main.py`, `backend/app/routers/*` | API modular; crea tablas con SQLAlchemy al iniciar. |
| Base de datos PostgreSQL | Parcial | `backend/app/models.py`, `backend/app/db.py`, `docker-compose.yml` | Sin migraciones Alembic; algunas tablas no estan integradas al flujo. |
| Autenticacion y usuarios | Parcial | `AuthPage.jsx`, `AppSidebar.jsx`, `medical_images.py:get_current_user`, `heatmap_access.py` | Login y roles simulados con `localStorage`; backend usa usuario admin mock. Heatmaps aplican limites por rol mediante headers del prototipo, no auth real. |
| Chatbot educativo | Parcial | `ChatbotPage.jsx`, `backend/app/routers/chat.py` | Usa Ollama/LLaMA via API local; historial en navegador, no en DB. |
| RAG / contexto de casos | Parcial | `_build_cases_context` en `chat.py`, tabla `cases` | Busca coincidencias SQL en casos activos; no hay embeddings vectoriales ni carga automatica de `case*.json`. |
| SCT | Implementado/parcial | `SCTPage.jsx`, `ConfigPage.jsx`, `backend/app/routers/sct.py`, tabla `sct_tests` | Genera, resuelve, guarda, lista y elimina tests; no guarda intentos/respuestas por estudiante. |
| Imagenes histopatologicas | Implementado/parcial | `ImagesPage.jsx`, `ConfigPage.jsx`, `medical_images.py` | Carga, listado, importacion local CAMELYON17 y metadata en DB. |
| Visor histopatologico | Implementado/parcial | `OpenSeadragonViewer.jsx`, `MedicalImageViewer.jsx`, endpoints DZI | DZI/OpenSeadragon para deep zoom; Fabric para imagenes sin DZI. |
| ROI y patches | Implementado/parcial | `OpenSeadragonViewer.jsx`, `roi.py`, `patch_extractor.py` | ROI 1/ROI 2 en visor DZI con validacion y extraccion; anotaciones Fabric exportables localmente. |
| IA visual | Parcial/avanzado | `inference_service.py`, checkpoints en `backend/artifacts` | CONCH congelado + cabeza 3 clases; requiere checkpoint, token/cache HF y entorno GPU/CPU compatible. |
| Heatmap ROI | Implementado/parcial | `POST /api/histopathology/heatmaps/jobs`, `GET .../jobs/{job_id}`, `GET .../image/{id}/latest`, `GET .../image/{id}/history`, overlay en `OpenSeadragonViewer.jsx`, panel en `ConfigPage.jsx`, `heatmap_store.py`, `heatmap_jobs.py`, `heatmap_access.py` | Escaneo asincronico acotado a ROI con jobs en memoria, polling de progreso, persistencia en filesystem por `image_id` y `trace_id`, carga de ultimo mapa guardado, historial de mapas, preparacion docente/admin y rate limit por rol. No heatmap de lamina completa. |
| Pruebas | Parcial | `backend/tests/*` | `backend/.venv/Scripts/python.exe -m pytest tests -q`: 48 passed. |
| Docker | Parcial | `docker-compose.yml`, Dockerfiles | Compose incluye db/backend/ollama; no incluye servicio frontend. |

Verificaciones ejecutadas:

| Verificacion | Resultado |
|---|---|
| `backend/.venv/Scripts/python.exe -m pytest tests -q` | 48 passed tras agregar tests de historial, compatibilidad con `latest.json`, resumen compacto, rate limit por rol, `heatmap_store` y `heatmap_jobs` |
| `npm.cmd run build` en `frontend` | Build exitoso; advertencia de chunk JS > 500 kB |
| `git log --oneline -n 12` | Ultimo commit funcional revisado: `56d83a6 feat: optimiza heatmaps para concurrencia` |
| `git status --short` | Cambios en: limites por rol/rate limit de heatmaps, frontend y documentacion |

---

## 4.2.5. Informacion para diagrama de actividades

Actor principal: estudiante de Medicina.  
Inicio del flujo: acceso a la plataforma web y autenticacion simulada.  
Flujo principal recomendado: ingreso -> dashboard -> seleccion de modulo -> visor histopatologico / SCT / chatbot -> actividad educativa -> retroalimentacion o resultado educativo.  
Nota de alcance: el sistema debe modelarse como apoyo formativo, no como diagnostico.

| Paso | Responsable | Accion | Entrada | Salida | Estado actual | Evidencia sugerida |
|---|---|---|---|---|---|---|
| 1 | Estudiante | Ingresa a la plataforma | URL frontend | Landing o login | Implementado | Captura `/`, `frontend/src/app.jsx` |
| 2 | Frontend | Muestra login/registro | Email, password, nombre opcional | Usuario en `localStorage` | Parcial | `AuthPage.jsx`; aclarar login simulado |
| 3 | Frontend | Redirige al dashboard | Usuario local | Dashboard con modulos | Implementado/parcial | `/dashboard`, `DashboardPage.jsx`, `tracker.js` |
| 4 | Estudiante | Selecciona modulo de imagenes | Click en "Imagenes IA" | Biblioteca de imagenes | Implementado/parcial | `/dashboard/images`, `ImagesPage.jsx` |
| 5 | Frontend | Solicita biblioteca | GET `/api/medical-images/list` | Lista de imagenes | Implementado | Captura lista + endpoint |
| 6 | Backend | Consulta imagenes activas | Tabla `medical_images` | JSON de imagenes | Implementado/parcial | `medical_images.py`, tabla DB |
| 7 | Estudiante | Selecciona imagen | `image_id` | Visor DZI o Fabric | Implementado/parcial | Captura visor |
| 8 | Frontend | Carga DZI si `has_dzi=true` | `/api/medical-images/dzi/{id}.dzi` | OpenSeadragon con tiles | Implementado/parcial | `OpenSeadragonViewer.jsx`, `patient_017_node_2.dzi` |
| 9 | Backend | Sirve manifiesto/tile DZI | `image_id`, level, col, row | XML DZI o tile JPEG | Implementado | Endpoints DZI, carpeta `backend/uploads/dzi_tiles` |
| 10 | Estudiante | Define ROI 1 | Arrastre en visor | Coordenadas nivel 0 | Implementado/parcial | Captura ROI 1 |
| 11 | Estudiante | Define ROI 2 dentro de ROI 1 | Arrastre en visor | ROI 2 valida o error | Implementado/parcial | Captura ROI 2; `roi.py` |
| 12 | Frontend | Valida contencion y tamano basico | ROI 1/ROI 2 | Boton analizar habilitado o error | Implementado/parcial | `OpenSeadragonViewer.jsx` |
| 13 | Frontend | Consulta estado del modelo | GET `/api/histopathology/status` | `model_ready`, metadata | Implementado | Captura panel modelo |
| 14 | Estudiante | Ejecuta analisis ROI 2 | `image_id`, ROI 1, ROI 2 | Solicitud backend | Implementado/parcial | POST `/api/histopathology/analyze-roi` |
| 15 | Backend | Valida imagen y ROI | DB + coordenadas | Error 400/404/422 o patch | Implementado | `histopathology.py`, `validate_roi_pair` |
| 16 | Backend | Extrae patch ROI 2 | WSI/raster + ROI 2 | Imagen RGB | Implementado | `patch_extractor.py`, debug patches |
| 17 | Modulo IA visual | Evalua calidad ROI | Patch RGB | `evaluable` o `roi_no_evaluable` | Implementado/parcial | `roi_quality.py`, tests |
| 18 | Modulo IA visual | Clasifica patch | Patch evaluable | Clase/probabilidades/umbral | Parcial/avanzado | `inference_service.py`, checkpoint Stage 6 |
| 19 | Backend | Registra auditoria | Resultado + trace | JSONL audit log | Implementado | `backend/artifacts/histopathology/audit_log.jsonl` |
| 20 | Frontend | Muestra resultado educativo | Payload IA | Clase, confianza, QC, warning | Implementado/parcial | Captura resultado ROI |
| 21 | Estudiante | Solicita mapa ROI 1 (acotado) | ROI 1, tile_size (512/1024) | Job asincronico creado (`job_id`) | Implementado/parcial | POST `/api/histopathology/heatmaps/jobs`; selector de tile_size en UI |
| 21a | Frontend | Hace polling de progreso del job | `job_id` | Estado: en cola / procesando / completado / fallido; tiles procesados/total | Implementado/parcial | GET `/api/histopathology/heatmaps/jobs/{job_id}`; barra de progreso en visor |
| 21b | Estudiante (opcional) | Carga ultimo mapa guardado | `image_id` | Heatmap previo recuperado | Implementado/parcial | GET `/api/histopathology/heatmaps/image/{id}/latest`; boton "Cargar ultimo mapa" |
| 22 | Backend/IA | Divide ROI en tiles, clasifica y persiste | ROI, tile_size, stride, max_tiles | Tiles con `tumor_score`; heatmap guardado en filesystem | Implementado/parcial | `heatmap_jobs.py`, `heatmap_store.py`; archivos en `artifacts/histopathology/heatmaps/` |
| 23 | Estudiante | Consulta chatbot | Pregunta texto | Respuesta educativa | Parcial | `/dashboard/chat`, `POST /api/chat` |
| 24 | Backend/RAG/LLM | Busca casos y llama Ollama | Pregunta + tabla `cases` | Mensaje IA | Parcial | `chat.py`, logs Ollama |
| 25 | Estudiante | Genera/resuelve SCT | Numero, dificultad, enfoque | Test y resultado | Implementado/parcial | `/dashboard/sct`, `sct.py` |

Flujos alternativos y excepciones:

| Situacion | Responsable | Comportamiento actual | Estado | Evidencia |
|---|---|---|---|---|
| ROI 2 fuera de ROI 1 | Frontend/backend | Frontend muestra error; backend tambien rechaza con `ValueError`/400 | Implementado | `roiContains`, `validate_roi_pair`, tests |
| ROI 2 fuera de lamina | Backend | Retorna 400 por limites de lamina | Implementado | `validate_roi_bounds` |
| ROI 2 menor/mayor al rango | Frontend/backend | Frontend bloquea; backend exige 32-4096 px | Implementado | `ROI2_MIN_SIZE`, `ROI2_MAX_SIZE`, `roi.py` |
| ROI no evaluable | IA visual/backend | Retorna `roi_no_evaluable`, motivo y recomendacion | Implementado/parcial | `roi_quality.py`, audit log |
| Modelo no disponible | Backend/frontend | `/status` indica `model_ready=false`; analizar queda deshabilitado o retorna 503 | Implementado/parcial | `histopathology_status`, UI modelo |
| Imagen no carga | Frontend/backend | OpenSeadragon `open-failed`; backend 404 si no existe DZI/archivo | Implementado/parcial | `OpenSeadragonViewer.jsx`, `medical_images.py` |
| Chatbot no responde | Backend/frontend | Backend 502/503 por Ollama; frontend muestra error generico | Parcial | `chat.py`, `ChatbotPage.jsx` |
| SCT IA no genera JSON valido | Backend | Error 500 por parseo JSON; UI alerta error | Parcial | `sct.py`, `SCTPage.jsx` |

Legibilidad del diagrama: conviene dividirlo en 3 imagenes:

1. Flujo base del estudiante: login simulado, dashboard, seleccion de modulo.
2. Flujo histopatologico: biblioteca, visor, ROI 1/ROI 2, analisis IA, heatmap ROI.
3. Flujos IA educativa: chatbot RAG/LLM y SCT.

---

## 4.2.6. Informacion para BPMN del proceso formativo

Pools recomendados:

| Pool | Rol |
|---|---|
| Estudiante de Medicina | Realiza actividades formativas e interpreta resultados educativos. |
| Plataforma Web ASOFAMECH | UI React, navegacion, estado local, validaciones cliente. |
| Backend FastAPI | API, persistencia, filesystem, extraccion de patches, orquestacion IA. |
| Servicios IA/RAG | Ollama/LLaMA para chat/SCT y CONCH + clasificador para ROI. |
| Base de datos / almacenamiento | PostgreSQL, uploads, DZI, artifacts/audit logs. |

Lanes recomendadas:

| Pool | Lanes |
|---|---|
| Estudiante | Acceso, actividad histopatologica, actividad SCT, consulta chatbot |
| Plataforma Web | Autenticacion local, dashboard, visor, UI SCT, UI chatbot |
| Backend FastAPI | Imagenes, histopatologia, SCT, chat/casos |
| Servicios IA/RAG | LLM texto, IA visual CONCH, control calidad ROI |
| Base/almacenamiento | PostgreSQL, filesystem uploads, artifacts |

| Elemento BPMN | Nombre sugerido | Responsable / Pool | Descripcion | Tipo de flujo | Estado actual |
|---|---|---|---|---|---|
| Evento inicio | Acceso del estudiante | Estudiante | Abre plataforma web | Secuencia | Implementado |
| Tarea usuario | Iniciar sesion | Estudiante | Ingresa credenciales | Secuencia | Parcial/simulado |
| Tarea servicio | Registrar sesion local | Plataforma Web | Guarda usuario en `localStorage` | Secuencia | Parcial |
| Gateway | Usuario local existe? | Plataforma Web | Redirige a dashboard o auth | Secuencia | Implementado/parcial |
| Tarea usuario | Seleccionar actividad | Estudiante | Chatbot, SCT o imagenes | Secuencia | Implementado |
| Tarea usuario | Seleccionar imagen | Estudiante | Escoge lamina/imagen | Secuencia | Implementado/parcial |
| Flujo mensaje | Solicitar lista imagenes | Web -> Backend | GET `/api/medical-images/list` | Mensaje | Implementado |
| Tarea servicio | Consultar metadata imagenes | Backend -> BD | Lee `medical_images` | Mensaje | Implementado |
| Flujo mensaje | Retornar biblioteca | Backend -> Web | JSON imagenes | Mensaje | Implementado |
| Tarea usuario | Delimitar ROI 1 y ROI 2 | Estudiante/Web | Coordenadas en visor | Secuencia | Implementado/parcial |
| Gateway | ROI 2 contenida y valida? | Web/Backend | Valida contencion, tamano y limites | Secuencia | Implementado |
| Flujo mensaje | Analizar ROI | Web -> Backend | POST `/api/histopathology/analyze-roi` | Mensaje | Implementado/parcial |
| Tarea servicio | Extraer patch | Backend | OpenSlide/PIL extrae ROI 2 | Secuencia | Implementado |
| Flujo mensaje | Solicitar inferencia visual | Backend -> IA visual | Patch RGB | Mensaje | Implementado/parcial |
| Gateway | ROI evaluable? | IA visual | QC de fondo, tejido, nucleos, estroma | Secuencia | Implementado |
| Tarea servicio | Clasificar patch | IA visual | CONCH + cabeza 3 clases | Secuencia | Parcial/avanzado |
| Tarea servicio | Registrar auditoria | Backend -> almacenamiento | JSONL por `trace_id` | Mensaje | Implementado |
| Flujo mensaje | Resultado educativo ROI | Backend -> Web | Clase, confianza, QC, warning | Mensaje | Implementado |
| Tarea usuario | Interpretar retroalimentacion | Estudiante | Lee resultado no diagnostico | Secuencia | Implementado/parcial |
| Tarea usuario | Generar test SCT | Estudiante | Define parametros | Secuencia | Implementado/parcial |
| Flujo mensaje | Generar items SCT | Web -> Backend -> LLM | POST `/api/sct/generate` | Mensaje | Implementado/parcial |
| Tarea servicio | Guardar test | Backend -> BD | Inserta `sct_tests` | Mensaje | Implementado |
| Tarea usuario | Responder SCT | Estudiante/Web | Escala -2 a +2 | Secuencia | Implementado local |
| Tarea usuario | Consultar chatbot | Estudiante | Pregunta texto | Secuencia | Parcial |
| Flujo mensaje | Pregunta chatbot | Web -> Backend | POST `/api/chat` | Mensaje | Implementado |
| Tarea servicio | Recuperar casos | Backend -> BD | Busca en `cases` | Mensaje | Parcial |
| Flujo mensaje | Solicitar respuesta LLM | Backend -> Ollama | Prompt educativo + contexto | Mensaje | Parcial |
| Evento intermedio error | Imagen/ROI/modelo/chat falla | Web/Backend/IA | Error visible o respuesta HTTP | Excepcion | Parcial |
| Evento fin | Actividad formativa finalizada | Estudiante | Resultado, respuesta o feedback mostrado | Secuencia | Implementado/parcial |

Estructura BPMN sugerida: mantener 4 pools maximo en la lamina principal: Estudiante, Plataforma Web, Backend FastAPI, Servicios externos/almacenamiento. Usar flujos de secuencia solo dentro de cada pool y flujos de mensaje entre pools. Los detalles de CONCH, DZI y RAG pueden modelarse como subprocesos colapsados.

---

## 4.3.2. Product Backlog del proyecto

| ID | Epica / modulo | Historia o tarea | Prioridad | Estado | Dependencias | Criterio de aceptacion | Evidencia esperada |
|---|---|---|---|---|---|---|---|
| PB-01 | Autenticacion y usuarios | Login/registro frontend | Alta | Parcial | React Router, localStorage | Usuario entra al dashboard | `AuthPage.jsx` |
| PB-02 | Autenticacion y usuarios | Autenticacion backend real con hash/JWT | Alta | Pendiente | Usuarios DB, seguridad | Token y roles validados en API | Endpoints auth, pruebas |
| PB-03 | Autenticacion y usuarios | Control de roles real docente/admin | Alta | Pendiente | Auth backend | Acciones admin protegidas | Tests 401/403 |
| PB-04 | Gestion academica | Dashboard con metricas locales | Media | Implementado | tracker.js | Muestra consultas, tiempo y SCT | Captura dashboard |
| PB-05 | Gestion academica | Persistir metricas por estudiante en DB | Media | Pendiente | Auth, tablas academicas | Historial centralizado | Tablas intentos/logs |
| PB-06 | Gestion academica | Panel admin para imagenes/SCT | Alta | Parcial | ConfigPage, endpoints | Admin lista/sube/elimina recursos | Captura config |
| PB-07 | Casos educativos | Modelo y endpoints de casos | Media | Implementado | DB | Crear/listar/buscar casos | `/api/cases` |
| PB-08 | Casos educativos | Carga automatica de `case1-3.json` | Media | Pendiente | Script seed | Casos disponibles tras levantar DB | Script/log seed |
| PB-09 | Imagenes histopatologicas | Subida de JPG/PNG/TIFF/SVS | Alta | Implementado/parcial | Uploads, DB, OpenSlide | Archivo y metadata guardados | `/upload`, carpeta uploads |
| PB-10 | Imagenes histopatologicas | Importacion local CAMELYON17 | Media | Implementado/parcial | Data local | Lamina local registrada sin subir GB | `/local/camelyon17`, `/import-local` |
| PB-11 | Imagenes histopatologicas | Borrado seguro y soft-delete consistente | Media | Parcial | DB/filesystem | Recurso eliminado sin huerfanos | DELETE + DB |
| PB-12 | Visor histopatologico | Visor OpenSeadragon DZI | Alta | Implementado/parcial | DZI endpoints | Lamina navegable con zoom | Captura visor |
| PB-13 | Visor histopatologico | Visor Fabric para raster sin DZI | Media | Implementado/parcial | Fabric | Imagen con zoom/anotaciones | `MedicalImageViewer.jsx` |
| PB-14 | Visor histopatologico | Generacion DZI dinamica para WSI | Alta | Implementado/parcial | OpenSlide | Manifiesto y tiles bajo demanda | `patient_017_node_2.dzi` |
| PB-15 | Seleccion ROI | ROI 1 y ROI 2 en visor DZI | Alta | Implementado/parcial | OpenSeadragon | Coordenadas nivel 0 correctas | `OpenSeadragonViewer.jsx` |
| PB-16 | Seleccion ROI | Validacion geometrica ROI | Alta | Implementado | `roi.py` | ROI 2 dentro de ROI 1 y lamina | Tests ROI |
| PB-17 | Seleccion ROI | Persistencia de ROI en DB | Alta | Pendiente | Tabla ROI, auth | ROI recuperable por usuario/imagen | Endpoint + tabla |
| PB-18 | Procesamiento patches | Extraccion ROI 2 con OpenSlide/PIL | Alta | Implementado | `patch_extractor.py` | Patch RGB generado | Debug patch |
| PB-19 | Procesamiento patches | Guardado de artefactos debug | Media | Implementado | artifacts | Patch original/preprocesado por trace | `debug_patches` |
| PB-20 | IA visual | Servicio CONCH + cabeza 3 clases | Alta | Parcial/avanzado | PyTorch, CONCH, checkpoint | `/status` listo y predice ROI | Checkpoint + audit log |
| PB-21 | IA visual | Control de calidad ROI | Alta | Implementado/parcial | PIL/QC | Rechaza fondo/estroma/baja celularidad | Tests QC |
| PB-22 | IA visual | Validacion clinica formal | Alta | Pendiente | Dataset validado, expertos | Metricas externas defendibles | Informe validacion |
| PB-23 | IA visual | Heatmap ROI 1 asincronico acotado | Media | Implementado/parcial | heatmap_jobs, heatmap_store, heatmap_access, visor, ConfigPage | Jobs async, barra progreso, tiles coloreados, persistencia filesystem, carga de ultimo mapa, historial por imagen, preparacion admin acotada, limites por rol | Overlay visor; panel config; archivos en artifacts/ |
| PB-24 | IA visual | Heatmap lamina completa (precalculo admin) | Media | Pendiente/parcial | GPU, cola persistente, cache, auth admin | Panel admin acotado ya permite preparar regiones; falta lamina completa analizada en background para que estudiantes consuman resultado | Endpoints tarea larga; cola durable; auth real |
| PB-25 | RAG / LLM | Chat educativo con Ollama | Alta | Parcial | Ollama, LLaMA | Responde pregunta en espanol con aviso | `/api/chat` |
| PB-26 | RAG / LLM | RAG SQL por casos | Media | Parcial | Tabla cases | Incluye max. 3 casos relevantes | `chat.py` |
| PB-27 | RAG / LLM | RAG vectorial/documental | Media | Pendiente | Embeddings, vector DB | Recuperacion semantica trazable | Indice/vector store |
| PB-28 | Chatbot educativo | UI de conversaciones | Alta | Implementado/parcial | localStorage | Historial local, guardar/eliminar | `ChatbotPage.jsx` |
| PB-29 | Chatbot educativo | Persistir `ChatLog` | Media | Pendiente | Auth/DB | Preguntas/respuestas auditables | Tabla `chat_logs` usada |
| PB-30 | Chatbot educativo | Sanitizacion markdown IA | Alta | Pendiente | DOMPurify u otro | Mitigar XSS | Test seguridad |
| PB-31 | SCT | Generar items IA | Alta | Implementado/parcial | Ollama | JSON con items SCT | `/api/sct/generate` |
| PB-32 | SCT | Resolver y puntuar test | Alta | Implementado local | Frontend | Feedback y puntaje | Captura resultados |
| PB-33 | SCT | Guardar/listar/obtener/eliminar tests | Alta | Implementado | DB | CRUD SCT funcional | `sct_tests` |
| PB-34 | SCT | Registrar intentos por estudiante | Alta | Pendiente | Auth, nuevas tablas | Historial academico centralizado | `sct_attempts` |
| PB-35 | Base de datos | Modelos SQLAlchemy | Alta | Implementado/parcial | PostgreSQL | Tablas creadas al startup | `models.py` |
| PB-36 | Base de datos | Migraciones Alembic | Media | Pendiente | SQLAlchemy | Cambios versionados | Carpeta migrations |
| PB-37 | Backend / API | Routers modulares | Alta | Implementado | FastAPI | Rutas activas en `/docs` | `main.py`, `routers/*` |
| PB-38 | Backend / API | Healthchecks de IA/DB | Media | Parcial | `/health`, `/status` | Estado observable | `/health`, `/status` |
| PB-39 | Frontend / interfaz | Rutas principales y sidebar | Alta | Implementado | React Router | Navegacion estable | `app.jsx`, `AppSidebar.jsx` |
| PB-40 | Frontend / interfaz | Usar `VITE_API_BASE` en imagenes/config | Media | Pendiente | api.js | Sin URLs hardcodeadas | Refactor fetch |
| PB-41 | Pruebas y validacion | Tests ROI/QC/auditoria | Media | Implementado | pytest | 8 tests pasan | `backend/tests/*` |
| PB-42 | Pruebas y validacion | Tests API chat/SCT/imagenes | Alta | Pendiente | pytest/TestClient | Contratos verificados | Suite API |
| PB-43 | Pruebas y validacion | E2E frontend | Media | Pendiente | Playwright/Cypress | Login, SCT, chat, visor | Reporte E2E |
| PB-44 | Documentacion | Docs tecnicas histopatologia/SCT/DB | Alta | Implementado/parcial | `docs/` | Evidencia reproducible | Markdown docs |
| PB-45 | Documentacion | Actualizar OpenAPI exportado | Media | Pendiente | FastAPI real | `openapi_temp.json` vigente | OpenAPI actual |

---

## 4.3.3. Tablero Kanban e iteraciones

### Tabla A. Estructura del tablero Kanban

| Columna | Descripcion | Ejemplos de tareas |
|---|---|---|
| Backlog | Alcance proyectado aun no iniciado | Auth real, persistir ROI, intentos SCT, heatmap completo |
| Por hacer | Tareas priorizadas proximas | Seed de casos, sanitizar chat, tests API |
| En desarrollo | Cambios activos o no confirmados | Documentacion academica, capturas y validacion externa |
| En revision | Requiere prueba/captura/documentacion | Build frontend, tests ROI/QC, status modelo |
| Hecho | Funcionalidad implementada y verificable | Routers FastAPI, CRUD SCT, visor DZI, tests ROI |
| Bloqueado | Depende de recursos externos | Token CONCH/HF, GPU, dataset WSI, validacion experta |

### Tabla B. Iteraciones del proyecto

| Iteracion | Objetivo | Tareas principales | Resultado obtenido | Estado | Evidencia sugerida |
|---|---|---|---|---|---|
| I1 | Base chatbot educativa | FastAPI, React inicial, Ollama, casos TB | Chat educativo funcional parcial | Implementado/parcial | `chat.py`, `ChatbotPage.jsx`, README |
| I2 | Persistencia y casos | PostgreSQL, SQLAlchemy, casos, SCTTest | Tablas y endpoints basicos | Implementado/parcial | `models.py`, `cases.py`, `sct.py` |
| I3 | Modulo SCT | Generacion IA, resolucion, guardado | SCT funcional y administrable | Implementado/parcial | `/dashboard/sct`, `/api/sct/*` |
| I4 | Redisenio frontend | Dashboard, sidebar, pages nuevas | Navegacion y UI principal | Implementado | Commit `f5b21b7`, `app.jsx` |
| I5 | Imagenes medicas | Upload/listado/visor Fabric/DZI | Biblioteca y visor parcial | Implementado/parcial | `medical_images.py`, `ImagesPage.jsx` |
| I6 | ROI histopatologica | ROI 1/ROI 2, extraccion patch, validaciones | Analisis ROI backend/frontend | Implementado/parcial | `OpenSeadragonViewer.jsx`, tests ROI |
| I7 | IA visual CONCH | CONCH, checkpoints, QC, auditoria | Clasificador educativo ROI 3 clases | Parcial/avanzado | artifacts, audit log, `/status` |
| I8 | Heatmap ROI asincronico | Jobs async (`heatmap_jobs.py`), persistencia (`heatmap_store.py`), historial por imagen, limites por rol (`heatmap_access.py`), polling frontend, barra progreso, selector tile_size, boton "Cargar ultimo mapa", mejor tile como ROI 2, panel admin en configuracion para precalculo acotado | Heatmap acotado a ROI con progreso, persistencia, historial, rate limit y preparacion docente | Implementado/parcial | audit log scan, overlay, panel config, artifacts/histopathology/heatmaps/ |
| I9 | Documentacion/defensa | Docs histopatologia, roadmap, DB | Material para informe | Parcial | `docs/*` |

Bloqueos tecnicos detectados:

| Bloqueo | Impacto | Estado |
|---|---|---|
| Auth real ausente | Roles y permisos no defendibles como seguridad | Pendiente |
| Dependencia Ollama/modelo | Chat/SCT fallan si Ollama no esta activo | Parcial |
| Token/cache CONCH | IA visual puede no iniciar si checkpoint no esta disponible | Bloqueado externo/parcial |
| WSI grandes | Subida/procesamiento requiere OpenSlide, disco y tiempo | Parcial |
| Sin migraciones | Riesgo al modificar esquema | Pendiente |
| Sin persistencia ROI/intentos | Gestion academica y trazabilidad incompletas | Pendiente |

### Tabla C. Estado actual de tareas

| Tarea | Modulo | Estado actual | Evidencia disponible | Observacion |
|---|---|---|---|---|
| Rutas React | Frontend | Implementado | `app.jsx` | Landing, auth, dashboard, chat, SCT, images, config |
| Dashboard | Gestion academica | Parcial | `DashboardPage.jsx`, `tracker.js` | Metricas locales |
| Login | Auth | Parcial | `AuthPage.jsx` | No backend/JWT |
| Chat | Chatbot/RAG | Parcial | `chat.py`, `ChatbotPage.jsx` | RAG SQL simple |
| SCT CRUD | SCT | Implementado | `/api/sct/*`, `sct_tests` | Sin intentos por estudiante |
| Biblioteca imagenes | Imagenes | Implementado/parcial | `/api/medical-images/list` | Requiere DB con datos |
| DZI | Visor | Implementado/parcial | `.dzi`, endpoints tiles | WSI dinamico |
| ROI 1/2 | ROI | Implementado/parcial | `OpenSeadragonViewer.jsx`, `roi.py` | No persistencia formal |
| Patch extraction | Patches | Implementado | `patch_extractor.py` | OpenSlide/PIL |
| QC ROI | IA visual | Implementado | `roi_quality.py`, tests | Heuristico |
| CONCH classifier | IA visual | Parcial/avanzado | checkpoint Stage 6, audit log | No validacion clinica final |
| Heatmap ROI 1 | IA visual | Implementado/parcial | Jobs async, polling, overlay, mejor tile, persistencia filesystem, panel admin acotado | Acotado a ROI; no heatmap lamina completa; jobs en memoria (no sobreviven reinicio) |
| Pruebas | Validacion | Parcial | 8 passed | Solo histopatologia basica |

---

## 4.3.4 a 4.3.11. Implementacion de componentes

### Tabla resumen

| Modulo | Tecnologia principal | Funcionalidades implementadas | Estado actual | Evidencia disponible | Limitaciones |
|---|---|---|---|---|---|
| Frontend | React 18 + Vite | Rutas, dashboard, chatbot, SCT, imagenes, config | Implementado/parcial | Build exitoso, `frontend/src` | Auth local, URLs hardcodeadas en imagenes/config |
| Backend | FastAPI + SQLAlchemy | Routers chat, casos, SCT, imagenes, histopatologia | Implementado/parcial | `/health`, routers | Sin auth real, sin migraciones |
| Base de datos | PostgreSQL 15 | Usuarios, imagenes, casos, docs, chat logs, SCT tests | Parcial | `models.py` | `documents`/`chat_logs` no usados, sin Alembic |
| Visor histopatologico | OpenSeadragon + Fabric | DZI, tiles, zoom, visor raster | Implementado/parcial | `OpenSeadragonViewer.jsx`, `MedicalImageViewer.jsx` | Persistencia de anotaciones incompleta |
| Seleccion ROI | OpenSeadragon overlay + FastAPI | ROI 1/2, validacion, extraccion patch | Implementado/parcial | `roi.py`, tests | ROI no se guarda en DB |
| SCT | FastAPI + Ollama + React | Generar, resolver, guardar/listar/eliminar | Implementado/parcial | `sct.py`, `SCTPage.jsx` | Sin intentos/respuestas por estudiante |
| Chatbot educativo | React + FastAPI + Ollama | Conversaciones locales, prompt educativo, RAG SQL | Parcial | `chat.py`, `ChatbotPage.jsx` | Sin logs DB, sin RAG vectorial/sanitizacion |
| IA/RAG | Ollama + CONCH + PyTorch | Chat/SCT LLM; clasificador ROI 3 clases; QC | Parcial/avanzado | `inference_service.py`, artifacts | No diagnostico, dependencias externas, validacion limitada |

### 4.3.4. Implementacion del frontend

| Campo | Descripcion |
|---|---|
| Objetivo | Proveer interfaz educativa para estudiantes/docentes: dashboard, chatbot, SCT, imagenes, configuracion. |
| Tecnologias | React 18, Vite, React Router, OpenSeadragon, Fabric, CSS global. |
| Archivos | `frontend/src/app.jsx`, `main.jsx`, `api.js`, `pages/*`, `components/*`, `styles.css`. |
| Funcionalidades implementadas | Landing, auth simulada, dashboard, sidebar, chat UI, SCT UI, biblioteca/visor, panel config. |
| Parciales | Acceso por rol local, metricas localStorage, historial chat local, llamadas imagenes hardcodeadas. |
| Pendientes | Auth real, API client centralizado para imagenes/casos, tests frontend, sanitizacion robusta. |
| Endpoints relacionados | `/api/chat`, `/api/sct/*`, `/api/medical-images/*`, `/api/histopathology/*`. |
| Flujo de datos | UI -> fetch HTTP -> FastAPI -> DB/IA/filesystem -> JSON -> UI. |
| Estado | Implementado/parcial. |
| Evidencias | Capturas de rutas; build exitoso; `app.jsx`; bundle `dist`. |
| Limitaciones | Sin persistencia academica centralizada; no E2E; bundle grande. |

### 4.3.5. Implementacion del backend

| Campo | Descripcion |
|---|---|
| Objetivo | Exponer API REST para modulos educativos, IA, imagenes y persistencia. |
| Tecnologias | FastAPI, SQLAlchemy, Pydantic, httpx, OpenSlide, Pillow, PyTorch opcional. |
| Archivos | `backend/app/main.py`, `routers/*`, `histopathology/*`, `db.py`, `models.py`. |
| Funcionalidades implementadas | Health, CORS, creacion tablas, routers chat/casos/SCT/imagenes/histopatologia, static uploads. |
| Parciales | Permisos mock, errores basicos, servicios mezclados en routers. |
| Pendientes | Auth/JWT, migraciones, jobs asincronicos, rate limit, tests API. |
| Estado | Implementado/parcial. |
| Evidencias | FastAPI `/docs`, endpoints, logs Uvicorn, tests pytest. |

### 4.3.6. Implementacion de la base de datos

| Campo | Descripcion |
|---|---|
| Objetivo | Persistir entidades del prototipo: usuarios, imagenes, casos, documentos, chat logs y tests SCT. |
| Tecnologias | PostgreSQL 15, SQLAlchemy ORM, psycopg2. |
| Archivos | `backend/app/models.py`, `backend/app/db.py`, `docker-compose.yml`. |
| Funcionalidades implementadas | Modelos y relaciones `User` -> `MedicalImage`; `SCTTest` con JSON; `Case` para RAG SQL. |
| Parciales | `Document` y `ChatLog` existen pero no se usan activamente. |
| Pendientes | Alembic, seed de casos, tablas ROI, intentos SCT, logs chat reales. |
| Estado | Parcial. |
| Evidencias | Captura `psql \dt`, modelo SQLAlchemy, informe DB. |

### 4.3.7. Implementacion del visor histopatologico

| Campo | Descripcion |
|---|---|
| Objetivo | Visualizar imagenes histopatologicas con zoom y soporte para WSI/DZI. |
| Tecnologias | OpenSeadragon, Fabric, OpenSlide, Deep Zoom Image, Pillow. |
| Archivos | `OpenSeadragonViewer.jsx`, `MedicalImageViewer.jsx`, `medical_images.py`. |
| Implementado | DZI manifest/tile endpoints, visor OSD, zoom/pan, carga raster, DZI dinamico WSI. |
| Parcial | Generacion/servicio DZI depende de OpenSlide; Fabric exporta anotaciones localmente. |
| Pendiente | Cache robusta, colas para procesamiento, persistir anotaciones/ROI. |
| Estado | Implementado/parcial. |
| Evidencias | Captura visor, `patient_017_node_2.dzi`, endpoints DZI. |

### 4.3.8. Implementacion de seleccion de ROI

| Campo | Descripcion |
|---|---|
| Objetivo | Permitir seleccionar regiones de interes y enviar ROI 2 a analisis educativo. |
| Tecnologias | Overlay React sobre OpenSeadragon, Pydantic, OpenSlide/PIL. |
| Archivos | `OpenSeadragonViewer.jsx`, `histopathology/schemas.py`, `roi.py`, `patch_extractor.py`. |
| Implementado | ROI 1, ROI 2, contencion, limites, tamano min/max, conversion coordenadas visor-imagen. |
| Parcial | Anotaciones Fabric separadas; ROI no se guarda en DB. |
| Pendiente | Modelo `regions_of_interest`, CRUD ROI, reapertura de ROI guardadas. |
| Estado | Implementado/parcial. |
| Evidencias | Captura ROI, tests `test_histopathology_roi.py`, audit log. |

### 4.3.9. Implementacion del modulo SCT

| Campo | Descripcion |
|---|---|
| Objetivo | Evaluar razonamiento clinico mediante Script Concordance Test. |
| Tecnologias | React, FastAPI, Pydantic, Ollama/LLaMA 3, PostgreSQL JSON. |
| Archivos | `SCTPage.jsx`, `ConfigPage.jsx`, `backend/app/routers/sct.py`, `schemas.py`. |
| Implementado | Generacion IA, ejemplo estatico, guardar/listar/obtener/eliminar tests, resolver y feedback local. |
| Parcial | Calidad depende de JSON LLM; puntaje local; no hay respuestas por estudiante en DB. |
| Pendiente | Intentos, respuestas, estadisticas, comparacion con panel experto, exportacion academica. |
| Estado | Implementado/parcial. |
| Evidencias | Capturas SCT, endpoints `/api/sct/*`, tabla `sct_tests`. |

### 4.3.10. Implementacion del chatbot educativo

| Campo | Descripcion |
|---|---|
| Objetivo | Responder consultas educativas medicas con advertencia no diagnostica. |
| Tecnologias | React, FastAPI, httpx, Ollama/LLaMA 3, SQLAlchemy. |
| Archivos | `ChatbotPage.jsx`, `backend/app/routers/chat.py`, `api.js`. |
| Implementado | Conversaciones locales, envio de preguntas, respuesta LLM, prompt educativo, RAG SQL simple por casos. |
| Parcial | Historial solo local, `ChatLog` no usado, RAG no vectorial. |
| Pendiente | Persistencia consentida, sanitizacion DOMPurify, fuentes/citas, moderacion, healthcheck Ollama visible. |
| Estado | Parcial. |
| Evidencias | Captura chat, endpoint `/api/chat`, logs backend/Ollama. |

### 4.3.11. Implementacion de servicios de IA / RAG

| Campo | Descripcion |
|---|---|
| Objetivo | Apoyar actividades educativas con LLM texto y clasificacion visual exploratoria. |
| Tecnologias | Ollama/LLaMA 3, CONCH, PyTorch, linear head 3-class, OpenSlide/PIL. |
| Archivos | `chat.py`, `sct.py`, `histopathology/ml/*`, `histopathology_offline/*`, `docs/HISTOPATHOLOGY_AI.md`. |
| Implementado | LLM chat/SCT; CONCH frozen; checkpoint 3 clases; QC ROI; auditoria; debug patches; metrics artifacts. |
| Parcial | RAG SQL simple; IA visual limitada a patches ganglio/CAMELYON/PCam/SLN-Breast; depende de entorno. |
| Pendiente | RAG vectorial, validacion formal, MIL/CLAM lamina completa, heatmap asincronico persistente. |
| Estado | Parcial/avanzado. |
| Evidencias | `/api/histopathology/status`, audit log, reports, checkpoints, docs histopathology. |

---

## 6. Endpoints y base de datos

### Endpoints

| Metodo | Endpoint | Descripcion | Entrada esperada | Salida esperada | Estado | Modulo asociado |
|---|---|---|---|---|---|---|
| GET | `/health` | Estado backend | - | `{status:"ok"}` | Implementado | Backend |
| POST | `/api/chat` | Consulta chatbot | `{text}` | `{messages:[{text}]}` | Parcial | Chat/RAG |
| GET | `/api/cases` | Lista casos | - | Lista casos | Implementado | Casos |
| POST | `/api/cases` | Crea caso | title, description, body | Caso creado | Implementado API | Casos |
| GET | `/api/cases/search?q=&limit=` | Busca casos | Query params | Lista casos | Implementado | Casos/RAG |
| POST | `/api/sct/generate` | Genera SCT con IA | `num_items`, `difficulty`, `focus` | Items SCT | Parcial | SCT/LLM |
| GET | `/api/sct/example` | SCT estatico | - | Items ejemplo | Implementado | SCT |
| POST | `/api/sct/save` | Guarda test SCT | name, difficulty, focus, items | Test guardado | Implementado | SCT |
| GET | `/api/sct/list` | Lista SCT | - | Tests activos | Implementado | SCT |
| GET | `/api/sct/{test_id}` | Detalle SCT | test_id | Test + items | Implementado | SCT |
| DELETE | `/api/sct/{test_id}` | Soft-delete SCT | test_id | Mensaje | Implementado | SCT |
| POST | `/api/medical-images/upload` | Sube imagen | Multipart file + metadata | Metadata + has_dzi | Implementado/parcial | Imagenes |
| GET | `/api/medical-images/local/camelyon17` | Lista WSI locales | - | Laminas locales | Implementado/parcial | Imagenes |
| POST | `/api/medical-images/import-local/camelyon17` | Importa WSI local | form filename/title | Imagen registrada | Implementado/parcial | Imagenes |
| GET | `/api/medical-images/list` | Lista imagenes | - | Imagenes activas | Implementado | Imagenes |
| GET | `/api/medical-images/view/{image_id}` | Visualiza/preview | image_id | Archivo/stream | Implementado/parcial | Visor |
| GET | `/api/medical-images/download/{image_id}` | Descarga imagen | image_id | Archivo | Implementado | Imagenes |
| DELETE | `/api/medical-images/{image_id}` | Elimina imagen | image_id | Mensaje | Parcial | Imagenes |
| GET | `/api/medical-images/dzi/{image_id}.dzi` | DZI manifest | image_id | XML DZI | Implementado | Visor |
| GET | `/api/medical-images/dzi/{image_id}_files/{level}/{col}_{row}.{fmt}` | Tile DZI | coords tile | Imagen tile | Implementado | Visor |
| GET | `/api/medical-images/info/{image_id}` | Detalle imagen | image_id | Metadata | Implementado | Imagenes |
| GET | `/api/histopathology/status` | Estado IA visual | - | Model metadata/listo | Implementado/parcial | IA visual |
| POST | `/api/histopathology/analyze-roi` | Analiza ROI 2 | image_id, roi_1, roi_2 | Prediccion/QC/audit | Implementado/parcial | ROI/IA visual |
| POST | `/api/histopathology/heatmaps/jobs` | Inicia job heatmap ROI 1 | image_id, roi, tile_size, stride, max_tiles, headers rol/client-id | `{job_id, status:"queued", ...}` o 403/429 | Implementado/parcial | Heatmap async |
| GET | `/api/histopathology/heatmaps/jobs/{job_id}` | Consulta estado job heatmap | job_id | `{status, progress, processed_tiles, total_tiles, result}` | Implementado/parcial | Heatmap async |
| GET | `/api/histopathology/heatmaps/image/{image_id}/latest` | Carga ultimo heatmap persistido | image_id | Heatmap guardado o 404 | Implementado/parcial | Heatmap async |
| GET | `/api/histopathology/heatmaps/image/{image_id}/history` | Lista historial resumido de heatmaps de una imagen | image_id, limit | `{image_id,count,items}` | Implementado/parcial | Heatmap async |

### Tablas de base de datos

| Tabla | Proposito | Campos principales | Relaciones | Estado |
|---|---|---|---|---|
| `users` | Usuarios | id, email, name, password_hash, role, created_at | 1:N con `medical_images` | Parcial; auth no real |
| `medical_images` | Metadata imagenes | filename, title, file_type, file_size, file_path, dzi_path, uploaded_by | FK `uploaded_by -> users.id` | Implementado/parcial |
| `cases` | Casos clinicos para RAG SQL | title, description, body, is_active | Sin FK | Implementado API/parcial flujo |
| `documents` | Documentos para RAG futuro | title, content, tags | Sin FK | Pendiente/no usado |
| `chat_logs` | Logs chat proyectados | user_id, question, answer, created_at | Sin FK | Pendiente/no usado |
| `sct_tests` | Tests SCT guardados | name, difficulty, focus, num_items, items_json, is_active | Sin FK | Implementado |

---

## 7. Evidencias para Capitulo IV

| Evidencia | Modulo relacionado | Que demuestra | Estado | Recomendacion para informe |
|---|---|---|---|---|
| Captura landing | Frontend | Acceso y enfoque educativo | Implementado | Incluir |
| Captura login | Auth | Login simulado | Parcial | Incluir aclarando simulacion |
| Captura dashboard | Gestion academica | Modulos y metricas locales | Parcial | Incluir |
| Captura chatbot | Chatbot | Flujo pregunta/respuesta | Parcial | Incluir con disclaimer |
| Captura SCT configuracion | SCT | Parametros de generacion | Implementado/parcial | Incluir |
| Captura SCT item/resultados | SCT | Escala, feedback, puntaje | Implementado/parcial | Incluir |
| Captura config SCT | Gestion academica | Banco de tests | Implementado/parcial | Incluir |
| Captura biblioteca imagenes | Imagenes | Listado/carga | Implementado/parcial | Incluir |
| Captura visor DZI | Visor | Deep zoom histopatologico | Implementado/parcial | Incluir si backend activo |
| Captura ROI 1/ROI 2 | ROI | Seleccion de regiones | Implementado/parcial | Incluir |
| Captura resultado ROI | IA visual | Clase, confianza, QC, warning | Parcial/avanzado | Incluir como educativo/no diagnostico |
| Captura heatmap ROI async | IA visual | Job asincronico, barra progreso, tiles coloreados, persistencia | Implementado/parcial | Incluir mostrando estados (en cola, procesando, completado) |
| FastAPI `/docs` | Backend/API | Endpoints reales | Implementado/parcial | Incluir |
| `pytest` 22 passed | Pruebas | Validacion ROI/QC/auditoria/heatmap_store/heatmap_jobs | Parcial | Incluir log |
| Build frontend | Frontend | Compilacion | Implementado | Incluir log resumido |
| `docker-compose.yml` | Despliegue | DB/backend/ollama/GPU/env | Parcial | Incluir, aclarar frontend fuera |
| `models.py`/psql | Base de datos | Tablas reales | Parcial | Incluir |
| `audit_log.jsonl` | IA visual | Trazabilidad por `trace_id` | Implementado/parcial | Incluir extracto anonimizado |
| `tri_head_*metrics.json` | IA visual | Metricas entrenamiento/evaluacion | Parcial | Incluir con limites metodologicos |
| `patient_017_node_2.dzi` | Visor | DZI real 94968 x 210579 | Implementado/parcial | Incluir |
| Git log | Gestion desarrollo | Evolucion por commits | Implementado | Incluir 5-10 commits |
| Kanban externo | Gestion proyecto | Scrumban/Kanban | Pendiente si no existe | Crear captura si se uso Trello/GitHub Projects |

---

---

## 8a. Arquitectura del modulo heatmap asincronico

### Descripcion general

El modulo de heatmap histopatologico permite al estudiante solicitar un analisis tile a tile de la Region de Interes 1 (ROI 1) definida sobre una lamina histopatologica. A diferencia de un escaneo sincronico (que bloquea la solicitud HTTP hasta terminar), el sistema utiliza un patron de jobs asincronicos para permitir progreso observable, tolerancia a latencias y persistencia del resultado.

### Flujo tecnico del job de heatmap

```
[Estudiante: clic "Mapa de ROI 1"]
         |
         v
POST /api/histopathology/heatmaps/jobs
  {image_id, roi, tile_size, stride, max_tiles}
         |
         v
Backend: crea job en memoria (_JOBS dict, heatmap_jobs.py)
  status: "queued", job_id: UUID
         |
         v
Backend: lanza hilo de trabajo (BackgroundTasks / threading)
  - Divide ROI en grid de tiles segun tile_size y stride
  - Por cada tile: extrae patch (OpenSlide/PIL), QC, clasifica (CONCH)
  - Actualiza job: status="running", progress, processed_tiles, total_tiles
         |
         v
[Frontend: polling cada ~1.2 s]
GET /api/histopathology/heatmaps/jobs/{job_id}
  -> actualiza barra de progreso y conteo de tiles
         |
         v
Backend: al terminar todos los tiles
  - Calcula resumen: tile con mayor tumor_score (best_tile), count metastasicos
  - Persiste resultado en filesystem (heatmap_store.py):
      artifacts/histopathology/heatmaps/traces/{trace_id}.json
      artifacts/histopathology/heatmaps/images/{image_id}/latest.json
  - Actualiza job: status="completed", result={tiles, summary, persisted:true}
         |
         v
Frontend: recibe result, renderiza overlay de tiles coloreados
  Verde (baja) / Amarillo (media) / Rojo (alta metastasis) / Gris (no evaluable)
         |
         v
[Sesion futura: clic "Cargar ultimo mapa"]
GET /api/histopathology/heatmaps/image/{image_id}/latest
  -> recupera heatmap previo persistido sin necesidad de re-analizar
```

### Parametros configurables en la UI

| Parametro | Valores disponibles | Efecto |
|---|---|---|
| `tile_size` | 512 px, 1024 px | Tamano del tile cuadrado extraido; determina granularidad del mapa |
| `stride` | Igual a `tile_size` (sin solapamiento) | Avance entre tiles; stride = tile_size implica cobertura sin redundancia |
| `max_tiles` | 64 (constante actual) | Limite de tiles por job para proteger tiempo de respuesta educativo |

### Persistencia de heatmaps (heatmap_store.py)

Cada resultado de job completado se guarda en dos rutas del filesystem:

- **Por trace_id**: `artifacts/histopathology/heatmaps/traces/{trace_id}.json`  
  Permite recuperar cualquier analisis previo de forma trazable.

- **Por image_id (latest)**: `artifacts/histopathology/heatmaps/images/{image_id}/latest.json`  
  Permite cargar rapidamente el heatmap mas reciente de una imagen sin conocer el trace_id.

La escritura esta protegida por un `threading.Lock` para evitar corrupcion en entornos con concurrencia.

### Cola de jobs y limite de workers (heatmap_jobs.py)

Los jobs se almacenan en memoria (`_JOBS: Dict[str, Dict]`) con un semaforo (`_WORKER_SEMAPHORE`) configurable via variable de entorno `HISTO_MAX_CONCURRENT_HEATMAP_JOBS` (defecto: 1). Esto limita la cantidad de jobs de heatmap ejecutandose simultaneamente para no saturar la GPU o CPU del servidor educativo.

Limitacion importante: los jobs en memoria no sobreviven reinicios del servidor. El resultado ya persistido en filesystem si es recuperable.

### Uso educativo vs. uso admin/docente

El diseno del modulo distingue dos niveles de uso:

**Estudiante (uso interactivo):**
- Puede solicitar heatmaps acotados a ROI 1 con max_tiles=16 y tile_size 512 o 1024.
- El analisis tarda segundos a pocos minutos segun el area de ROI y la disponibilidad de GPU.
- Resultado inmediato visible en visor con overlay de tiles coloreados.
- Puede cargar el ultimo mapa guardado sin repetir el calculo.
- Tiene rate limit de 3 solicitudes por ventana de 60 segundos para evitar saturacion accidental.
- **No puede** analizar la lamina completa (WSI completa puede tener millones de tiles).

**Docente / administrador (precalculo):**
- Desde `ConfigPage.jsx` puede generar un heatmap acotado sobre una imagen DZI antes de la clase, definiendo coordenadas ROI, `tile_size` y `max_tiles`.
- El resultado se guarda en el filesystem y queda disponible para todos los estudiantes via "Cargar ultimo mapa".
- El historial por imagen permite recuperar mapas anteriores por `trace_id`, util para preparar varias regiones educativas en una misma lamina.
- Tiene limites configurables mas altos para preparar mapas: hasta 256 tiles y 20 solicitudes por ventana por defecto.
- El flujo de lamina completa aun no esta implementado como endpoint protegido con cola durable; sigue como tarea pendiente de PB-24.

### Riesgos tecnicos identificados

| Riesgo | Descripcion | Impacto | Mitigacion actual |
|---|---|---|---|
| Consumo de GPU/CPU | El modelo CONCH requiere inferencia por cada tile; sin GPU puede ser lento para ROI grande. | Alto en produccion; moderado con max_tiles acotado | Limite `max_tiles`, semaforo de workers, rate limit por rol |
| Concurrencia sin persistencia de jobs | Jobs en memoria se pierden al reiniciar el servidor; el cliente queda en polling indefinido. | Medio | Resultado ya persistido en filesystem; pendiente: cola durable (Redis, DB) |
| WSI muy grandes | Laminillas completas de 100,000+ px por lado generan miles de tiles; no acotados al ROI del estudiante. | Alto | ROI 1 acotado obligatorio; heatmap completo reservado para admin |
| Saturacion de workers | Multiples estudiantes solicitando heatmaps simultaneamente pueden colapsar la memoria o el modelo. | Alto si sin limites | `HISTO_MAX_CONCURRENT_HEATMAP_JOBS`, `HISTO_STUDENT_HEATMAP_JOBS_PER_WINDOW`; pendiente: auth real/JWT |
| Uso no diagnostico | Clasificacion educativa no validada clinicamente; puede mostrar falsos positivos/negativos. | Critico si se malinterpreta | Advertencia visible en UI; log de auditoria por trace_id; disclaimer en resultado |
| Dependencia de checkpoint CONCH | Si el checkpoint no esta disponible, el modelo no carga y todos los heatmaps fallan. | Alto | `/api/histopathology/status` indica `model_ready=false`; boton analizar deshabilitado |
| Tamano del bundle frontend | Bundle JS > 500 kB (warning Vite); OpenSeadragon es grande. | Bajo/medio en educativo | Advertencia conocida; puede mitigarse con code splitting futuro |

---

## 8. Recomendaciones finales para Capitulo IV

Secciones que pueden completarse con evidencia real:

| Seccion | Evidencia real disponible |
|---|---|
| 4.2.5 Diagrama de actividades | Flujos React/Backend/IA reales de chat, SCT, visor y ROI |
| 4.2.6 BPMN | Pools/lane basados en frontend, backend, DB, IA/Ollama/CONCH |
| 4.3.2 Product Backlog | Backlog reconstruible desde commits, archivos y pendientes claros |
| 4.3.3 Kanban/iteraciones | Iteraciones tecnicas derivadas de commits y modulos |
| 4.3.4 Frontend | Codigo React y build exitoso |
| 4.3.5 Backend | Routers FastAPI y endpoints |
| 4.3.6 Base de datos | Modelos SQLAlchemy y PostgreSQL |
| 4.3.7 Visor histopatologico | OSD/Fabric/DZI/endpoints |
| 4.3.8 ROI | ROI 1/2, validaciones, patch extraction, tests |
| 4.3.9 SCT | Generacion/resolucion/CRUD |
| 4.3.10 Chatbot | UI + endpoint + prompt educativo |
| 4.3.11 IA/RAG | Ollama, RAG SQL, CONCH, QC, audit logs, checkpoints |

Secciones que deben redactarse como implementacion parcial:

| Seccion | Motivo |
|---|---|
| Autenticacion/usuarios | Login local y backend mock, sin JWT ni permisos reales |
| Gestion academica | Dashboard/metricas locales, sin persistencia institucional |
| RAG | Recuperacion SQL por texto, sin vector DB ni ingestion documental completa |
| IA visual | Funcional para ROI educativa, pero no validacion clinica ni lamina completa |
| Heatmap | Acotado a ROI y sincronico; sin persistencia ni procesamiento completo WSI |
| Docker | No incluye frontend en compose actual |

Secciones o funcionalidades pendientes/proyectadas:

| Pendiente | No afirmar como terminado |
|---|---|
| Autenticacion real, JWT, RBAC | No declarar seguridad productiva |
| Persistencia de ROI | No afirmar almacenamiento central de ROI |
| Intentos/respuestas SCT por estudiante | No afirmar trazabilidad academica completa |
| ChatLog | Tabla existe, endpoint no la usa |
| RAG vectorial/documental | Solo existe busqueda SQL simple |
| Configuracion IA desde UI | Tab "Configuracion IA" es placeholder |
| Diagnostico clinico o validacion clinica | Prototipo educativo, no diagnostico |
| Clasificacion de lamina completa | Solo ROI/patch y heatmap ROI acotado |

Diagramas tecnicos que conviene agregar/corregir:

| Diagrama | Recomendacion |
|---|---|
| Actividades | Separar base, histopatologia y IA educativa |
| BPMN | Usar flujos de mensaje entre pools; no secuencia entre estudiante/backend |
| Arquitectura logica | React, FastAPI, PostgreSQL, Ollama, CONCH, filesystem |
| Despliegue | Local/Docker: frontend 3000, backend 8001, db 5432, Ollama 11434 |
| DER | Tablas reales y tablas propuestas separadas |
| Secuencia ROI | Frontend -> status -> analyze-roi -> QC -> CONCH -> audit -> respuesta |
| Secuencia SCT | Frontend -> generate -> Ollama -> save/list/get |

Informacion faltante para dejar el capitulo solido:

| Falta | Para que sirve |
|---|---|
| Capturas actualizadas del sistema corriendo | Evidencia visual del prototipo |
| Captura FastAPI `/docs` actual | Evidencia endpoints reales |
| Captura DB `\dt` y registros SCT/imagenes | Evidencia persistencia |
| Captura Kanban real si existio | Evidencia Scrumban/Kanban |
| Decision metodologica del puntaje SCT | Justificar tolerancia +/-1 si se mantiene |
| Politica de uso de datos/datasets WSI | Defender limites de CAMELYON/PCam/SLN-Breast |
| Validacion con usuarios/docentes | Respaldar utilidad educativa |
| Plan de riesgos IA | Alucinaciones, seguridad, no diagnostico |
