# Capitulo IV - Estado real de implementacion ASOFAMECH

Documento de apoyo para los apartados 4.3.4 a 4.3.11.

Fecha de revision: 19-05-2026.

Alcance: revision del codigo fuente local del proyecto ASOFAMECH. Este documento evita pegar bloques extensos de codigo y prioriza proceso de implementacion, decisiones tecnicas, flujo funcional, evidencias y validaciones.

Validaciones ejecutadas durante la revision:

| Validacion | Resultado |
|---|---|
| `backend/.venv/Scripts/python.exe -m pytest tests -q` | 126 pruebas aprobadas, 4 warnings de Pydantic v2. |
| `frontend/npm.cmd run build` | Build exitoso con Vite. 58 modulos transformados. Advertencia: bundle JS principal mayor a 500 kB. |
| Revision Git reciente | Commits relevantes: `db7ca61`, `d241791`, `ac18946`, `291f0be`, `7bcd4d7`. |

## 4.3.4. Implementacion del Front-End

El front-end se implemento como una aplicacion de pagina unica construida con React 18 y Vite. La navegacion se organiza con `react-router-dom` y las vistas principales estan definidas en `frontend/src/app.jsx`. La interfaz esta contenida principalmente en `frontend/src/pages` y `frontend/src/components`, con estilos globales en `frontend/src/styles.css`.

Tecnologias y librerias utilizadas:

- React 18 para componentes y estado de interfaz.
- Vite para servidor de desarrollo y empaquetado.
- React Router DOM para rutas publicas y privadas de facto.
- OpenSeadragon para visualizacion DZI de laminas histopatologicas.
- Fabric.js para visor/anotaciones sobre imagenes no DZI.
- Fetch API y cliente propio `authClient.js` para comunicacion HTTP.
- `localStorage` para sesion del cliente, historial local de chat, metricas de uso y resultados SCT locales.

Estructura de vistas implementadas:

- `LandingPage.jsx`: pagina publica de presentacion.
- `AuthPage.jsx`: login y registro con flujo de aprobacion.
- `DashboardPage.jsx`: tablero inicial, actividad, metricas y ranking.
- `ChatbotPage.jsx`: asistente educativo con historial de conversaciones.
- `SCTPage.jsx`: generacion, resolucion y retroalimentacion de SCT.
- `ImagesPage.jsx`: biblioteca de imagenes y visor histopatologico.
- `ConfigPage.jsx`: gestion de imagenes, documentos RAG, usuarios, configuracion IA, correo y tests SCT.
- `ReviewPage.jsx`: revision docente de sesiones histopatologicas.

Flujo de navegacion:

1. El visitante accede a `/`.
2. Desde la landing puede ir a `/auth`.
3. Al iniciar sesion se guarda token JWT, usuario y rol en `localStorage`.
4. El usuario autenticado ingresa a `/dashboard`.
5. Desde el dashboard accede a asistente IA, SCT o imagenes IA.
6. Usuarios con rol Profesor o Administrador ven configuracion en el sidebar.
7. La revision docente existe como ruta `/dashboard/review`, aunque el sidebar actual no la muestra como enlace permanente.

Control visual por rol:

El componente `AppSidebar.jsx` oculta la opcion de configuracion para usuarios no privilegiados. `ConfigPage.jsx` muestra pestanas adicionales para Administrador, como Usuarios, Configuracion IA y Correo. Este control es visual y se apoya en el rol almacenado localmente; las acciones sensibles se refuerzan en backend mediante JWT y dependencias de rol.

Decisiones tecnicas adoptadas:

- Usar React/Vite para iteracion rapida y bajo costo de configuracion.
- Separar paginas y componentes para mantener modularidad.
- Usar cliente `authClient.js` para adjuntar `Authorization: Bearer`.
- Mantener estados locales para conversaciones y resultados SCT, permitiendo una experiencia fluida aun cuando no todo esta persistido.
- Usar OpenSeadragon solo cuando la imagen dispone de DZI, evitando cargar laminas completas en memoria.

Tabla de evidencia del apartado 4.3.4:

| Apartado | Componente implementado | Tecnologia/herramienta usada | Evidencia tecnica disponible | Evidencia visual sugerida | Validacion o prueba realizada | Estado actual | Limitaciones o pendiente |
|---|---|---|---|---|---|---|---|
| 4.3.4 | Landing publica | React/Vite | `LandingPage.jsx`, ruta `/` | Pagina inicial publica ASOFAMECH | Build Vite exitoso | Implementado | Ajustar textos finales del informe/institucion. |
| 4.3.4 | Login y registro | React, JWT client-side | `AuthPage.jsx`, `authClient.js` | Formulario de inicio de sesion y registro pendiente | Prueba manual recomendada login/registro | Implementado | Completar flujo visual de cuenta pendiente y rechazo con mas estados. |
| 4.3.4 | Dashboard | React, API dashboard | `DashboardPage.jsx`, `/api/dashboard/stats`, `/api/dashboard/ranking` | Dashboard principal con modulos | Build Vite exitoso | Implementado/parcial | Algunas metricas SCT siguen en `localStorage`. |
| 4.3.4 | Sidebar y navegacion | React Router | `AppSidebar.jsx`, `app.jsx` | Sidebar por rol | Revision de rutas | Implementado/parcial | Ruta `/dashboard/review` no esta enlazada actualmente en sidebar. |
| 4.3.4 | Asistente IA | React, fetch API | `ChatbotPage.jsx`, `api.js` | Chat con respuesta educativa y fuentes RAG | Prueba manual recomendada | Implementado | Historial largo vive en cliente; backend guarda cada pregunta/respuesta. |
| 4.3.4 | SCT | React, formularios | `SCTPage.jsx`, `SCTSection.jsx` | Generacion y resolucion de SCT | Build Vite exitoso | Implementado/parcial | Falta persistencia centralizada de intentos por estudiante. |
| 4.3.4 | Imagenes IA | React, OpenSeadragon | `ImagesPage.jsx`, `OpenSeadragonViewer.jsx` | Visor con ROI y heatmap | Prueba manual recomendada | Implementado/parcial | Depende de DZI y backend con OpenSlide. |
| 4.3.4 | Configuracion | React, panel admin | `ConfigPage.jsx` | Tabs: imagenes, RAG, usuarios, IA, correo, SCT | Build Vite exitoso | Implementado/parcial | UI grande; conviene code splitting por bundle pesado. |

