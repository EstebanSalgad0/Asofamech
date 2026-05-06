# Informe tecnico-operativo para Capitulo IV: Marco Operativo

Proyecto revisado: ASOFAMECH / MediChat  
Objetivo: identificar el estado real del prototipo, requerimientos, evidencias tecnicas y diagramas necesarios para el Marco Operativo de un trabajo de titulo.

## 1. Resumen tecnico general del proyecto

El repositorio contiene una plataforma web educativa orientada al aprendizaje medico con apoyo de inteligencia artificial. La aplicacion combina un frontend React/Vite, un backend FastAPI, una base de datos PostgreSQL, integracion con Ollama/LLaMA 3, un modulo de chatbot educativo, un modulo Script Concordance Test (SCT) y un modulo de visualizacion/anotacion de imagenes histologicas.

Modulos realmente presentes en el codigo:

| Modulo | Estado real | Evidencia | Observaciones |
|---|---:|---|---|
| Frontend React/Vite | Implementado | `frontend/src/app.jsx`, `frontend/src/pages/*`, `frontend/src/components/*` | Define rutas para landing, login simulado, dashboard, chatbot, SCT, imagenes y configuracion. |
| Backend FastAPI | Implementado/parcial | `backend/app/main.py`, `backend/app/routers/*` | Expone endpoints de chat, casos, SCT e imagenes medicas. |
| Base de datos PostgreSQL | Parcial | `backend/app/db.py`, `backend/app/models.py`, `docker-compose.yml` | Hay modelos SQLAlchemy y creacion automatica de tablas; no hay migraciones ni seed automatico. |
| Chatbot educativo IA | Parcial | `backend/app/routers/chat.py`, `frontend/src/pages/ChatbotPage.jsx` | Usa Ollama y prompt educativo; historial se guarda en `localStorage`. |
| RAG sobre casos clinicos | Parcial | `backend/app/routers/chat.py`, `backend/app/models.py`, `case1.json` a `case3.json` | Busca casos en tabla `cases`, pero los JSON de casos no se cargan automaticamente. |
| SCT | Implementado/parcial | `backend/app/routers/sct.py`, `frontend/src/pages/SCTPage.jsx`, `frontend/src/pages/ConfigPage.jsx` | Genera items con IA, permite resolver, guardar y administrar tests. No persiste respuestas por estudiante. |
| Visor histopatologico | Parcial | `frontend/src/pages/ImagesPage.jsx`, `MedicalImageViewer.jsx`, `OpenSeadragonViewer.jsx`, `backend/app/routers/medical_images.py` | Soporta carga/listado/visualizacion, Fabric y OpenSeadragon/DZI. |
| ROI/anotaciones | Parcial | `frontend/src/components/MedicalImageViewer.jsx` | Permite dibujar anotaciones en memoria y exportar JSON local; no hay persistencia backend. |
| Autenticacion/autorizacion | Parcial/simulada | `frontend/src/pages/AuthPage.jsx`, `medical_images.py:get_current_user` | Login con `localStorage`, roles editables en UI, backend usa usuario mock. |
| Docker | Parcial | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` | Compose levanta DB, backend y Ollama; no incluye servicio frontend aunque existe Dockerfile. |
| Pruebas | Pendiente | Busqueda de `*test*`, `*spec*` sin resultados | No hay suites unitarias, integracion ni E2E. |

Flujo tecnologico detectado:

`React/Vite` -> `FastAPI` -> `PostgreSQL` / `Ollama` / `filesystem uploads`  
`React` usa `localStorage` para login simulado, rol, metricas, actividad e historial de chat.

Verificacion ejecutada:

| Verificacion | Resultado |
|---|---|
| `npm.cmd run build` en `frontend` | Exitoso. Vite compilo 54 modulos y genero `dist`. Advertencia: chunk JS mayor a 500 kB. |
| `python -m compileall backend/app` | No ejecutado correctamente por bloqueo de acceso al lanzador `python.exe`/`py.exe` en el entorno. |

## 2. Estructura del repositorio

| Carpeta/archivo | Proposito | Modulo asociado | Observaciones |
|---|---|---|---|
| `backend/` | Servicio backend | API, DB, IA, imagenes, SCT | FastAPI con SQLAlchemy. |
| `backend/app/main.py` | Punto de entrada FastAPI | Backend | Configura CORS, crea tablas al inicio, monta routers y `/uploads`. |
| `backend/app/db.py` | Conexion a DB | Base de datos | Usa `DATABASE_URL`; default local PostgreSQL. |
| `backend/app/models.py` | Modelos SQLAlchemy | Persistencia | Define `User`, `MedicalImage`, `Case`, `Document`, `ChatLog`, `SCTTest`. |
| `backend/app/schemas.py` | Esquemas Pydantic | API/SCT/casos | Define DTOs de casos y SCT. No hay schemas para imagenes ni auth. |
| `backend/app/routers/chat.py` | Endpoint chatbot | IA/RAG | Llama a Ollama y agrega contexto desde `Case`. |
| `backend/app/routers/cases.py` | Endpoints de casos | Casos clinicos/RAG | Lista, crea y busca casos. |
| `backend/app/routers/sct.py` | Endpoints SCT | SCT/IA | Genera, guarda, lista, obtiene y elimina tests SCT. |
| `backend/app/routers/medical_images.py` | Endpoints imagenes | Visor histologico | Upload, listado, vista, descarga, DZI y tiles. |
| `backend/requirements.txt` | Dependencias Python | Backend | Incluye FastAPI, SQLAlchemy, httpx, OpenSlide y Pillow. |
| `backend/Dockerfile` | Imagen backend | Despliegue | Instala `openslide-tools` y ejecuta Uvicorn. |
| `backend/uploads/` | Almacenamiento local | Imagenes | Contiene carpetas `medical_images` y `dzi_tiles`; ignorado por Git. |
| `frontend/` | Aplicacion web | Frontend | React 18 + Vite. |
| `frontend/src/app.jsx` | Router principal | Navegacion | Rutas publicas y dashboard. |
| `frontend/src/api.js` | Cliente API | Frontend-backend | Usa `VITE_API_BASE` para chat/SCT; no incluye funciones para casos/imagenes. |
| `frontend/src/pages/` | Pantallas principales | UI | Landing, auth, dashboard, chatbot, SCT, imagenes, configuracion. |
| `frontend/src/components/` | Componentes reutilizables | UI, visor, SCT | Incluye visor Fabric, OpenSeadragon, SCT selector, chat simple. |
| `frontend/src/tracker.js` | Metricas locales | Dashboard | Persiste consultas, tiempo, tests y actividad en `localStorage`. |
| `frontend/src/styles.css` | Estilos globales | UI | Archivo grande que cubre landing, dashboard, chat, SCT, visor y config. |
| `frontend/package.json` | Dependencias JS | Frontend | React, React Router, OpenSeadragon, Fabric, Vite. |
| `frontend/Dockerfile` | Imagen frontend | Despliegue | Ejecuta `npm run dev`; no esta integrado en `docker-compose.yml`. |
| `docker-compose.yml` | Orquestacion | DB, backend, Ollama | No define contenedor frontend. Usa volumenes `db_data`, `ollama_data`. |
| `case1.json`, `case2.json`, `case3.json` | Casos clinicos TB | Casos/RAG | No existe script de carga automatica a PostgreSQL. |
| `README.md` | Documentacion general | Proyecto | Declara arquitectura completa; algunas afirmaciones exceden estado real. |
| `DEV_SETUP.md` | Guia desarrollo local | Ejecucion | Describe ejecucion local con Docker para DB/Ollama y procesos locales para frontend/backend. |
| `SCT_MODULE.md` | Documentacion SCT | SCT | Describe el modulo y su API; util para evidencia. |
| `openapi_temp.json` | OpenAPI temporal | API | Esta desactualizado: solo incluye `/health`, `/api/chat` y `/api/cases`. |

## 3. Arquitectura logica detectada

Arquitectura real:

| Capa/componente | Responsabilidad | Evidencia |
|---|---|---|
| Cliente web React | Interfaz, navegacion, estado local, consumo API | `frontend/src/app.jsx`, `pages/*`, `api.js` |
| Estado local navegador | Login simulado, rol, metricas, actividad, historial de chat | `AuthPage.jsx`, `tracker.js`, `ChatbotPage.jsx` |
| API FastAPI | Fachada backend y endpoints REST | `backend/app/main.py`, `routers/*` |
| Servicio de IA local | Generacion de respuestas chat y SCT | `chat.py`, `sct.py`, `docker-compose.yml` |
| Base de datos PostgreSQL | Persistencia de usuarios mock, imagenes, casos y tests SCT | `db.py`, `models.py` |
| Filesystem uploads | Almacenamiento de imagenes y tiles DZI | `medical_images.py`, `backend/uploads/` |
| Visor histologico | Visualizacion zoomable y anotaciones | `ImagesPage.jsx`, `OpenSeadragonViewer.jsx`, `MedicalImageViewer.jsx` |

Flujos principales:

1. Usuario accede a React en `localhost:3000`.
2. Login/registro se simula en frontend y se guarda en `localStorage`.
3. React consume FastAPI en `localhost:8001`.
4. Chat envia `POST /api/chat`; backend busca casos activos y consulta Ollama.
5. SCT envia `POST /api/sct/generate`; backend solicita a Ollama items JSON y los devuelve.
6. SCT guardado usa PostgreSQL mediante `SCTTest.items_json`.
7. Imagenes se suben via `POST /api/medical-images/upload`; se guardan en disco y se registra metadata en DB.
8. Para imagen SVS, backend intenta generar DZI con OpenSlide; frontend usa OpenSeadragon si `has_dzi = true`.
9. Para imagen comun o preview SVS, frontend usa Fabric para zoom y anotaciones temporales/exportables.

Elementos que deben aparecer en el diagrama de arquitectura logica:

| Elemento | Tipo | Conexion |
|---|---|---|
| Navegador del estudiante/docente | Actor/cliente | Consume React |
| Aplicacion React/Vite | Frontend | Llama API FastAPI |
| `localStorage` | Almacenamiento cliente | Guarda sesion simulada, rol, actividad y conversaciones |
| API FastAPI | Backend | Expone endpoints REST |
| Router Chat | Modulo backend | Consulta PostgreSQL y Ollama |
| Router SCT | Modulo backend | Consulta Ollama y PostgreSQL |
| Router Medical Images | Modulo backend | Usa PostgreSQL, filesystem y OpenSlide |
| Router Cases | Modulo backend | Usa PostgreSQL |
| PostgreSQL | Base de datos | Tablas SQLAlchemy |
| Ollama/LLaMA 3 | Servicio IA local | `/api/chat` de Ollama |
| Volumen uploads | Almacenamiento archivos | Imagenes originales y DZI tiles |

## 4. Diagrama de contexto del sistema

Sistema central: Plataforma web educativa ASOFAMECH.

Actores externos:

| Actor | Relacion con el sistema | Evidencia/alcance |
|---|---|---|
| Estudiante de Medicina | Ingresa, consulta chatbot, resuelve SCT, visualiza imagenes y realiza anotaciones | Rutas `/dashboard`, `/dashboard/chat`, `/dashboard/sct`, `/dashboard/images` |
| Docente/Profesor | Administra tests SCT e imagenes desde configuracion | `ConfigPage.jsx` con rol `Profesor` |
| Administrador | Sube/elimina imagenes y administra SCT | `ConfigPage.jsx`, `medical_images.py` |
| Servicio Ollama | Genera respuestas educativas y items SCT | `chat.py`, `sct.py` |
| Base PostgreSQL | Persiste datos del prototipo | `models.py`, `db.py` |
| Filesystem local | Guarda imagenes y tiles | `medical_images.py` |

Relaciones para el diagrama:

| Origen | Destino | Relacion |
|---|---|---|
| Estudiante | Plataforma web | Navega, consulta, responde, anota |
| Docente/Administrador | Plataforma web | Gestiona imagenes y tests |
| Plataforma web | API FastAPI | Solicitudes HTTP REST |
| API FastAPI | PostgreSQL | Lectura/escritura de entidades |
| API FastAPI | Ollama | Solicitud de inferencia IA |
| API FastAPI | Filesystem uploads | Guarda/lee imagenes y tiles |
| Plataforma web | `localStorage` | Persistencia local no centralizada |

## 5. Casos de uso reales y esperados

| Actor | Caso de uso | Descripcion | Modulo | Estado | Evidencia |
|---|---|---|---|---:|---|
| Visitante | Ver landing page | Consulta informacion general del proyecto | Frontend | Implementado | `LandingPage.jsx` |
| Usuario | Iniciar sesion/registrarse | Guarda usuario en `localStorage` y navega al dashboard | Auth | Parcial | `AuthPage.jsx` |
| Estudiante | Ver dashboard | Revisa modulos, metricas y actividad local | Dashboard | Implementado/parcial | `DashboardPage.jsx`, `tracker.js` |
| Estudiante | Consultar chatbot | Envia pregunta y recibe respuesta educativa IA | Chatbot | Parcial | `ChatbotPage.jsx`, `chat.py` |
| Estudiante | Guardar historial de chat | Guarda conversaciones en navegador | Chatbot | Implementado local | `ChatbotPage.jsx` |
| Estudiante | Buscar apoyo en casos RAG | Backend busca casos relacionados en DB | Chat/RAG | Parcial | `chat.py`, `Case` |
| Docente | Crear caso clinico por API | Crea registro en tabla `cases` | Casos | Implementado API | `cases.py` |
| Estudiante/Docente | Listar/buscar casos | Consulta casos activos | Casos | Implementado API | `cases.py` |
| Estudiante | Generar test SCT con IA | Configura numero, dificultad y enfoque | SCT | Implementado/parcial | `SCTPage.jsx`, `sct.py` |
| Estudiante | Resolver test SCT | Responde escala -2 a +2 y obtiene resultado | SCT | Implementado local | `SCTPage.jsx` |
| Estudiante/Docente | Guardar/cargar test SCT | Persiste test generado en PostgreSQL | SCT | Implementado | `sct.py`, `SCTTest` |
| Docente/Admin | Administrar tests SCT | Lista, visualiza y elimina tests | Config/SCT | Implementado/parcial | `ConfigPage.jsx`, `sct.py` |
| Estudiante | Visualizar imagen histologica | Selecciona imagen de biblioteca o archivo local | Imagenes | Parcial | `ImagesPage.jsx` |
| Docente/Admin | Subir imagen medica | Carga JPG/PNG/TIFF/SVS con metadata | Imagenes | Implementado/parcial | `ConfigPage.jsx`, `medical_images.py` |
| Estudiante | Hacer anotaciones/ROI | Dibuja rectangulo, circulo o poligono | ROI | Parcial | `MedicalImageViewer.jsx` |
| Estudiante | Exportar anotaciones | Descarga JSON local de anotaciones | ROI | Implementado local | `MedicalImageViewer.jsx` |
| Sistema | Generar DZI para SVS | Procesa SVS con OpenSlide y tiles | Visor | Parcial | `process_svs_to_dzi` |
| Admin | Configurar IA | Pantalla declara futura configuracion | IA | Pendiente | `ConfigPage.jsx` tab `ai` |

## 6. Historias de usuario

| Historia | Criterio de aceptacion | Modulo | Prioridad | Estado |
|---|---|---|---:|---:|
| Como estudiante, quiero iniciar sesion para acceder a los modulos educativos. | Al enviar email/password se crea sesion local y se abre dashboard. | Auth | Alta | Parcial |
| Como estudiante, quiero consultar a un asistente medico educativo para resolver dudas formativas. | El sistema envia la pregunta a `/api/chat` y muestra respuesta con aviso educativo. | Chatbot | Alta | Parcial |
| Como estudiante, quiero guardar conversaciones para revisarlas despues. | La conversacion queda disponible en historial local y puede marcarse como guardada. | Chatbot | Media | Implementado local |
| Como estudiante, quiero generar un SCT por dificultad y enfoque para practicar razonamiento clinico. | Se genera un test con items, hipotesis, nueva informacion y respuesta esperada. | SCT | Alta | Implementado/parcial |
| Como estudiante, quiero responder items SCT y recibir retroalimentacion para mejorar mi razonamiento. | El sistema exige responder todos los items, calcula puntaje y muestra explicaciones. | SCT | Alta | Implementado local |
| Como docente, quiero guardar tests SCT para reutilizarlos con estudiantes. | El test se almacena en PostgreSQL y aparece en lista de tests guardados. | SCT | Alta | Implementado |
| Como docente, quiero administrar tests SCT para mantener un banco actualizado. | Se pueden listar, ver detalle y eliminar logicamente tests. | Config/SCT | Media | Implementado |
| Como estudiante, quiero visualizar imagenes histologicas con zoom para estudiar estructuras. | El visor muestra imagen seleccionada y permite zoom/pan. | Visor | Alta | Parcial |
| Como estudiante, quiero marcar regiones de interes para identificar hallazgos. | Se pueden dibujar anotaciones y verlas en el panel lateral. | ROI | Alta | Parcial |
| Como estudiante, quiero exportar mis anotaciones para dejar evidencia de mi analisis. | El sistema descarga un JSON con anotaciones, imagen y fecha. | ROI | Media | Implementado local |
| Como docente, quiero subir imagenes histologicas para construir una biblioteca educativa. | Se sube archivo, se registra metadata y aparece en la biblioteca. | Imagenes | Alta | Parcial |
| Como administrador, quiero controlar roles y permisos para proteger acciones administrativas. | Solo usuarios autorizados pueden administrar recursos. | Seguridad | Alta | Pendiente real; simulado |
| Como docente, quiero cargar casos clinicos para que el chatbot use contexto educativo. | Los casos se almacenan y se consideran en respuestas del chat. | Casos/RAG | Media | Parcial |

## 7. Requerimientos funcionales

| Codigo | Requerimiento | Descripcion | Modulo | Prioridad | Estado real | Evidencia | Observaciones |
|---|---|---|---|---:|---:|---|---|
| RF-01 | Acceso de usuario | Permitir ingreso/registro de usuario a la plataforma. | Auth | Alta | Parcial | `AuthPage.jsx` | No hay backend de auth, JWT ni hashing real. |
| RF-02 | Navegacion principal | Proveer rutas para landing, dashboard, chat, SCT, imagenes y config. | Frontend | Alta | Implementado | `app.jsx` | Control de acceso depende de `localStorage`. |
| RF-03 | Dashboard operativo | Mostrar modulos, metricas y actividad reciente. | Dashboard | Media | Implementado local | `DashboardPage.jsx`, `tracker.js` | Metricas no son centralizadas. |
| RF-04 | Consulta al chatbot | Enviar consulta medica educativa y mostrar respuesta IA. | Chatbot | Alta | Implementado/parcial | `ChatbotPage.jsx`, `chat.py` | Depende de Ollama activo. |
| RF-05 | Aviso educativo/no diagnostico | Informar que la respuesta no reemplaza atencion medica. | Chatbot/UI | Alta | Implementado | `chat.py`, `ChatbotPage.jsx`, `LandingPage.jsx` | Buen respaldo para enfoque etico. |
| RF-06 | Enriquecimiento por casos | Buscar casos clinicos relacionados para contextualizar respuesta. | RAG | Media | Parcial | `_build_cases_context` en `chat.py` | No hay seed automatico; si DB esta vacia no opera. |
| RF-07 | Gestion de casos clinicos | Listar, crear y buscar casos clinicos. | Casos | Media | Implementado API | `cases.py` | Sin UI principal activa; `CaseList` usa funcion inexistente. |
| RF-08 | Generacion SCT con IA | Generar items SCT segun numero, dificultad y enfoque. | SCT | Alta | Implementado/parcial | `sct.py`, `SCTPage.jsx` | Prompt extenso; modelo hardcodeado en `sct.py`. |
| RF-09 | Ejemplo SCT estatico | Entregar SCT de ejemplo sin IA. | SCT | Baja | Implementado API | `GET /api/sct/example` | No parece usado por `SCTPage.jsx`. |
| RF-10 | Resolucion SCT | Permitir responder escala -2 a +2. | SCT | Alta | Implementado local | `SCTPage.jsx` | Respuestas del estudiante no se guardan en DB. |
| RF-11 | Retroalimentacion SCT | Calcular puntaje y mostrar explicaciones. | SCT | Alta | Implementado local | `SCTPage.jsx` | Tolerancia +/-1 en pagina principal. |
| RF-12 | Persistencia de tests SCT | Guardar/listar/obtener/eliminar tests. | SCT | Alta | Implementado | `SCTTest`, `sct.py` | Items se guardan como JSON. |
| RF-13 | Biblioteca de imagenes | Listar imagenes medicas disponibles. | Imagenes | Alta | Implementado/parcial | `ImagesPage.jsx`, `medical_images.py` | Requiere imagenes cargadas en DB. |
| RF-14 | Carga de imagenes medicas | Subir SVS/JPG/PNG/TIFF con metadata. | Imagenes | Alta | Implementado/parcial | `ConfigPage.jsx`, `medical_images.py` | Permisos backend usan usuario mock admin. |
| RF-15 | Visualizacion de imagenes | Mostrar imagen con zoom/pan. | Visor | Alta | Parcial | `MedicalImageViewer.jsx`, `OpenSeadragonViewer.jsx` | Dos rutas: Fabric para imagen directa, OSD para DZI. |
| RF-16 | Procesamiento DZI | Generar y servir tiles DZI para SVS. | Visor | Media | Parcial | `process_svs_to_dzi`, endpoints DZI | Proceso sin cola ni background real; costoso para SVS grandes. |
| RF-17 | Seleccion ROI/anotaciones | Marcar regiones de interes. | ROI | Alta | Parcial | `MedicalImageViewer.jsx` | No persiste coordenadas en backend. |
| RF-18 | Exportacion de anotaciones | Descargar JSON con anotaciones. | ROI | Media | Implementado local | `handleExportAnnotations` | Evidencia local, no trazabilidad institucional. |
| RF-19 | Administracion de imagenes | Eliminar imagenes desde panel config. | Config | Media | Implementado/parcial | `ConfigPage.jsx`, `DELETE /api/medical-images/{id}` | Sin auth real. |
| RF-20 | Configuracion IA | Permitir configurar modelo/prompt/temperatura. | Config IA | Baja | Pendiente | `ConfigPage.jsx` placeholder | Pantalla dice "Proximamente". |
| RF-21 | Registro centralizado de chat | Guardar preguntas/respuestas en DB. | Chatbot | Media | Pendiente | `ChatLog` no usado | Modelo existe, no se escribe. |
| RF-22 | Registro de respuestas SCT por estudiante | Persistir intentos, puntajes y respuestas. | SCT | Alta | Pendiente | No hay modelo/endpoints | Necesario si se quiere trazabilidad academica. |

## 8. Requerimientos no funcionales

| Codigo | Requerimiento | Descripcion | Evidencia | Estado | Observaciones |
|---|---|---|---|---:|---|
| RNF-01 | Ejecucion local | El sistema debe poder ejecutarse localmente. | `DEV_SETUP.md`, `vite.config.js`, `db.py` | Parcial | Requiere servicios DB/Ollama activos. |
| RNF-02 | Contenerizacion | Servicios principales deben ejecutarse con Docker. | `docker-compose.yml`, Dockerfiles | Parcial | Compose no incluye frontend. |
| RNF-03 | Modularidad | Separacion frontend/backend/routers/modelos/componentes. | Estructura `backend/app`, `frontend/src` | Implementado | Buena base para descripcion arquitectonica. |
| RNF-04 | Mantenibilidad | Codigo organizado por routers y paginas. | `routers/*`, `pages/*` | Parcial | Falta capa de servicios y migraciones. |
| RNF-05 | Rendimiento en imagenes grandes | Usar tiles DZI para no cargar imagen completa. | OpenSeadragon, OpenSlide | Parcial | Generacion sincronica puede ser lenta. |
| RNF-06 | Seguridad de autenticacion | Controlar identidad y roles de usuarios. | `AuthPage.jsx`, `get_current_user` | Pendiente/parcial | Actualmente simulado y manipulable. |
| RNF-07 | Seguridad de contenido IA | Evitar uso diagnostico y riesgos de alucinacion. | Prompt y disclaimers | Parcial | Falta moderacion, limites, citas y trazabilidad. |
| RNF-08 | Sanitizacion frontend | Evitar inyeccion HTML desde respuestas del modelo. | `dangerouslySetInnerHTML` en `ChatbotPage.jsx` | Riesgo | Render markdown sin sanitizador robusto. |
| RNF-09 | Usabilidad | Interfaz con modulos claros, feedback, estados de carga. | `styles.css`, paginas | Implementado/parcial | UI completa, pero algunos textos/promesas son no demostradas. |
| RNF-10 | Trazabilidad educativa | Registrar actividad y progreso. | `tracker.js` | Parcial | Solo localStorage; no institucional. |
| RNF-11 | Documentacion | Mantener README, setup y modulo SCT. | `README.md`, `DEV_SETUP.md`, `SCT_MODULE.md` | Parcial | `openapi_temp.json` esta desactualizado. |
| RNF-12 | Escalabilidad | Separar servicios y persistencia. | FastAPI + DB + Ollama | Parcial | Ollama local y procesamiento DZI limitan escalado. |
| RNF-13 | Configurabilidad | Variables de entorno para DB/IA/API. | `DATABASE_URL`, `OLLAMA_URL`, `LLM_MODEL`, `VITE_API_BASE` | Parcial | Imagenes usan URLs hardcodeadas a `localhost:8001`. |
| RNF-14 | Portabilidad | Correr en Windows/local y Docker. | Dockerfiles y docs | Parcial | GPU NVIDIA en Compose puede fallar en equipos sin soporte. |
| RNF-15 | Testeabilidad | Existencia de pruebas automaticas. | Busqueda de tests | Pendiente | No hay pytest, Vitest ni E2E. |
| RNF-16 | Persistencia consistente | Mantener datos en DB y volumenes. | PostgreSQL, volumenes Docker | Parcial | No hay Alembic ni versionado de esquema. |
| RNF-17 | Caracter educativo/no diagnostico | El sistema debe declararse formativo. | README, Landing, prompt chat | Implementado | Importante para redaccion del informe. |

## 9. Modelo de datos o DER

Modelo implementado en `backend/app/models.py`:

| Entidad | Atributos principales | Relaciones | Modulo que la utiliza |
|---|---|---|---|
| `User` | `id`, `email`, `name`, `password_hash`, `role`, `created_at` | 1:N con `MedicalImage` por `uploaded_images` | Imagenes; usuario mock |
| `MedicalImage` | `id`, `filename`, `original_filename`, `title`, `description`, `pathology_type`, `file_type`, `file_size`, `file_path`, `dzi_path`, `uploaded_by`, `created_at`, `is_active` | N:1 con `User` por `uploaded_by` | Visor/imagenes |
| `Case` | `id`, `title`, `description`, `body`, `is_active` | Sin FK | Casos/RAG/chat |
| `Document` | `id`, `title`, `content`, `tags` | Sin FK | No usado actualmente |
| `ChatLog` | `id`, `user_id`, `question`, `answer`, `created_at` | Sin FK formal | No usado actualmente |
| `SCTTest` | `id`, `name`, `difficulty`, `focus`, `num_items`, `items_json`, `created_at`, `is_active` | Sin FK | SCT |

Relaciones DER reales:

1. `users.id` 1:N `medical_images.uploaded_by`.
2. `cases` es tabla independiente usada por busqueda RAG.
3. `sct_tests` almacena los items en un campo JSON; no existe tabla `sct_items`.
4. `documents` y `chat_logs` existen como modelo, pero no tienen flujo funcional activo.

Entidades que deberian agregarse si el DER representara el prototipo formativo completo:

| Entidad propuesta | Motivo | Atributos sugeridos |
|---|---|---|
| `RegionInterest` / `RegionInteres` | Persistir ROI/anotaciones | `id`, `image_id`, `user_id`, `type`, `coordinates_json`, `label`, `created_at` |
| `SCTAttempt` / `RespuestaSCT` | Registrar intentos de estudiante | `id`, `test_id`, `user_id`, `score`, `started_at`, `finished_at` |
| `SCTAnswer` | Guardar respuesta por item | `id`, `attempt_id`, `item_id`, `selected_value`, `expected_value`, `is_correct` |
| `ChatInteraction` | Usar `ChatLog` con FK real | `id`, `user_id`, `question`, `answer`, `model`, `created_at` |
| `EducationalCaseImage` | Relacionar casos e imagenes | `case_id`, `image_id`, `description` |

## 10. Diagrama de clases conceptual

Clases conceptuales recomendadas para UML, distinguiendo codigo real y clases de dominio necesarias:

| Clase | Origen | Atributos/metodos relevantes | Relaciones |
|---|---|---|---|
| `Usuario` | Real (`User`) | `email`, `name`, `password_hash`, `role` | Superclase conceptual de estudiante/docente/admin |
| `Estudiante` | Conceptual | `progreso`, `historialConsultas`, `intentosSCT` | Especializa `Usuario` |
| `Docente` | Conceptual | `crearTestSCT()`, `subirImagen()` | Especializa `Usuario` |
| `Administrador` | Conceptual/real por rol | `gestionarImagenes()`, `gestionarTests()` | Especializa `Usuario` |
| `CasoEducativo` | Real (`Case`) | `title`, `description`, `body`, `is_active` | Puede asociarse a chatbot/SCT/imagenes |
| `ImagenHistopatologica` | Real (`MedicalImage`) | `file_path`, `dzi_path`, `pathology_type`, `view()` | Pertenece a `Usuario` uploader |
| `RegionInteres` | Propuesta | `type`, `coordinates`, `label`, `created_at` | Pertenece a `ImagenHistopatologica` y `Usuario` |
| `TestSCT` | Real (`SCTTest`) | `name`, `difficulty`, `focus`, `items_json` | Contiene `PreguntaSCT` |
| `PreguntaSCT` | Real como JSON/Pydantic (`SCTItem`) | `vignette`, `hypothesis`, `new_info`, `correct_answer`, `explanation` | Parte de `TestSCT` |
| `RespuestaSCT` | Propuesta/frontend local | `selected_value`, `is_correct`, `score` | Pertenece a `Estudiante` y `PreguntaSCT` |
| `InteraccionChatbot` | Modelo parcial (`ChatLog`) | `question`, `answer`, `created_at` | Pertenece a `Usuario` |
| `ServicioIA` | Servicio backend conceptual | `generarRespuesta()`, `generarSCT()` | Usa Ollama/LLaMA 3 |
| `ServicioImagenes` | Router backend conceptual | `upload()`, `view()`, `generateDZI()` | Usa OpenSlide/filesystem/DB |

Relaciones principales para UML:

- `Usuario` 1:N `ImagenHistopatologica`.
- `ImagenHistopatologica` 1:N `RegionInteres` (propuesta).
- `TestSCT` 1:N `PreguntaSCT`.
- `Estudiante` 1:N `RespuestaSCT` (propuesta).
- `RespuestaSCT` N:1 `PreguntaSCT`.
- `Estudiante` 1:N `InteraccionChatbot`.
- `ServicioIA` depende de `Ollama`.
- `ServicioImagenes` depende de `OpenSlide` y `Filesystem`.

## 11. Diagrama de actividades

Flujo principal del estudiante:

1. Inicio.
2. El estudiante abre la plataforma.
3. Visualiza landing page.
4. Decide iniciar sesion o registrarse.
5. Ingresa credenciales.
6. El sistema valida de forma simulada y guarda usuario en `localStorage`.
7. El sistema muestra dashboard.
8. El estudiante selecciona modulo.
9. Decision: modulo seleccionado.
10. Si selecciona chatbot:
    - Escribe pregunta.
    - Frontend envia `POST /api/chat`.
    - Backend busca casos relacionados.
    - Decision: existen casos relacionados?
    - Si existen, agrega contexto al prompt.
    - Backend solicita respuesta a Ollama.
    - Decision: Ollama responde correctamente?
    - Si responde, frontend muestra respuesta y guarda conversacion local.
    - Si falla, frontend muestra mensaje de error.
11. Si selecciona imagenes:
    - Sistema lista imagenes disponibles.
    - Decision: hay imagenes disponibles?
    - Si no hay, muestra estado vacio.
    - Si hay, estudiante selecciona imagen.
    - Decision: imagen tiene DZI?
    - Si tiene DZI, usa OpenSeadragon.
    - Si no tiene DZI, usa Fabric/preview.
    - Estudiante navega con zoom/pan.
    - Decision: selecciona ROI?
    - Si si, dibuja anotacion.
    - Decision: exporta anotaciones?
    - Si si, descarga JSON local.
12. Si selecciona SCT:
    - Configura numero, dificultad y enfoque.
    - Solicita generacion IA.
    - Decision: IA genera items?
    - Si falla, muestra alerta.
    - Si genera, muestra test.
    - Estudiante responde items.
    - Decision: respondio todos?
    - Si no, sistema solicita completar.
    - Si si, calcula puntaje y muestra retroalimentacion.
    - Decision: guarda test?
    - Si si, envia `POST /api/sct/save`.
13. Fin con retroalimentacion/actividad registrada localmente.

## 12. Diagrama BPMN del proceso formativo

Pools requeridos:

1. Estudiante de Medicina.
2. Plataforma web educativa.
3. Servicios internos de backend/IA.

Descripcion BPMN textual:

| Paso | Pool origen | Actividad/mensaje | Pool destino | Resultado/decision |
|---|---|---|---|---|
| 1 | Estudiante | Accede a la plataforma | Plataforma web | Se carga landing page |
| 2 | Estudiante | Solicita iniciar sesion | Plataforma web | Formulario de acceso |
| 3 | Plataforma web | Valida sesion local | Plataforma web | Decision: usuario valido? |
| 4 | Plataforma web | Si no valido, muestra error o permanece en login | Estudiante | Reintento |
| 5 | Plataforma web | Si valido, muestra dashboard | Estudiante | Seleccion de modulo |
| 6 | Estudiante | Selecciona caso/modulo de estudio | Plataforma web | Decision: Chat, SCT o Imagenes |
| 7A | Estudiante | Envia consulta educativa | Plataforma web | Mensaje chat |
| 8A | Plataforma web | Solicita respuesta IA `POST /api/chat` | Servicios backend/IA | Backend busca contexto y llama Ollama |
| 9A | Servicios backend/IA | Devuelve respuesta educativa | Plataforma web | Decision: respuesta exitosa? |
| 10A | Plataforma web | Muestra respuesta o error | Estudiante | Retroalimentacion conversacional |
| 7B | Estudiante | Configura y solicita SCT | Plataforma web | Parametros SCT |
| 8B | Plataforma web | Solicita generacion `POST /api/sct/generate` | Servicios backend/IA | Backend llama Ollama |
| 9B | Servicios backend/IA | Devuelve items SCT | Plataforma web | Decision: items validos? |
| 10B | Plataforma web | Presenta test SCT | Estudiante | Respuestas en escala -2 a +2 |
| 11B | Estudiante | Envia respuestas SCT | Plataforma web | Calculo local de puntaje |
| 12B | Plataforma web | Muestra puntaje y explicaciones | Estudiante | Retroalimentacion formativa |
| 7C | Estudiante | Selecciona imagen histologica | Plataforma web | Solicitud de visualizacion |
| 8C | Plataforma web | Solicita imagen/tiles | Servicios backend/IA | Backend sirve archivo o DZI |
| 9C | Servicios backend/IA | Entrega imagen/tiles | Plataforma web | Render visor |
| 10C | Estudiante | Navega, hace zoom y marca ROI | Plataforma web | Anotacion local |
| 11C | Plataforma web | Exporta ROI local si corresponde | Estudiante | Evidencia descargable |
| 13 | Plataforma web | Registra actividad local | Plataforma web | Dashboard actualizado |
| 14 | Plataforma web | Presenta retroalimentacion final | Estudiante | Cierre del proceso formativo |

Compuertas BPMN sugeridas:

- Usuario autenticado localmente?
- Modulo seleccionado: Chat / SCT / Imagenes.
- Servicio IA disponible?
- Existen casos relacionados en DB?
- Imagen tiene DZI?
- Estudiante marca ROI?
- Estudiante responde todos los items SCT?
- Ocurre error tecnico?

## 13. Diagrama de despliegue local o Docker

Despliegue real detectado:

| Nodo/servicio | Tecnologia | Puerto | Volumen | Dependencias | Estado |
|---|---|---:|---|---|---:|
| `asofamech_db` | `postgres:15` | `5432:5432` | `db_data:/var/lib/postgresql/data` | Ninguna | Definido |
| `asofamech_backend` | Dockerfile Python/FastAPI | `8001:8001` | `./backend/app:/app/app`, `./backend/uploads:/app/uploads` | `db` | Definido |
| `asofamech_ollama` | `ollama/ollama:latest` | `11434:11434` | `ollama_data:/root/.ollama` | GPU NVIDIA opcional/declarada | Definido |
| Frontend local | Vite dev server | `3000` | N/A | Backend API | Documentado, no en Compose |
| Frontend Dockerfile | Node 20 Alpine | `3000` | N/A | N/A | Existe, no orquestado |

Variables relevantes:

| Variable | Uso | Evidencia |
|---|---|---|
| `DATABASE_URL` | Conexion backend a PostgreSQL | `db.py`, `docker-compose.yml` |
| `OLLAMA_URL` | URL de Ollama | `chat.py`, `sct.py`, `docker-compose.yml` |
| `LLM_MODEL` | Modelo chat | `chat.py` | 
| `VITE_API_BASE` | URL API frontend | `frontend/src/api.js`, docs |

Diagrama de despliegue recomendado:

1. Nodo "Equipo local del usuario".
2. Contenedor `frontend` opcional en puerto 3000 o proceso local `npm run dev`.
3. Contenedor `backend` en puerto 8001.
4. Contenedor `db` PostgreSQL en puerto 5432.
5. Contenedor `ollama` en puerto 11434.
6. Volumen `db_data`.
7. Volumen `ollama_data`.
8. Carpeta montada `backend/uploads`.
9. Red Docker interna entre backend, db y ollama.

Observacion critica: `docker-compose.yml` no levanta frontend, aunque README indica arquitectura dockerizada completa.

## 14. API y endpoints backend

| Metodo | Ruta | Descripcion | Entrada esperada | Salida esperada | Modulo | Estado |
|---|---|---|---|---|---|---:|
| GET | `/health` | Healthcheck backend | Ninguna | `{"status":"ok"}` | Core | Implementado |
| POST | `/api/chat` | Consulta chatbot IA | JSON `{ "text": "..." }` | `{ "messages": [{ "text": "..." }] }` | Chatbot | Implementado/parcial |
| GET | `/api/cases` | Lista casos activos | Ninguna | Lista `CaseOut` | Casos | Implementado |
| POST | `/api/cases` | Crea caso clinico | `title`, `description`, `body` | `CaseOut` | Casos | Implementado |
| GET | `/api/cases/search?q=&limit=` | Busca casos | Query `q`, `limit` | Lista `CaseOut` | Casos/RAG | Implementado |
| POST | `/api/sct/generate` | Genera items SCT con IA | `num_items`, `difficulty`, `focus` | `SCTResponse` | SCT/IA | Implementado/parcial |
| GET | `/api/sct/example` | Devuelve ejemplo SCT | Ninguna | `SCTResponse` | SCT | Implementado |
| POST | `/api/sct/save` | Guarda test SCT | `name`, `difficulty`, `focus`, `num_items`, `items` | `SCTTestOut` | SCT | Implementado |
| GET | `/api/sct/list` | Lista tests SCT activos | Ninguna | Lista `SCTTestOut` | SCT | Implementado |
| GET | `/api/sct/{test_id}` | Obtiene test SCT | Path `test_id` | `SCTTestDetail` | SCT | Implementado |
| DELETE | `/api/sct/{test_id}` | Soft-delete de SCT | Path `test_id` | Mensaje e id | SCT | Implementado |
| POST | `/api/medical-images/upload` | Sube imagen medica | Multipart: `file`, `title`, `description`, `pathology_type` | Metadata y mensaje | Imagenes | Implementado/parcial |
| GET | `/api/medical-images/list` | Lista imagenes activas | Ninguna | Lista de metadata | Imagenes | Implementado |
| GET | `/api/medical-images/view/{image_id}` | Sirve imagen/preview | Path `image_id` | Archivo/stream imagen | Visor | Implementado/parcial |
| GET | `/api/medical-images/download/{image_id}` | Descarga imagen original | Path `image_id` | Archivo | Imagenes | Implementado |
| DELETE | `/api/medical-images/{image_id}` | Elimina imagen y archivos | Path `image_id` | Mensaje | Imagenes | Implementado/parcial |
| GET | `/api/medical-images/dzi/{image_id}.dzi` | Sirve manifiesto DZI | Path `image_id` | XML DZI | Visor DZI | Implementado/parcial |
| GET | `/api/medical-images/dzi/{image_id}_files/{level}/{col}_{row}.{fmt}` | Sirve tile DZI | Path level/col/row/fmt | Tile imagen | Visor DZI | Implementado/parcial |
| GET | `/api/medical-images/info/{image_id}` | Obtiene detalle de imagen | Path `image_id` | Metadata extendida | Imagenes | Implementado |

Endpoints que deberian capturarse en FastAPI `/docs`:

- `/api/chat`
- `/api/sct/generate`
- `/api/sct/save`
- `/api/sct/list`
- `/api/medical-images/upload`
- `/api/medical-images/list`
- `/api/medical-images/view/{image_id}`
- `/api/cases`
- `/api/cases/search`

Observacion: `openapi_temp.json` no representa la API actual completa.

## 15. Frontend y pantallas del sistema

| Pantalla/componente | Proposito | Ruta | Modulo | Estado | Captura sugerida |
|---|---|---|---|---:|---|
| `LandingPage` | Presentacion publica | `/` | Landing | Implementado | Portada y disclaimer educativo |
| `AuthPage` | Login/registro simulado | `/auth` | Auth | Parcial | Formulario login/registro |
| `DashboardPage` | Inicio post-login, metricas, modulos | `/dashboard` | Dashboard | Implementado/parcial | Tarjetas de modulos y actividad |
| `ChatbotPage` | Chat IA con historial | `/dashboard/chat` | Chatbot | Parcial | Conversacion con respuesta IA y aviso |
| `SCTPage` | Generar/resolver/ver resultados SCT | `/dashboard/sct` | SCT | Implementado/parcial | Configuracion, test y resultados |
| `ImagesPage` | Biblioteca y visor histologico | `/dashboard/images` | Visor | Parcial | Lista, visor, anotaciones |
| `ConfigPage` | Gestion imagenes/SCT/config IA | `/dashboard/config` | Admin | Parcial | Tabs imagenes, SCT, IA placeholder |
| `MedicalImageViewer` | Visor Fabric para imagenes no DZI | Componente | Visor/ROI | Parcial | Zoom + panel anotaciones |
| `OpenSeadragonViewer` | Visor DZI | Componente | Visor | Parcial | Imagen deep zoom si existe DZI |
| `SCTSection`, `ChatSection`, `ChatPage`, `HeroSection`, `Footer`, `FeaturesSection` | Componentes/paginas previas o no ruteadas | No activas en `app.jsx` | Legacy/UI | No usados en flujo principal | No usar como evidencia central |

Capturas recomendadas:

1. Landing page con aviso educativo.
2. Login/registro.
3. Dashboard con modulos.
4. Chatbot con pregunta/respuesta y disclaimer.
5. Configuracion SCT antes de generar.
6. Test SCT en ejecucion con escala -2 a +2.
7. Resultados SCT con retroalimentacion.
8. Biblioteca de imagenes.
9. Visor histologico con zoom.
10. Anotacion/ROI en visor y panel lateral.
11. Panel de configuracion para subida de imagenes.
12. Panel de administracion SCT.
13. Tab de IA "Proximamente" como evidencia de pendiente.

## 16. Modulo de visor histopatologico

Estado real:

| Capacidad | Estado | Evidencia | Observacion |
|---|---:|---|---|
| Listar imagenes desde backend | Implementado | `GET /api/medical-images/list`, `ImagesPage.jsx` | Hardcodea `http://localhost:8001` en varias llamadas. |
| Cargar imagen local | Implementado local | `handleFileUpload` en `ImagesPage.jsx` | No persiste el archivo local. |
| Subir imagen a backend | Implementado/parcial | `ConfigPage.jsx`, `upload_medical_image` | Backend usa usuario mock admin. |
| Visualizar JPG/PNG/TIFF | Implementado/parcial | `MedicalImageViewer.jsx`, `/view/{id}` | Usa Fabric canvas. |
| Visualizar SVS | Parcial | `view_image` y `process_svs_to_dzi` | Preview y DZI dependen de OpenSlide. |
| Deep zoom DZI | Parcial | `OpenSeadragonViewer.jsx`, endpoints DZI | Solo se usa si `has_dzi` es true. |
| Anotaciones sobre imagen | Parcial | `MedicalImageViewer.jsx` | No persistencia central. |
| Herramientas OSD de anotacion | Pendiente/parcial UI | `OpenSeadragonViewer.jsx` | Botones existen, pero no implementan dibujo/guardado real. |

Evidencias a capturar:

- Pantalla de biblioteca con imagen cargada.
- Visor Fabric con zoom y anotacion.
- Si existe SVS procesado, visor OpenSeadragon con tiles DZI.
- Endpoint `/api/medical-images/list` en `/docs`.
- Carpeta `backend/uploads/medical_images` y `backend/uploads/dzi_tiles` si contienen datos de prueba.

Requerimientos respaldados: RF-13, RF-14, RF-15, RF-16, RF-17, RNF-05.

## 17. Modulo ROI

Estado: Parcial.

Implementado realmente:

- Herramientas de anotacion en `MedicalImageViewer.jsx`: seleccionar, rectangulo, circulo, poligono.
- Panel lateral de anotaciones.
- Eliminacion de anotaciones.
- Limpieza de todas las anotaciones.
- Exportacion local a JSON con `image`, `annotations` y `timestamp`.

No implementado:

- Tabla `RegionInteres`.
- Endpoint para crear/listar/actualizar/eliminar ROI.
- Persistencia de coordenadas en PostgreSQL.
- Asociacion formal ROI-imagen-usuario-caso.
- Reapertura de ROI guardadas.
- Anotaciones reales sobre OpenSeadragon/DZI.

Datos que deberian capturarse para ROI:

| Dato | Necesidad |
|---|---|
| `image_id` | Asociar ROI a imagen histopatologica |
| `case_id` | Asociar ROI a caso educativo, si aplica |
| `user_id` | Trazabilidad del estudiante/docente |
| `type` | Rectangulo, circulo, poligono, linea, texto |
| `coordinates_json` | Coordenadas normalizadas o en sistema de imagen |
| `label` | Nombre/descripcion de region |
| `pathology_tag` | Hallazgo esperado u observado |
| `created_at` | Fecha/hora de creacion |
| `updated_at` | Fecha/hora de modificacion |

## 18. Modulo SCT

Estado real: Implementado funcionalmente para generacion, resolucion local y administracion de tests; parcial para trazabilidad educativa.

Backend:

| Funcion | Endpoint/modelo | Estado |
|---|---|---:|
| Generar items con IA | `POST /api/sct/generate` | Implementado |
| Ejemplo estatico | `GET /api/sct/example` | Implementado |
| Guardar test | `POST /api/sct/save` + `SCTTest` | Implementado |
| Listar tests | `GET /api/sct/list` | Implementado |
| Obtener test | `GET /api/sct/{test_id}` | Implementado |
| Eliminar test | `DELETE /api/sct/{test_id}` | Implementado con soft-delete |

Frontend:

| Pantalla/componente | Funcion | Estado |
|---|---|---:|
| `SCTPage.jsx` | Configurar, generar, responder, calcular resultados, guardar | Implementado/parcial |
| `ConfigPage.jsx` | Gestionar tests, generar y guardar desde panel admin | Implementado/parcial |
| `SCTTestSelector.jsx` | Seleccionar tests guardados | Implementado, no central en ruta actual |
| `SCTSection.jsx` | Version alternativa/legacy de SCT | No usada en rutas actuales |

Limitaciones:

- No hay tabla de intentos/respuestas por estudiante.
- No se registra progreso historico centralizado.
- `items_json` no normaliza preguntas.
- La calidad depende de Ollama y del cumplimiento del JSON por el modelo.
- La pagina principal usa tolerancia de respuesta +/-1; debe justificarse si se reporta.
- No hay comparacion con panel de expertos real.

Evidencias:

- Captura de generacion SCT.
- Captura de item con viñeta/hipotesis/nueva informacion/escala.
- Captura de resultados con explicacion.
- FastAPI `/docs` con endpoints SCT.
- Registro en tabla `sct_tests` en PostgreSQL.

## 19. Chatbot educativo e integracion con IA

Funcionamiento detectado:

1. Frontend envia texto mediante `sendChatMessage` a `POST /api/chat`.
2. Backend valida mensaje no vacio.
3. Backend extrae tokens de la pregunta y busca coincidencias en `Case.title`, `Case.description` y `Case.body`.
4. Si encuentra casos, arma contexto RAG con maximo 3 casos.
5. Backend construye prompt de sistema educativo con aviso de no reemplazo clinico.
6. Backend llama a Ollama en `${OLLAMA_URL}/api/chat` usando `LLM_MODEL`, por defecto `llama3:8b`.
7. Frontend muestra la respuesta y guarda historial en `localStorage`.

Control educativo:

| Mecanismo | Evidencia | Estado |
|---|---|---:|
| Prompt de sistema formativo | `chat.py` | Implementado |
| Disclaimer visible | `ChatbotPage.jsx`, `LandingPage.jsx`, README | Implementado |
| Enfoque no diagnostico | Prompt y textos UI | Implementado/parcial |

Riesgos tecnicos/funcionales:

| Riesgo | Impacto | Recomendacion |
|---|---|---|
| Alucinaciones IA | Respuestas incorrectas o no verificadas | Incluir advertencias, referencias, curadoria y limites tematicos |
| Sin moderacion | Respuestas fuera de alcance | Agregar filtros/politicas de seguridad |
| `dangerouslySetInnerHTML` | Riesgo XSS si llega HTML malicioso | Usar sanitizador tipo DOMPurify o render markdown seguro |
| Casos RAG sin seed | RAG puede no aportar contexto | Crear script de carga para `case1.json`-`case3.json` |
| `ChatLog` no usado | Sin trazabilidad de consultas | Persistir interacciones anonimizadas o con consentimiento |
| Dependencia de Ollama local | Falla si modelo no esta descargado | Healthcheck de IA e instrucciones claras |
| Sin rate limiting | Sobrecarga o abuso | Agregar limites por usuario/IP |

## 20. Pruebas existentes y pruebas recomendadas

Pruebas existentes:

| Tipo | Evidencia | Estado |
|---|---|---:|
| Unitarias backend | No hay archivos `test_*.py` | Pendiente |
| Unitarias frontend | No hay Vitest/Jest | Pendiente |
| Integracion API | No hay scripts formales | Pendiente |
| E2E | No hay Playwright/Cypress | Pendiente |
| Build frontend | `npm.cmd run build` ejecutado | Exitoso con advertencia de chunk |
| OpenAPI docs | FastAPI genera `/docs`; `openapi_temp.json` esta desactualizado | Parcial |

Pruebas recomendadas:

| Prueba | Objetivo | Requerimiento relacionado |
|---|---|---|
| Test unitario `_build_cases_context` | Verificar busqueda y truncado de casos | RF-06 |
| Test API `/api/chat` con Ollama mock | Validar contrato `{messages:[...]}` y errores | RF-04, RNF-07 |
| Test API `/api/cases` | Crear, listar y buscar casos | RF-07 |
| Test API `/api/sct/generate` con respuesta IA mock | Validar parseo JSON y errores | RF-08 |
| Test API `/api/sct/save/list/get/delete` | Verificar persistencia y soft-delete | RF-12 |
| Test upload imagen | Validar extensiones, metadata y archivo guardado | RF-14 |
| Test DZI | Verificar manifiesto y tile cuando existe DZI | RF-16 |
| Test componente `SCTPage` | Responder todos los items y mostrar resultados | RF-10, RF-11 |
| Test componente `MedicalImageViewer` | Dibujar y exportar anotaciones | RF-17, RF-18 |
| Test seguridad auth | Confirmar que acciones admin requieren token real cuando se implemente | RNF-06 |
| Test E2E flujo estudiante | Login, chat, SCT, visor | RF-01 a RF-18 |
| Test accesibilidad/usabilidad | Navegacion por teclado, contraste, estados vacios | RNF-09 |

## 21. Estado actual de implementacion

| Componente | Estado | Evidencia | Observaciones | Recomendacion |
|---|---:|---|---|---|
| Frontend | Implementado | `frontend/src/*` | Build exitoso; bundle grande | Code splitting y limpieza de componentes no usados |
| Backend | Implementado/parcial | `backend/app/*` | API funcional por routers | Agregar capa servicios, pruebas y manejo de errores |
| Base de datos | Parcial | `models.py`, `db.py` | Sin migraciones ni seed | Agregar Alembic y carga inicial de casos |
| Visor histopatologico | Parcial | `ImagesPage`, visores | Funciona para imagenes; DZI depende de procesamiento | Probar con imagen real y documentar limites |
| ROI | Parcial | `MedicalImageViewer.jsx` | Solo local/exportable | Persistir ROI en DB |
| SCT | Implementado/parcial | `sct.py`, `SCTPage`, `ConfigPage` | No persiste intentos | Agregar `SCTAttempt`/`SCTAnswer` |
| Chatbot | Parcial | `chat.py`, `ChatbotPage` | Sin logs DB, sin sanitizacion robusta | Persistencia, moderacion y sanitizacion |
| IA/Ollama | Parcial | `docker-compose`, `chat.py`, `sct.py` | Dependencia local y modelo | Healthcheck IA y configuracion modelo centralizada |
| Autenticacion | Parcial/simulada | `AuthPage`, `get_current_user` | No hay seguridad real | Implementar auth backend/JWT/roles |
| Pruebas | Pendiente | Sin archivos de test | Solo build manual | Crear suite minima |
| Docker | Parcial | `docker-compose.yml`, Dockerfiles | Compose sin frontend | Agregar servicio frontend o ajustar README |
| Documentacion | Parcial | README, DEV_SETUP, SCT_MODULE | Algunas promesas no implementadas | Actualizar segun estado real |
| Casos/RAG | Parcial | `cases.py`, `case*.json`, `chat.py` | JSON no se cargan automaticamente | Script seed y UI de gestion |
| Configuracion IA | Pendiente | `ConfigPage` placeholder | Solo pantalla futura | Implementar o marcar como planificado |

## 22. Lista de diagramas que debo construir

| Diagrama | Informacion exacta que debe contener |
|---|---|
| Diagrama de contexto | Actores: Estudiante, Docente, Administrador; sistema ASOFAMECH; servicios PostgreSQL, Ollama, filesystem; relaciones de uso/consulta/gestion. |
| Diagrama de casos de uso | Login simulado, consultar chatbot, resolver SCT, visualizar imagen, marcar ROI, exportar ROI, subir imagen, administrar SCT, crear/buscar casos. Marcar casos pendientes si corresponde. |
| Flujo de navegacion | `/`, `/auth`, `/dashboard`, `/dashboard/chat`, `/dashboard/sct`, `/dashboard/images`, `/dashboard/config`; redireccion por login local. |
| Diagrama de actividades | Flujo estudiante: ingreso, modulo, chat/SCT/visor, decisiones de error, ROI, retroalimentacion. |
| BPMN | Tres pools: Estudiante, Plataforma web, Servicios backend/IA. Mensajes HTTP y respuestas IA/DB. |
| Arquitectura logica | React, FastAPI routers, PostgreSQL, Ollama, uploads, OpenSlide, OpenSeadragon/Fabric, `localStorage`. |
| Diagrama de despliegue | Local/Docker: frontend 3000, backend 8001, db 5432, Ollama 11434, volumenes y uploads. Indicar frontend no incluido en Compose actual. |
| DER/modelo de datos | Tablas reales `users`, `medical_images`, `cases`, `documents`, `chat_logs`, `sct_tests`; y propuestas `regions_interest`, `sct_attempts`, `sct_answers`. |
| Diagrama de clases | Usuario, Estudiante, Docente, CasoEducativo, ImagenHistopatologica, RegionInteres, TestSCT, PreguntaSCT, RespuestaSCT, InteraccionChatbot, ServicioIA. |
| EDT/WBS | Analisis, diseno, frontend, backend, DB, IA, visor, SCT, chatbot, pruebas, documentacion, despliegue. |
| Cronograma | Fases: levantamiento, desarrollo modulos, integracion IA/DB, pruebas, documentacion, validacion con usuarios. |

## 23. Lista de evidencias y capturas que debo tomar

1. Repositorio raiz mostrando `backend`, `frontend`, `docker-compose.yml`, docs y JSON de casos.
2. `README.md` y `DEV_SETUP.md` como evidencia de instrucciones.
3. `docker-compose.yml` mostrando servicios DB, backend y Ollama.
4. Terminal con `npm.cmd run build` exitoso.
5. FastAPI `/docs` con endpoints chat, SCT, imagenes y casos.
6. Landing page de ASOFAMECH.
7. Pantalla de login/registro.
8. Dashboard con modulos y metricas.
9. Chatbot con pregunta y respuesta educativa.
10. Aviso de no diagnostico en chatbot/landing.
11. Configuracion de SCT con numero, dificultad y enfoque.
12. Pantalla de generacion SCT o loading.
13. Item SCT con viñeta, hipotesis, nueva informacion y escala.
14. Resultado SCT con puntaje y retroalimentacion.
15. Panel de tests SCT guardados.
16. Panel de configuracion de imagenes.
17. Modal de subida de imagen.
18. Biblioteca de imagenes histologicas.
19. Visor histopatologico con zoom.
20. Anotacion/ROI dibujada sobre imagen.
21. Exportacion JSON de anotaciones.
22. PostgreSQL con tablas creadas (`users`, `medical_images`, `cases`, `sct_tests`).
23. Carpeta `backend/uploads` con imagenes/tiles si se usa una muestra.
24. Tab configuracion IA "Proximamente" para evidenciar pendiente.
25. Logs de backend/Ollama durante consulta IA.
26. Evidencia de ausencia de pruebas o plan de pruebas recomendado.
27. Tablero Kanban o gestion del proyecto, si existe fuera del repositorio.

## 24. Observaciones criticas

| Observacion | Riesgo para el informe | Recomendacion de redaccion |
|---|---|---|
| Autenticacion real no existe | Sobredeclarar seguridad | Decir "login simulado/local" y "auth pendiente". |
| Roles son modificables en frontend | No hay control real de permisos | No declarar control de acceso robusto. |
| Backend de imagenes usa usuario admin mock | Acciones admin no protegidas | Presentarlo como prototipo tecnico. |
| Docker Compose no incluye frontend | Arquitectura dockerizada incompleta | Indicar despliegue local mixto o Compose parcial. |
| `openapi_temp.json` esta desactualizado | Evidencia API incorrecta | Usar `/docs` real de FastAPI, no ese archivo como fuente final. |
| Casos JSON no se cargan a DB | RAG puede no funcionar con contexto | Incluir como pendiente: seed/ingesta de casos. |
| `ChatLog` y `Document` no se usan | Modelo sobredimensionado | Marcar como modelos preliminares/no integrados. |
| ROI no persiste en backend | Trazabilidad de imagen incompleta | Decir "anotacion local/exportable", no "almacenamiento ROI". |
| OpenSeadragon tiene toolbar de anotacion sin logica real | Funcionalidad aparente | Evidenciar solo zoom DZI; ROI real esta en Fabric. |
| Configuracion IA es placeholder | No esta implementada | Marcar como futura mejora. |
| No hay pruebas automaticas | Calidad no verificable formalmente | Incluir plan de pruebas recomendado. |
| `dangerouslySetInnerHTML` para IA | Riesgo de seguridad | Recomendacion de sanitizacion. |
| URLs hardcodeadas a `localhost:8001` | Baja portabilidad | Usar `VITE_API_BASE` tambien en imagenes. |
| Modelo SCT hardcodeado en `sct.py` | Configuracion inconsistente | Usar `LLM_MODEL` de entorno. |
| Landing declara cifras como 1M+, 98%, +5K | Riesgo de evidencia no demostrada | No usarlas como resultados reales del prototipo. |
| Sin migraciones Alembic | Evolucion DB riesgosa | Recomendacion tecnica. |
| Procesamiento SVS sincronico | Puede bloquear backend | Usar cola/background tasks para produccion. |

## 25. Version resumida para pegar en el informe

La plataforma ASOFAMECH corresponde a un prototipo web educativo orientado al apoyo del aprendizaje medico mediante inteligencia artificial. Su arquitectura se organiza en un frontend desarrollado con React y Vite, un backend construido con FastAPI, una base de datos PostgreSQL y un servicio local de inteligencia artificial mediante Ollama/LLaMA 3. El sistema incorpora modulos de chatbot educativo, generacion y resolucion de Script Concordance Test (SCT), gestion de imagenes histologicas y visualizacion/anotacion de regiones de interes en imagenes medicas.

El frontend presenta una landing page, autenticacion simulada, dashboard de acceso a modulos, chatbot, modulo SCT, visor de imagenes y panel de configuracion. El backend expone endpoints REST para chat, casos clinicos, SCT e imagenes medicas. La base de datos implementa entidades para usuarios, imagenes medicas, casos, documentos, logs de chat y tests SCT, aunque algunas de ellas aun no se encuentran completamente integradas a los flujos funcionales. La integracion con IA se realiza a traves de Ollama, tanto para responder consultas educativas como para generar items SCT.

El estado actual del prototipo es funcional en sus flujos principales, pero con componentes relevantes en estado parcial. El chatbot opera con un prompt educativo y puede enriquecer respuestas con casos clinicos almacenados en PostgreSQL; sin embargo, los casos JSON incluidos en el repositorio no se cargan automaticamente. El modulo SCT permite generar, resolver, guardar, listar y eliminar tests, pero no registra intentos ni respuestas por estudiante. El visor histopatologico permite visualizar imagenes, utilizar zoom y realizar anotaciones locales; no obstante, la persistencia formal de regiones de interes en base de datos se encuentra pendiente.

Los requerimientos funcionales principales implementados o parcialmente implementados son: acceso al sistema, navegacion por dashboard, consulta al chatbot educativo, gestion de casos clinicos por API, generacion y resolucion de SCT, persistencia de tests SCT, carga y visualizacion de imagenes medicas, generacion/servicio de tiles DZI para imagenes SVS y anotacion local de regiones de interes. Entre los requerimientos no funcionales se identifican ejecucion local, modularidad, documentacion parcial, caracter educativo/no diagnostico, rendimiento mediante DZI, configurabilidad por variables de entorno y portabilidad parcial mediante Docker.

Las evidencias tecnicas disponibles incluyen la estructura del repositorio, archivos Docker, documentacion README/DEV_SETUP/SCT_MODULE, endpoints FastAPI, modelos SQLAlchemy, pantallas React, visor Fabric/OpenSeadragon, prompts de IA, carpetas de uploads y build frontend exitoso. Las principales limitaciones actuales son la ausencia de autenticacion real, falta de pruebas automaticas, ausencia de migraciones, Docker Compose incompleto para frontend, configuracion IA aun no implementada, no persistencia de ROI ni respuestas SCT por estudiante, y riesgos propios del uso de IA generativa sin moderacion ni validacion experta automatizada.

En consecuencia, para el Capitulo IV se recomienda presentar el sistema como un prototipo educativo funcional con modulos avanzados parcialmente integrados, evitando declarar como completamente implementadas las capacidades de autenticacion, trazabilidad academica, persistencia de ROI, despliegue Docker completo y validacion clinica. Los diagramas necesarios son: contexto, casos de uso, flujo de navegacion, actividades, BPMN, arquitectura logica, despliegue, DER/modelo de datos, clases conceptuales, EDT/WBS y cronograma.