## 4.3.5. Implementacion del Back-End

El back-end se implemento con FastAPI y se organiza en routers especializados. `backend/app/main.py` crea la aplicacion, configura CORS, monta routers, expone `/health` y crea tablas mediante SQLAlchemy al iniciar.

Tecnologias utilizadas:

- FastAPI como framework REST.
- Uvicorn como servidor ASGI.
- SQLAlchemy como ORM.
- PostgreSQL/pgvector como base de datos.
- httpx para comunicacion con Ollama.
- python-multipart para carga de archivos.
- OpenSlide y Pillow para imagenes medicas.
- PyTorch/CONCH para inferencia histopatologica cuando las dependencias estan disponibles.

Organizacion del backend:

- `backend/app/routers`: rutas por modulo.
- `backend/app/models.py`: modelos SQLAlchemy.
- `backend/app/schemas.py`: esquemas generales.
- `backend/app/histopathology/schemas.py`: esquemas ROI, heatmap y correcciones.
- `backend/app/auth.py` y `auth_security.py`: JWT, hashing y control de roles.
- `backend/app/histopathology/*`: ROI, QC, inferencia, heatmaps, cache y auditoria.
- `backend/histopathology_offline/*`: entrenamiento, evaluacion y mineria CAMELYON17.

Endpoints principales:

| Modulo | Endpoints principales | Estado |
|---|---|---|
| Salud | `GET /health` | Implementado |
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` | Implementado |
| Usuarios/admin | `GET/POST/PATCH/DELETE /api/admin/users`, `POST /approve`, `POST /reject` | Implementado |
| Config IA | `GET/PUT /api/admin/ai-config`, `GET /api/admin/integrations/status` | Implementado |
| Correo | `GET/PUT /api/admin/email-config`, `POST /test`, `GET/PUT /email-templates/{key}` | Implementado/parcial |
| Imagenes | `POST /api/medical-images/upload`, `GET /list`, `GET /view/{id}`, `DELETE /{id}` | Implementado |
| CAMELYON17 local | `GET /local/camelyon17`, `POST /import-local/camelyon17` | Implementado |
| DZI | `GET /dzi/{id}.dzi`, `GET /dzi/{id}_files/{level}/{col}_{row}.{fmt}` | Implementado |
| Histopatologia | `GET /status`, `POST /analyze-roi`, `POST /scan-roi` | Implementado |
| Heatmaps | `POST /heatmaps/jobs`, `GET /jobs/{id}`, `GET /image/{id}/latest`, `GET /history`, `GET/DELETE /{trace_id}` | Implementado/parcial |
| Sesiones ROI | `GET /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}` | Implementado |
| Revision docente | `POST/DELETE /sessions/{id}/correction`, `GET /review/sessions`, `GET /dataset/manifest` | Implementado |
| RAG | `GET/POST/PUT/DELETE /api/rag/documents`, `POST /reindex`, `GET /search` | Implementado/parcial |
| Chatbot | `POST /api/chat` | Implementado |
| Casos | `GET /api/cases`, `POST /api/cases`, `GET /api/cases/search` | Implementado API |
| SCT | `POST /api/sct/generate`, `GET /example`, `POST /save`, `GET /list`, `GET/DELETE /{id}` | Implementado/parcial |
| Dashboard | `GET /api/dashboard/stats`, `GET /api/dashboard/ranking` | Implementado/parcial |

Flujo de comunicacion:

El frontend envia solicitudes REST al backend usando `VITE_API_BASE` o `http://localhost:8001`. Las rutas protegidas reciben token Bearer. El backend valida el usuario, consulta PostgreSQL, filesystem, Ollama o el servicio histopatologico, y devuelve JSON para la interfaz.

Tabla de evidencia del apartado 4.3.5:

| Apartado | Componente implementado | Tecnologia/herramienta usada | Evidencia tecnica disponible | Evidencia visual sugerida | Validacion o prueba realizada | Estado actual | Limitaciones o pendiente |
|---|---|---|---|---|---|---|---|
| 4.3.5 | API principal | FastAPI/Uvicorn | `main.py`, `/health`, OpenAPI | Swagger `/docs` | Pytest 126 passed | Implementado | Migraciones formales pendientes. |
| 4.3.5 | Routers modulares | FastAPI APIRouter | `routers/auth.py`, `admin.py`, `histopathology.py`, etc. | Captura Swagger por tags | Pytest | Implementado | Estandarizar nombres/respuestas. |
| 4.3.5 | Seguridad | JWT HS256, PBKDF2 | `auth.py`, `auth_security.py` | Login exitoso y cuenta pendiente | `test_auth_security.py`, `test_user_approval.py` | Implementado | Configurar secreto JWT real en produccion. |
| 4.3.5 | Integracion Ollama | httpx | `chat.py`, `sct.py`, `docker-compose.yml` | Consola Ollama/backend | Prueba manual recomendada | Implementado/parcial | Depende de modelo local descargado y servicio activo. |
| 4.3.5 | Histopatologia API | FastAPI + PyTorch | `histopathology.py` | Endpoint `/status` y resultado ROI | Tests histopathology | Implementado/parcial | Uso educativo, no diagnostico. |

## 4.3.6. Implementacion de la Base de Datos

La persistencia utiliza PostgreSQL 15 mediante SQLAlchemy. En Docker se declara la imagen `pgvector/pgvector:pg15`, lo que permite usar la extension `vector` cuando esta disponible. Las tablas se crean al iniciar el backend mediante `Base.metadata.create_all(bind=engine)` y migraciones ligeras de compatibilidad en `main.py`.

Entidades principales:

| Modelo | Tabla | Funcion |
|---|---|---|
| `User` | `users` | Usuarios, rol, estado de cuenta, aprobacion. |
| `MedicalImage` | `medical_images` | Metadata de imagenes, ruta del archivo, DZI y usuario uploader. |
| `Case` | `cases` | Casos clinicos usados como contexto para chatbot/RAG basico. |
| `Document` | `documents` | Documentos academicos cargados para RAG documental. |
| `DocumentChunk` | `document_chunks` | Fragmentos vectorizados de documentos. |
| Tabla pgvector dinamica | `document_vector_embeddings` | Embeddings vectoriales para busqueda semantica con pgvector. |
| `ChatLog` | `chat_logs` | Preguntas y respuestas del chatbot por usuario. |
| `AIConfiguration` | `ai_configurations` | Parametros IA, RAG, correo y comportamiento. |
| `EmailTemplate` | `email_templates` | Plantillas de correo para aprobacion/rechazo/suspension. |
| `SCTTest` | `sct_tests` | Tests SCT generados y guardados. |
| `HistopathologySession` | `histopathology_sessions` | Analisis ROI por usuario, imagen, coordenadas, clase, probabilidades y QC. |
| `HistopathologyCorrection` | `histopathology_corrections` | Correcciones docentes sobre sesiones histopatologicas. |

Relaciones principales:

- `User` 1:N `MedicalImage`.
- `User` 1:N `HistopathologySession`.
- `MedicalImage` 1:N `HistopathologySession`.
- `HistopathologySession` 1:1 `HistopathologyCorrection`.
- `Document` 1:N `DocumentChunk`.
- `DocumentChunk` 1:1 aproximado con `document_vector_embeddings` mediante `chunk_id`.
- `User` puede aprobar a otros usuarios mediante `approved_by`.

Informacion persistida actualmente:

- Usuarios y estado de aprobacion.
- Imagenes medicas y rutas de archivos.
- Casos clinicos.
- Documentos RAG y chunks.
- Logs de chat individuales.
- Configuracion IA y correo.
- Tests SCT guardados.
- Sesiones ROI histopatologicas.
- Correcciones docentes.
- Heatmaps en JSON dentro de `artifacts/histopathology/heatmaps`, no en tabla SQL.

Informacion pendiente o parcial:

- Intentos SCT por estudiante, respuestas individuales y puntajes historicos centralizados.
- Conversaciones completas de chatbot como hilo en base de datos; actualmente el backend guarda intercambio pregunta/respuesta y el frontend conserva hilos en `localStorage`.
- Jobs de heatmap durables en DB o Redis; actualmente viven en memoria.
- Migraciones Alembic formales.
- Politica definitiva de aislamiento por propietario de imagen en todos los modulos.

Tabla de evidencia del apartado 4.3.6:

| Apartado | Componente implementado | Tecnologia/herramienta usada | Evidencia tecnica disponible | Evidencia visual sugerida | Validacion o prueba realizada | Estado actual | Limitaciones o pendiente |
|---|---|---|---|---|---|---|---|
| 4.3.6 | Base relacional | PostgreSQL 15 | `docker-compose.yml`, `db.py` | Captura contenedor DB o tablas | Pytest con DB/test doubles segun tests | Implementado | Agregar Alembic. |
| 4.3.6 | ORM | SQLAlchemy | `models.py` | DER actualizado | Revision de modelos | Implementado | Documentacion DB anterior esta desactualizada. |
| 4.3.6 | RAG vectorial | pgvector + JSON embeddings | `pgvector_store.py`, `DocumentChunk` | Captura documentos/chunks | `test_embedding_service.py`, `test_rag_utils.py` | Implementado/parcial | Verificar extension vector en ambiente productivo. |
| 4.3.6 | Historial ROI | SQLAlchemy JSON | `HistopathologySession` | Registro con `trace_id` | Tests histopathology | Implementado | Completar vistas de historial transversal. |
| 4.3.6 | Heatmaps persistidos | JSON filesystem | `heatmap_store.py` | Carpeta `artifacts/.../heatmaps` | `test_heatmap_store.py` | Parcial | Migrar jobs/resultados criticos a DB. |

## 4.3.7. Implementacion del Visor Histopatologico

El visor histopatologico utiliza OpenSeadragon para imagenes con DZI y Fabric.js para visualizacion/anotacion de imagenes raster no DZI. El flujo principal esta en `ImagesPage.jsx` y `OpenSeadragonViewer.jsx`.

Carga e importacion de imagenes:

- Carga por navegador: `POST /api/medical-images/upload`.
- Importacion local CAMELYON17: `GET /api/medical-images/local/camelyon17` y `POST /api/medical-images/import-local/camelyon17`.
- Formatos permitidos: `.svs`, `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`.
- Las laminas WSI grandes se preparan con DZI dinamico, generando manifiesto y tiles bajo demanda.

DZI y tiles:

- Manifiesto DZI: `GET /api/medical-images/dzi/{image_id}.dzi`.
- Tiles: `GET /api/medical-images/dzi/{image_id}_files/{level}/{col}_{row}.{fmt}`.
- Para WSI, `process_wsi_to_dzi` crea el XML DZI sin pregenerar todos los tiles.
- Si falta un tile WSI, `get_dynamic_wsi_tile` lo genera bajo demanda con OpenSlide.

Decisiones tecnicas:

- DZI evita cargar imagenes de varios GB completas en el navegador.
- Importacion local CAMELYON17 evita subir archivos de 3 GB por HTTP.
- OpenSeadragon permite zoom y pan fluido.
- OpenSlide permite leer regiones y tiles desde laminas WSI reales.

Tabla de evidencia del apartado 4.3.7:

| Apartado | Componente implementado | Tecnologia/herramienta usada | Evidencia tecnica disponible | Evidencia visual sugerida | Validacion o prueba realizada | Estado actual | Limitaciones o pendiente |
|---|---|---|---|---|---|---|---|
| 4.3.7 | Biblioteca de imagenes | React + FastAPI | `ImagesPage.jsx`, `medical_images.py` | Lista de imagenes con DZI | Prueba manual recomendada | Implementado | Gestion por propietario parcial. |
| 4.3.7 | Visor DZI | OpenSeadragon | `OpenSeadragonViewer.jsx` | Visor con zoom 40x | Prueba manual con CAMELYON17 | Implementado | Requiere DZI y OpenSlide. |
| 4.3.7 | Tiles dinamicos | OpenSlide DeepZoom | `get_dynamic_wsi_tile` | Red de tiles cargando progresivamente | Prueba manual visor | Implementado/parcial | Cache de tiles DZI fisicos no centralizado. |
| 4.3.7 | Importacion CAMELYON17 | Filesystem + DB | `/local/camelyon17`, `/import-local/camelyon17` | Panel importar lamina local | Prueba manual previa | Implementado | Requiere archivos ya descargados en servidor. |

## 4.3.8. Implementacion del Modulo ROI

El modulo ROI permite seleccionar una region amplia de trabajo (ROI 1) y una subregion especifica (ROI 2). En el frontend, `OpenSeadragonViewer.jsx` transforma coordenadas del visor a coordenadas de imagen nivel 0. En backend, `roi.py` valida limites, tamanos y contencion.

Validaciones implementadas:

- ROI no debe exceder dimensiones de lamina.
- ROI 2 debe estar contenida dentro de ROI 1.
- ROI 2 debe medir al menos 32x32 pixeles.
- ROI 2 no debe superar 4096x4096 pixeles.
- Backend repite validacion, por lo que no depende solo de la UI.

Extraccion de patches:

- `OpenSlidePatchExtractor.get_slide_dimensions` obtiene dimensiones.
- `extract_roi2` lee la region desde OpenSlide o usa Pillow como fallback.
- Se genera `trace_id` por analisis.
- Se guardan artefactos de depuracion mediante `debug_patches.py`.
- Se persiste sesion en `histopathology_sessions` con usuario, imagen, ROI 1, ROI 2, estado, clase, probabilidades y metricas de calidad.

Flujo completo:

1. Usuario abre una imagen DZI.
2. Selecciona ROI 1.
3. Selecciona ROI 2 dentro de ROI 1.
4. Frontend valida contencion y tamano.
5. Frontend envia `POST /api/histopathology/analyze-roi`.
6. Backend valida geometria contra dimensiones reales.
7. Backend extrae patch RGB.
8. Se evalua control de calidad.
9. Se ejecuta CONCH/PyTorch si la ROI es evaluable.
10. Se devuelve resultado educativo y se persiste la sesion.

Tabla de evidencia del apartado 4.3.8:

| Apartado | Componente implementado | Tecnologia/herramienta usada | Evidencia tecnica disponible | Evidencia visual sugerida | Validacion o prueba realizada | Estado actual | Limitaciones o pendiente |
|---|---|---|---|---|---|---|---|
| 4.3.8 | ROI 1/ROI 2 | React + OpenSeadragon | `OpenSeadragonViewer.jsx` | ROI 1 azul y ROI 2 naranja | Prueba manual recomendada | Implementado | Mejorar UX para reajuste fino de ROI. |
| 4.3.8 | Validacion geometrica | Python/Pydantic | `roi.py`, `schemas.py` | Error cuando ROI 2 queda fuera | `test_histopathology_roi.py` | Implementado | Agregar mas mensajes pedagogicos. |
| 4.3.8 | Extraccion patch | OpenSlide/Pillow | `patch_extractor.py` | Patch debug con trace_id | Tests y prueba ROI | Implementado | Depende de OpenSlide para WSI. |
| 4.3.8 | Persistencia de sesion | SQLAlchemy | `HistopathologySession`, `/sessions` | Historial educativo de ROI | Tests histopathology | Implementado | Intentos SCT no siguen el mismo nivel de persistencia. |

## 4.3.9. Implementacion del Modelo Visual CONCH/PyTorch

El modelo visual usa CONCH como extractor congelado de caracteristicas y una cabeza clasificadora PyTorch entrenada sobre embeddings. La integracion esta en `app/histopathology/ml`.

Arquitectura:

- Backbone: CONCH `conch_ViT-B-16`.
- Uso: extractor congelado, sin reentrenar el backbone.
- Entrada: patch RGB, preprocesado por CONCH, tipicamente 224x224.
- Embedding: 512 dimensiones segun endpoint de estado.
- Cabeza: clasificador 3 clases sobre embeddings CONCH.
- Checkpoint activo en Docker: `tri_head_camelyon17_stage10_balanced_v1_weighted.pt`.

Clases/salidas:

- `no_metastasico`.
- `metastasico`.
- `estroma`.
- Salidas derivadas por decision: `roi_no_evaluable`, `resultado_incierto`, `no_metastasico_probable`.

Control de calidad:

Antes de inferir se evalua la ROI con `roi_quality.py`, que estima:

- fraccion de fondo blanco;
- fraccion de tejido util;
- fraccion nuclear/celular;
- predominio estromal;
- estroma con baja celularidad.

Si la ROI no es evaluable, el sistema evita dar una clasificacion cerrada y devuelve recomendacion educativa. Si el modelo predice `estroma`, tambien se abstiene como `roi_no_evaluable`. Si la confianza no supera el umbral configurado, devuelve resultado incierto o baja sospecha no metastasica.

Heatmaps:

- `POST /api/histopathology/heatmaps/jobs` crea un job asincronico en memoria.
- El backend divide ROI 1 en tiles.
- Cada tile se evalua con QC e inferencia.
- Se genera resumen con mejor tile, tiles sospechosos, cache hit/miss y decision ROI.
- Se guarda JSON por `trace_id` y ultimo mapa por imagen.
- Existe cache por tile en `heatmap_tile_cache.py`.
- Hay limites por rol para carga simultanea y cantidad de tiles.

Entrenamiento y validacion offline:

- Scripts en `backend/histopathology_offline`.
- Evaluacion con XML CAMELYON17.
- Stage 10 es el checkpoint activo.
- Stage 14 amplio datos con prioridad 1 CAMELYON17, pero no reemplazo Stage 10 porque la mejora fue marginal.

Tabla de evidencia del apartado 4.3.9:

| Apartado | Componente implementado | Tecnologia/herramienta usada | Evidencia tecnica disponible | Evidencia visual sugerida | Validacion o prueba realizada | Estado actual | Limitaciones o pendiente |
|---|---|---|---|---|---|---|---|
| 4.3.9 | Extractor CONCH | PyTorch + CONCH | `conch_feature_extractor.py` | Endpoint `/status` model_ready | Prueba status recomendada | Implementado/parcial | Requiere dependencias CONCH/checkpoint. |
| 4.3.9 | Cabeza clasificadora | PyTorch | `inference_service.py`, checkpoint Stage 10 | Resultado con probabilidades | Evaluaciones Stage 10/14 documentadas | Implementado/parcial | Dataset limitado a tarea CAMELYON/PCam. |
| 4.3.9 | Control de calidad | Heuristicas H&E | `roi_quality.py` | ROI no evaluable por estroma/fondo | `test_histopathology_roi_quality.py` | Implementado | Heuristico, no reemplaza revision experta. |
| 4.3.9 | Heatmaps ROI | FastAPI background tasks | `heatmap_jobs.py`, `heatmap_store.py` | Overlay por tiles en visor | `test_heatmap_*` | Implementado/parcial | Jobs en memoria; falta cola durable. |
| 4.3.9 | Auditoria | JSONL/artifacts | `audit_log.py`, `debug_patches.py` | Trace_id y patch debug | Tests audit log | Implementado | Gestion de retencion pendiente. |

## 4.3.10. Implementacion del RAG y Retroalimentacion Educativa

El sistema incorpora dos niveles de recuperacion:

1. RAG basico con casos clinicos: el chatbot busca coincidencias en la tabla `cases`.
2. RAG documental: permite crear documentos, fragmentarlos, vectorizarlos y recuperarlos semanticamente.

Implementacion actual:

- CRUD documental en `/api/rag/documents`.
- Fragmentacion mediante `chunk_text` en `rag_utils.py`.
- Embeddings con `sentence-transformers` si esta disponible.
- Fallback de embeddings locales por hashing si no esta disponible el modelo neuronal.
- Uso de pgvector cuando la extension esta disponible.
- Fallback a similitud coseno sobre JSON embeddings.
- Busqueda en `/api/rag/search`.
- Integracion con `POST /api/chat`, que recupera fuentes y las incorpora al prompt.
- Panel de documentos RAG en `ConfigPage.jsx`.
- Panel de configuracion IA con flags `rag_enabled`, `pgvector_enabled`, `neural_embeddings_enabled`, `embedding_model` y `max_context_documents`.

Flujo de RAG:

1. Docente/admin crea o actualiza documento RAG.
2. Backend divide el texto en chunks.
3. Cada chunk se vectoriza.
4. Si pgvector esta disponible, se guarda en `document_vector_embeddings`.
5. Ante una consulta, el backend vectoriza la pregunta.
6. Recupera documentos/chunks relevantes.
7. Construye contexto con fuentes.
8. El chatbot genera respuesta educativa apoyada en ese contexto.

Estado real:

RAG documental esta implementado en backend y UI, con busqueda vectorial y fallback. Queda parcial porque falta carga real de PDF/URL: la UI muestra origen PDF/URL, pero el backend actual recibe documento como titulo/contenido/tags. Tambien falta evaluacion formal de calidad de recuperacion y citacion academica mas robusta en la respuesta.

Tabla de evidencia del apartado 4.3.10:

| Apartado | Componente implementado | Tecnologia/herramienta usada | Evidencia tecnica disponible | Evidencia visual sugerida | Validacion o prueba realizada | Estado actual | Limitaciones o pendiente |
|---|---|---|---|---|---|---|---|
| 4.3.10 | RAG documental | FastAPI + SQLAlchemy | `rag.py`, `Document`, `DocumentChunk` | Panel Documentos RAG | `test_rag_utils.py`, `test_embedding_service.py` | Implementado/parcial | PDF/URL no ingestan contenido automaticamente. |
| 4.3.10 | Embeddings neuronales | sentence-transformers | `embedding_service.py` | Estado integracion IA | Tests embedding | Implementado/parcial | Depende de modelo local/descarga. |
| 4.3.10 | pgvector | PostgreSQL pgvector | `pgvector_store.py`, `docker-compose.yml` | Captura extension/vector store | Prueba recomendada `/api/admin/integrations/status` | Implementado/parcial | Fallback JSON si pgvector no esta disponible. |
| 4.3.10 | Retroalimentacion con contexto | Ollama + prompt | `chat.py`, `build_rag_context` | Respuesta con fuentes RAG | Prueba manual recomendada | Implementado/parcial | Citas/fuentes en formato academico aun mejorables. |

## 4.3.11. Implementacion del Chatbot Educativo y Modulo SCT

### A) Chatbot educativo

El chatbot educativo esta implementado en frontend mediante `ChatbotPage.jsx` y en backend mediante `POST /api/chat`. Usa Ollama como servicio local de modelo generativo y por defecto el modelo `llama3:8b`.

Funcionamiento:

1. El usuario escribe una consulta.
2. El frontend envia `POST /api/chat` con token si existe.
3. Backend valida que el mensaje no este vacio.
4. Si esta activo, clasifica si la consulta pertenece al ambito medico.
5. Recupera contexto desde casos clinicos y RAG documental.
6. Construye prompt educativo, con limites de no diagnostico.
7. Envia la solicitud a Ollama.
8. Guarda pregunta/respuesta en `ChatLog`.
9. Devuelve respuesta y fuentes RAG al frontend.

Limitaciones educativas:

- El prompt indica que no reemplaza evaluacion clinica.
- Se filtran consultas fuera del ambito medico.
- Se ignoran instrucciones de usuario que intenten cambiar reglas internas.

Estado:

Implementado/parcial. La respuesta y logs individuales estan persistidos; las conversaciones como hilos se gestionan en el navegador mediante `localStorage` por usuario.

### B) Modulo SCT

El modulo SCT permite generar tests de Script Concordance Test mediante Ollama, resolverlos en el frontend y guardar tests generados en PostgreSQL.

Parametros de generacion:

- Tema o foco medico (`focus`).
- Dificultad: `pregrado`, `internado`, `residente`.
- Cantidad de items (`num_items`).
- Escala de respuesta de -2 a +2.

Endpoints:

- `POST /api/sct/generate`.
- `GET /api/sct/example`.
- `POST /api/sct/save`.
- `GET /api/sct/list`.
- `GET /api/sct/{test_id}`.
- `DELETE /api/sct/{test_id}`.

Funcionamiento:

1. El usuario define tema, dificultad y cantidad de items.
2. Backend solicita a LLaMA/Ollama generar JSON de items SCT.
3. Frontend presenta vineta, hipotesis, nueva informacion y escala.
4. El estudiante responde.
5. La UI calcula puntaje y muestra explicacion por item.
6. Los tests pueden guardarse y luego cargarse desde la biblioteca.

Pendiente:

- Persistencia individual de intentos por estudiante.
- Puntajes centralizados por usuario.
- Historial SCT institucional.
- Rubricas o revision docente de respuestas.
- Mayor control de calidad de items generados.

Tabla de evidencia del apartado 4.3.11:

| Apartado | Componente implementado | Tecnologia/herramienta usada | Evidencia tecnica disponible | Evidencia visual sugerida | Validacion o prueba realizada | Estado actual | Limitaciones o pendiente |
|---|---|---|---|---|---|---|---|
| 4.3.11 A | Chatbot | React + FastAPI + Ollama | `ChatbotPage.jsx`, `chat.py` | Conversacion educativa | Prueba manual recomendada | Implementado/parcial | Hilos completos en localStorage. |
| 4.3.11 A | Filtro de alcance medico | Prompt + Ollama JSON | `_classify_medical_scope` | Consulta no medica rechazada | `test_chat_prompt.py` | Implementado | Depende del modelo local. |
| 4.3.11 A | RAG en chat | Casos + documentos | `retrieve_rag_hits`, `build_rag_context` | Respuesta con fuentes | Prueba RAG recomendada | Implementado/parcial | Mejorar citacion y evaluacion de fuentes. |
| 4.3.11 B | Generacion SCT | Ollama LLaMA 3 | `sct.py`, `SCT_SYSTEM_PROMPT` | Formulario generar SCT | Prueba manual recomendada | Implementado/parcial | Modelo hardcodeado en `sct.py`. |
| 4.3.11 B | Resolucion SCT | React | `SCTPage.jsx`, `SCTSection.jsx` | Test respondido con puntaje | Build Vite exitoso | Implementado/parcial | Intentos no persistidos en DB. |
| 4.3.11 B | Banco SCT | PostgreSQL JSON | `SCTTest`, endpoints SCT | Listado y detalle de tests | Prueba API recomendada | Implementado | Falta versionado/autor/propietario. |

## Lista consolidada de capturas recomendadas para Capitulo IV

### 4.3.4 Front-End

- Figura 4.X. Pagina inicial publica de ASOFAMECH.
- Figura 4.X. Interfaz de inicio de sesion.
- Figura 4.X. Formulario de registro con cuenta pendiente de aprobacion.
- Figura 4.X. Dashboard principal con modulos educativos.
- Figura 4.X. Sidebar con control visual por rol.
- Figura 4.X. Panel de configuracion con pestanas administrativas.

### 4.3.5 Back-End

- Figura 4.X. Documentacion Swagger/OpenAPI de FastAPI.
- Figura 4.X. Consola de Uvicorn con backend iniciado.
- Figura 4.X. Respuesta del endpoint `/health`.
- Figura 4.X. Respuesta autenticada de `/api/auth/me`.

### 4.3.6 Base de Datos

- Figura 4.X. Contenedor PostgreSQL/pgvector en Docker.
- Figura 4.X. Tablas principales en cliente SQL.
- Figura 4.X. Registro de usuario aprobado.
- Figura 4.X. Registro de sesion histopatologica con `trace_id`.
- Figura 4.X. Documento RAG con chunks indexados.

### 4.3.7 Visor Histopatologico

- Figura 4.X. Biblioteca de imagenes histopatologicas.
- Figura 4.X. Importacion local de lamina CAMELYON17.
- Figura 4.X. Visor OpenSeadragon con lamina DZI.
- Figura 4.X. Zoom progresivo sobre imagen histopatologica.

### 4.3.8 ROI

- Figura 4.X. Seleccion de ROI 1.
- Figura 4.X. Seleccion de ROI 2 dentro de ROI 1.
- Figura 4.X. Resultado educativo con coordenadas y `trace_id`.
- Figura 4.X. Historial de sesiones ROI.

### 4.3.9 Modelo Visual

- Figura 4.X. Estado del modelo histopatologico.
- Figura 4.X. Resultado ROI clasificado como metastasico/no metastasico.
- Figura 4.X. Resultado ROI no evaluable por estroma o baja calidad.
- Figura 4.X. Heatmap educativo por ROI.
- Figura 4.X. Mapa preparado con nombre y nota docente.

### 4.3.10 RAG

- Figura 4.X. Panel de documentos RAG.
- Figura 4.X. Estado de integracion RAG, pgvector y embeddings.
- Figura 4.X. Documento RAG creado.
- Figura 4.X. Respuesta del chatbot apoyada en fuentes cargadas.

### 4.3.11 Chatbot y SCT

- Figura 4.X. Interfaz del chatbot educativo.
- Figura 4.X. Respuesta educativa con advertencia no diagnostica.
- Figura 4.X. Generacion de test SCT.
- Figura 4.X. Test SCT respondido por estudiante.
- Figura 4.X. Retroalimentacion y puntaje SCT.
- Figura 4.X. Gestion de tests SCT en configuracion.

## Lista consolidada de pruebas y evidencias de ejecucion

| Evidencia | Comando o accion | Resultado esperado |
|---|---|---|
| Build frontend | `npm.cmd run build` en `frontend` | Build exitoso; advertencia de bundle grande aceptada. |
| Backend corriendo | `docker compose up backend db ollama` o servicio local Uvicorn | Consola sin errores criticos. |
| Swagger/OpenAPI | Abrir `http://localhost:8001/docs` | Ver routers por modulo. |
| Pytest | `backend/.venv/Scripts/python.exe -m pytest tests -q` | 126 pruebas aprobadas. |
| Login | Registrar, aprobar y entrar | Token guardado y acceso a dashboard. |
| Aprobacion usuario | Crear usuario pendiente y aprobar desde admin | Cambio a `approved`, correo/outbox. |
| Carga imagen | Subir JPG/PNG/TIFF/SVS | Registro en biblioteca. |
| Importacion CAMELYON17 | Importar lamina local | Imagen aparece sin subir GB por navegador. |
| Visor | Abrir imagen con DZI | OpenSeadragon muestra zoom/pan. |
| ROI | Seleccionar ROI 1 y ROI 2 | Coordenadas visibles y validas. |
| Inferencia IA | Analizar ROI 2 | Resultado con clase, probabilidad, QC y `trace_id`. |
| Heatmap | Generar mapa de ROI 1 | Job con progreso y overlay por tiles. |
| Chatbot | Enviar consulta medica | Respuesta educativa y log en backend. |
| RAG | Crear documento y preguntar sobre el tema | Respuesta con contexto recuperado. |
| SCT | Generar, responder y guardar test | Items, puntaje y test en listado. |
| Persistencia | Recargar sesion/imagen | Historial ROI y documentos se mantienen. |

## Flujo general de implementacion del sistema

1. El usuario accede a la plataforma web desde el navegador.
2. El usuario se registra o inicia sesion.
3. Si la cuenta esta pendiente, el administrador debe aprobarla.
4. Al aprobarse, el usuario recibe autorizacion de acceso y puede ingresar.
5. El dashboard presenta los modulos principales: asistente IA, SCT e imagenes IA.
6. En el chatbot, el usuario formula una consulta medica educativa.
7. El backend filtra alcance, recupera contexto RAG/casos y consulta Ollama.
8. En SCT, el usuario genera o carga un test, responde items y recibe retroalimentacion.
9. En imagenes, el usuario selecciona una lamina DZI.
10. El visor carga tiles y permite navegar con zoom/pan.
11. El usuario define ROI 1 y ROI 2.
12. El backend valida coordenadas y extrae el patch.
13. El sistema aplica QC y, si corresponde, ejecuta CONCH/PyTorch.
14. Se devuelve una prediccion educativa con probabilidades y advertencia no diagnostica.
15. Se registra la sesion con `trace_id`.
16. Docentes/admin pueden preparar heatmaps, revisar sesiones y corregir resultados para dataset futuro.

## Decisiones tecnicas principales

| Decision | Justificacion |
|---|---|
| React/Vite | Permite construir SPA modular, rapida de iterar y con build liviano para prototipo. |
| FastAPI | Facilita endpoints REST, documentacion Swagger automatica, tipado y validacion Pydantic. |
| PostgreSQL | Motor robusto para usuarios, SCT, documentos, sesiones ROI y trazabilidad. |
| pgvector | Permite busqueda vectorial documental en la misma base de datos. |
| Docker Compose | Orquesta PostgreSQL, backend y Ollama en un entorno reproducible. |
| OpenSeadragon/DZI | Resuelve visualizacion de imagenes de alta resolucion sin cargar la lamina completa. |
| ROI 1 y ROI 2 | Reduce carga computacional y permite separar contexto amplio de patch especifico de inferencia. |
| CONCH/PyTorch | CONCH aporta embeddings histopatologicos especializados; PyTorch permite cabezas entrenables. |
| Modelo congelado | Reduce costo de entrenamiento y riesgo de sobreajuste; solo se entrena clasificador sobre embeddings. |
| Ollama/LLaMA | Permite IA generativa local, controlable y sin depender necesariamente de APIs externas. |
| RAG | Reduce respuestas genericas al incorporar documentos y casos propios de la plataforma. |
| SCT | Se alinea con evaluacion de razonamiento clinico y permite retroalimentacion educativa estructurada. |

## Redaccion academica base para el informe

### 4.3.4. Implementacion del Front-End

El front-end de ASOFAMECH se implemento como una aplicacion web de pagina unica desarrollada con React y Vite. Esta decision permitio construir una interfaz modular, con rutas diferenciadas para la pagina publica, autenticacion, dashboard, asistente educativo, modulo SCT, visor histopatologico y paneles administrativos. La navegacion se estructuro mediante React Router DOM, mientras que los componentes visuales se organizaron en carpetas de paginas y componentes reutilizables.

La interfaz considera distintos perfiles de usuario. En la capa visual, el sidebar presenta u oculta opciones segun el rol del usuario, permitiendo que estudiantes accedan a los modulos formativos y que profesores o administradores accedan a configuracion, gestion de imagenes, documentos RAG, usuarios, correo y tests SCT. Como decision de implementacion, el front-end mantiene parte del estado de experiencia en el navegador, como historial conversacional, metricas de uso y resultados SCT locales, mientras que las acciones criticas se comunican con el backend mediante endpoints protegidos.

La validacion tecnica del front-end se realizo mediante el proceso de build de Vite, el cual compilo correctamente la aplicacion. Como limitacion actual, el bundle principal supera 500 kB, por lo que una mejora futura es aplicar division de codigo por rutas para optimizar la carga inicial.

### 4.3.5. Implementacion del Back-End

El back-end se desarrollo con FastAPI, organizando la logica en routers por dominio funcional. Esta estructura permite separar autenticacion, administracion, chatbot, casos clinicos, SCT, imagenes medicas, RAG e histopatologia. El archivo principal configura CORS, expone un endpoint de salud, crea tablas de base de datos al inicio y registra los routers de la aplicacion.

La comunicacion con el front-end se realiza mediante endpoints REST que retornan respuestas JSON. Las rutas protegidas utilizan token Bearer y validacion de usuario desde base de datos. Para las funcionalidades de inteligencia artificial, el back-end se comunica con Ollama mediante httpx, mientras que el modulo histopatologico integra OpenSlide, PyTorch y servicios propios de inferencia.

La evidencia de implementacion incluye la documentacion Swagger/OpenAPI, el endpoint `/health`, las pruebas automatizadas del backend y la organizacion modular de routers. Durante la revision se ejecutaron 126 pruebas automatizadas con resultado exitoso. Como mejora futura se recomienda incorporar migraciones formales con Alembic y fortalecer pruebas de integracion completas.

### 4.3.6. Implementacion de la Base de Datos

La base de datos del prototipo utiliza PostgreSQL con SQLAlchemy como ORM. En el entorno Docker se utiliza una imagen con soporte pgvector, lo que permite extender la base relacional con busqueda vectorial para documentos academicos. Las entidades principales representan usuarios, imagenes medicas, casos clinicos, documentos RAG, logs de chat, configuraciones, tests SCT, sesiones histopatologicas y correcciones docentes.

La persistencia actual permite registrar usuarios aprobados o pendientes, almacenar metadata de imagenes, conservar tests SCT generados, guardar documentos y fragmentos para RAG, registrar intercambios de chatbot y almacenar sesiones ROI con coordenadas, probabilidades y trazabilidad mediante `trace_id`. Las correcciones docentes se almacenan como una entidad relacionada con las sesiones histopatologicas, permitiendo construir manifiestos para reentrenamiento futuro.

Como limitacion, los jobs asincronicos de heatmap viven en memoria y los resultados de heatmap se guardan en archivos JSON, no en tablas relacionales. Adicionalmente, los intentos SCT individuales por estudiante aun no cuentan con persistencia centralizada. Estas limitaciones se consideran parte del roadmap posterior.

### 4.3.7. Implementacion del Visor Histopatologico

El visor histopatologico se implemento usando OpenSeadragon para imagenes de alta resolucion servidas como DZI. Esta decision responde a la necesidad de navegar laminas histologicas de gran tamano sin transferir el archivo completo al navegador. El backend genera o sirve el manifiesto DZI y entrega tiles bajo demanda, apoyandose en OpenSlide para archivos WSI como SVS o TIFF.

El sistema permite cargar imagenes por navegador y tambien importar laminas CAMELYON17 ya descargadas localmente en el servidor. Esta ultima decision evita transferir archivos de varios gigabytes por HTTP, haciendo mas realista el flujo de trabajo con datos histopatologicos. En el front-end, el usuario selecciona una imagen de la biblioteca, el visor carga el DZI correspondiente y permite desplazamiento y zoom progresivo.

Las evidencias recomendadas para el informe incluyen capturas de la biblioteca de imagenes, el visor con una lamina cargada, el zoom sobre tejido histologico y el endpoint DZI funcionando. La limitacion principal es que el flujo depende de OpenSlide y de que la imagen tenga DZI disponible.

### 4.3.8. Implementacion del Modulo ROI

El modulo ROI permite delimitar una region amplia de exploracion y una subregion especifica para analisis con IA. La ROI 1 define el contexto de trabajo, mientras que la ROI 2 corresponde al patch que sera extraido y evaluado por el modelo. Esta separacion reduce la carga computacional y permite mantener un flujo pedagogico comprensible para el estudiante.

La seleccion se realiza en el visor OpenSeadragon y las coordenadas se transforman al sistema de referencia de la imagen original. El backend valida que las regiones no excedan los limites de la lamina, que ROI 2 este contenida en ROI 1 y que su tamano sea adecuado. Posteriormente se extrae el patch mediante OpenSlide o Pillow, se genera un `trace_id` y se registra la sesion.

La evidencia funcional incluye capturas de ROI 1, ROI 2, coordenadas, resultado educativo, patch de depuracion y registro del `trace_id`. El modulo se encuentra implementado para el flujo principal de analisis, aunque puede mejorar en edicion fina de ROI y herramientas pedagogicas de comparacion.

### 4.3.9. Implementacion del Modelo Visual CONCH/PyTorch

El modulo de analisis visual utiliza CONCH como extractor congelado de caracteristicas histopatologicas y una cabeza clasificadora entrenada sobre embeddings. Esta arquitectura permite aprovechar un modelo visual especializado sin reentrenar el backbone completo, reduciendo costos computacionales y haciendo viable el prototipo en un entorno local.

La inferencia se ejecuta sobre patches extraidos desde ROI 2. Antes de clasificar, el sistema aplica un control de calidad que detecta exceso de fondo blanco, baja proporcion de tejido, baja celularidad y predominio estromal. Si la region no es adecuada, el sistema se abstiene y entrega una recomendacion educativa en lugar de forzar una clase. Cuando la inferencia procede, se devuelven clase, confianza, probabilidades, metadatos del modelo y advertencia de uso no diagnostico.

El checkpoint activo corresponde a una cabeza 3-class sobre embeddings CONCH entrenada para distinguir tejido no metastasico, metastasico y estroma. Las etapas offline documentadas muestran evaluaciones con CAMELYON17 y XML oficiales. El modelo se declara educativo y no diagnostico, debido a que la validacion clinica formal y la revision por patologo no forman parte del alcance actual.

### 4.3.10. Implementacion del RAG y Retroalimentacion Educativa

El componente RAG se implemento para enriquecer las respuestas educativas con informacion cargada en la plataforma. El sistema permite registrar documentos, fragmentarlos, generar embeddings y recuperar contenido relevante frente a una consulta. Cuando pgvector esta disponible, la busqueda se realiza en PostgreSQL mediante vectores; en caso contrario, el sistema utiliza un mecanismo de similitud sobre embeddings almacenados como JSON.

El chatbot utiliza el contexto recuperado para construir una respuesta mas contextualizada. Ademas, existe un mecanismo complementario basado en casos clinicos activos, lo que permite incorporar informacion del banco de casos al prompt educativo. La configuracion administrativa permite activar o desactivar RAG, seleccionar modelo de embeddings y revisar el estado de integraciones.

El estado actual es funcional para texto cargado manualmente. Como trabajo futuro queda completar ingestion directa de PDF o URL, mejorar la citacion de fuentes y evaluar la calidad de recuperacion con un conjunto de preguntas de prueba.

### 4.3.11. Implementacion del Chatbot Educativo y Modulo SCT

El chatbot educativo se implemento como una interfaz conversacional conectada a un endpoint FastAPI que consulta Ollama/LLaMA. Antes de responder, el sistema puede clasificar si la consulta pertenece al ambito medico y rechazar solicitudes fuera de alcance. Cuando RAG esta activo, recupera documentos o casos pertinentes y los incorpora al prompt. Cada intercambio se registra en base de datos como evidencia de uso, mientras que el hilo conversacional se conserva en el navegador.

El modulo SCT permite generar pruebas de Script Concordance Test a partir de un tema, dificultad y cantidad de items. El backend solicita al modelo generativo una salida estructurada con vineta clinica, hipotesis, nueva informacion, respuesta esperada y explicacion. El estudiante responde usando una escala de -2 a +2 y la interfaz entrega puntaje y retroalimentacion por item.

Los tests generados pueden guardarse, listarse, abrirse y eliminarse logicamente desde el sistema. No obstante, la persistencia individual de intentos, respuestas y puntajes por estudiante sigue pendiente. Esta funcionalidad es relevante para una futura version orientada a seguimiento academico longitudinal.
