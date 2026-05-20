# Capitulo IV - Estado actualizado de implementacion ASOFAMECH

Documento de apoyo para los apartados 4.3.5 a 4.3.11 del informe de tesis.

Fecha de revision: 19-05-2026.

Alcance: revision del codigo fuente local del proyecto ASOFAMECH. Este documento evita pegar bloques extensos de codigo fuente y prioriza proceso de implementacion, decisiones tecnicas, flujo funcional, evidencias, pruebas, estado actual y limitaciones.

Nota de consistencia: existen componentes experimentales asociados a revision/correccion docente de sesiones histopatologicas. Para el informe actual no deben presentarse como funcionalidad activa del prototipo ni como base de reentrenamiento real. En este documento se reformulan como elementos fuera del alcance actual o como trabajo futuro condicionado a especialistas.

Validaciones tecnicas ejecutadas durante la revision:

| Validacion | Resultado esperado / referencia |
|---|---|
| Backend tests | `backend/.venv/Scripts/python.exe -m pytest tests -q`: 126 pruebas aprobadas, 4 warnings de Pydantic v2. |
| Frontend build | `frontend/npm.cmd run build`: build exitoso con Vite, 58 modulos transformados, advertencia de bundle JS mayor a 500 kB. |
| Revision de endpoints | Swagger/OpenAPI en `http://localhost:8001/docs` |
| Revision funcional | Login, roles, visor, ROI, heatmap, RAG, chatbot y SCT |

## 1. Revision de consistencia del proyecto actualizado

La revision del codigo confirma que algunos elementos de revision/correccion docente existen en la base de codigo, pero deben excluirse del alcance principal del informe. El enfoque recomendado para el Capitulo IV es describir el modulo histopatologico como un sistema de analisis educativo con trazabilidad tecnica de sesiones ROI, no como un sistema validado por docentes o especialistas.

| Elemento encontrado | Archivo o modulo donde aparece | Debe eliminarse del informe como funcionalidad activa | Reformulacion recomendada | Trabajo futuro |
|---|---|---:|---|---|
| Revision docente de sesiones | `frontend/src/pages/ReviewPage.jsx`, `frontend/src/app.jsx`, `frontend/src/components/AppSidebar.jsx` | Si | Pantalla experimental no considerada dentro del alcance actual del prototipo. | Si, solo si se define un flujo de validacion con especialistas. |
| Ruta `/dashboard/review` | `frontend/src/app.jsx`, `frontend/src/components/AppSidebar.jsx` | Si | Ruta administrativa experimental. No usar como evidencia central del informe. | Si, condicionada a criterios institucionales. |
| Correcciones docentes | `backend/app/routers/histopathology.py`, `backend/app/histopathology/schemas.py`, `frontend/src/components/OpenSeadragonViewer.jsx` | Si | Mecanismo experimental de anotacion, no usado como verdad academica ni clinica. | Si, con patologo/docente responsable. |
| `HistopathologyCorrection` | `backend/app/models.py`, `backend/app/routers/admin.py`, `backend/app/routers/histopathology.py` | Si | Entidad fuera del alcance actual del informe. No incluirla como tabla principal. | Si, como extension futura. |
| `GET /api/histopathology/dataset/manifest` | `backend/app/routers/histopathology.py` | Si | Exportacion tecnica experimental. No presentarla como dataset curado. | Si, solo con datos validados. |
| Reentrenamiento con correcciones reales | Referencias funcionales indirectas en flujo experimental | Si | Reemplazar por "mejora futura del modelo con datos validados y CAMELYON17". | Si, requiere validacion experta. |
| Revision docente SCT | No se observa como flujo principal consolidado; existe acceso protegido a intentos SCT | Si | Describir como persistencia de intentos SCT y consulta tecnica por rol. | Futuro: control de calidad de items y retroalimentaciones. |

Recomendacion de redaccion: cuando se hable de histopatologia, usar los conceptos "trazabilidad de sesiones ROI", "registro tecnico de resultados", "historial de analisis ROI", "trace_id" y "evaluacion preliminar con CAMELYON17". Evitar declarar dataset curado, correccion docente activa o reentrenamiento clinicamente validado.

## 2. Informacion actualizada para 4.3.5. Implementacion del Back-End

### Tecnologias utilizadas

El back-end se implemento con FastAPI como framework principal para exponer servicios REST. La aplicacion utiliza Uvicorn como servidor ASGI, SQLAlchemy como ORM, PostgreSQL como base de datos relacional, pgvector para busqueda vectorial cuando esta disponible, httpx para integracion con Ollama, python-multipart para carga de archivos, Pillow y OpenSlide para procesamiento de imagenes, y PyTorch/CONCH para inferencia histopatologica.

### Estructura general del backend

| Capa | Evidencia tecnica | Funcion |
|---|---|---|
| Aplicacion principal | `backend/app/main.py` | Crea la app FastAPI, configura CORS, monta routers, expone `/health` y prepara tablas. |
| Routers | `backend/app/routers/` | Agrupa endpoints por dominio: autenticacion, usuarios, imagenes, histopatologia, RAG, SCT, chatbot, casos y configuracion. |
| Modelos | `backend/app/models.py` | Define entidades SQLAlchemy persistidas en PostgreSQL. |
| Schemas | `backend/app/schemas.py`, `backend/app/histopathology/schemas.py` | Define contratos Pydantic de entrada/salida. |
| Seguridad | `backend/app/auth.py`, `backend/app/auth_security.py` | Gestiona JWT, hash de contrasenas, usuario actual y permisos por rol. |
| Servicios IA | `backend/app/histopathology/`, `backend/app/routers/chat.py`, `backend/app/routers/sct.py` | Ejecuta inferencia visual, chatbot, RAG y generacion SCT. |
| Entrenamiento offline | `backend/histopathology_offline/` | Contiene scripts de preparacion, evaluacion y entrenamiento con CAMELYON17. |

### Endpoints reales implementados por modulo

| Modulo | Endpoints principales | Estado actual |
|---|---|---|
| Salud/status | `GET /health` | Implementado |
| Autenticacion | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` | Implementado |
| Usuarios/admin | `GET /api/admin/users`, `POST /api/admin/users`, `PATCH /api/admin/users/{id}`, `DELETE /api/admin/users/{id}`, `POST /api/admin/users/{id}/approve`, `POST /api/admin/users/{id}/reject` | Implementado |
| Configuracion IA | `GET /api/admin/ai-config`, `PUT /api/admin/ai-config`, `GET /api/admin/integrations/status` | Implementado/parcial |
| Correo | `GET /api/admin/email-config`, `PUT /api/admin/email-config`, `POST /api/admin/email-config/test`, `GET/PUT /api/admin/email-templates/{key}` | Implementado/parcial |
| Imagenes medicas | `POST /api/medical-images/upload`, `GET /api/medical-images/list`, `GET /api/medical-images/view/{id}`, `GET /api/medical-images/download/{id}`, `DELETE /api/medical-images/{id}` | Implementado |
| Importacion CAMELYON17 | `GET /api/medical-images/local/camelyon17`, `POST /api/medical-images/import-local/camelyon17` | Implementado |
| DZI/tiles | `GET /api/medical-images/dzi/{id}.dzi`, `GET /api/medical-images/dzi/{id}_files/{level}/{col}_{row}.{fmt}`, `GET /api/medical-images/dzi/{id}/info` | Implementado |
| Histopatologia/status | `GET /api/histopathology/status` | Implementado |
| ROI/inferencia | `POST /api/histopathology/analyze-roi`, `POST /api/histopathology/scan-roi` | Implementado |
| Heatmap | `POST /api/histopathology/heatmaps/jobs`, `GET /api/histopathology/heatmaps/jobs/{job_id}`, `GET /api/histopathology/heatmaps/image/{image_id}/latest`, `GET /api/histopathology/heatmaps/image/{image_id}/history`, `GET /api/histopathology/heatmaps/{trace_id}`, `DELETE /api/histopathology/heatmaps/{trace_id}` | Implementado/parcial |
| Sesiones ROI | `GET /api/histopathology/sessions`, `GET /api/histopathology/sessions/{session_id}`, `DELETE /api/histopathology/sessions/{session_id}` | Implementado |
| Chatbot | `POST /api/chat` | Implementado/parcial |
| Casos clinicos | `GET /api/cases`, `POST /api/cases`, `GET /api/cases/search` | Implementado API |
| RAG documental | `GET/POST /api/rag/documents`, `GET/PUT/DELETE /api/rag/documents/{id}`, `POST /api/rag/documents/{id}/reindex`, `GET /api/rag/search` | Implementado/parcial |
| SCT | `POST /api/sct/generate`, `GET /api/sct/example`, `POST /api/sct/save`, `GET /api/sct/list`, `GET /api/sct/{test_id}`, `DELETE /api/sct/{test_id}`, `POST /api/sct/{test_id}/attempt`, `GET /api/sct/my-attempts`, `GET /api/sct/attempts/{attempt_id}` | Implementado |
| Dashboard | `GET /api/dashboard/stats`, `GET /api/dashboard/ranking` | Implementado/parcial |

Endpoints experimentales fuera del alcance principal del informe: el codigo contiene rutas para correccion de sesiones, revision administrativa de sesiones y exportacion tipo manifiesto. No se recomienda usarlas como evidencia central del Capitulo IV; deben tratarse como prototipos futuros condicionados a validacion por especialistas.

### Flujo de comunicacion

1. El frontend envia solicitudes REST al backend usando token Bearer cuando la ruta lo requiere.
2. FastAPI valida usuario, rol y payload mediante Pydantic y dependencias de seguridad.
3. Segun el modulo, el backend consulta PostgreSQL, filesystem, OpenSlide, PyTorch/CONCH, pgvector u Ollama.
4. La respuesta se retorna en JSON y el frontend actualiza la vista correspondiente.
5. En histopatologia, cada analisis relevante genera `trace_id` y registro tecnico de sesion ROI.

### Decisiones tecnicas adoptadas

| Decision | Justificacion |
|---|---|
| FastAPI | Permite tipado, validacion automatica, documentacion OpenAPI y desarrollo rapido. |
| Routers modulares | Separa responsabilidades y facilita documentar endpoints por modulo. |
| JWT | Permite proteger rutas y diferenciar roles. |
| PostgreSQL | Entrega persistencia robusta para usuarios, imagenes, SCT, RAG y trazabilidad. |
| pgvector | Permite busqueda semantica documental sin incorporar otro motor externo. |
| Ollama | Permite ejecutar LLM local para chatbot y SCT. |
| OpenSlide/DZI | Permite trabajar con laminas WSI de gran tamano sin cargarlas completas. |

### Evidencias recomendadas

- Captura de Swagger/OpenAPI con routers principales.
- Captura de `/health` respondiendo correctamente.
- Consola Uvicorn o Docker Compose con backend activo.
- Prueba de login y respuesta de `/api/auth/me`.
- Prueba de endpoint `/api/histopathology/status`.
- Prueba de generacion SCT y envio de intento.
- Prueba de busqueda RAG.

### Limitaciones actuales

- No existen migraciones Alembic formales; algunas compatibilidades se resuelven al iniciar la aplicacion.
- Varias funciones dependen de servicios locales activos, como Ollama, OpenSlide o CUDA/PyTorch.
- Algunas rutas experimentales no deben considerarse alcance principal del informe.
- La validacion clinica del modelo visual no forma parte de esta etapa.
- Falta endurecer configuracion productiva de secretos, CORS, rate limits y despliegue.

## 3. Informacion actualizada para 4.3.6. Implementacion de la Base de Datos

### Motor y acceso a datos

La base de datos utiliza PostgreSQL mediante SQLAlchemy. En el entorno Docker se emplea una imagen con soporte pgvector (`pgvector/pgvector:pg15`), lo que permite almacenar y consultar embeddings vectoriales para el modulo RAG. El acceso a datos se organiza mediante modelos SQLAlchemy definidos en `backend/app/models.py` y sesiones configuradas en `backend/app/db.py`.

### Modelos/tablas principales reales

| Modelo | Funcion en el prototipo | Estado en informe |
|---|---|---|
| `User` | Usuarios, rol, estado de aprobacion y control de acceso. | Principal |
| `MedicalImage` | Metadata de imagenes medicas, rutas, estado DZI y usuario uploader. | Principal |
| `Case` | Casos clinicos para contexto educativo y RAG basico. | Principal |
| `Document` | Documento academico cargado para RAG documental. | Principal |
| `DocumentChunk` | Fragmentos textuales usados para recuperacion. | Principal |
| `document_vector_embeddings` | Tabla vectorial para embeddings con pgvector cuando esta disponible. | Principal/parcial |
| `ChatLog` | Registro de preguntas y respuestas del chatbot. | Principal |
| `AIConfiguration` | Parametros de IA, RAG, modelos, correo y comportamiento. | Principal |
| `EmailTemplate` | Plantillas de correo para eventos administrativos. | Principal |
| `SCTTest` | Tests SCT generados y guardados. | Principal |
| `SCTAttempt` | Intentos individuales por estudiante con respuestas, puntaje y timestamps. | Principal |
| `HeatmapJob` | Jobs asincronicos de heatmap con estado, progreso, request y resultado. | Principal |
| `HistopathologySession` | Sesiones ROI con imagen, usuario, coordenadas, resultado, probabilidades, metricas y `trace_id`. | Principal |
| `HistopathologyCorrection` | Entidad experimental de correccion/anotacion. | Fuera del alcance actual del informe |

### Relaciones principales

| Relacion | Descripcion |
|---|---|
| `User` 1:N `MedicalImage` | Un usuario puede registrar imagenes. |
| `User` 1:N `HistopathologySession` | Un usuario genera sesiones ROI trazables. |
| `MedicalImage` 1:N `HistopathologySession` | Una imagen puede tener multiples analisis ROI. |
| `User` 1:N `ChatLog` | Cada consulta queda asociada a un usuario cuando hay sesion. |
| `Document` 1:N `DocumentChunk` | Un documento se divide en fragmentos recuperables. |
| `SCTTest` 1:N `SCTAttempt` | Un test puede tener multiples intentos. |
| `User` 1:N `SCTAttempt` | Un estudiante puede registrar multiples intentos. |
| `HeatmapJob` por `job_id`/`trace_id` | Cada job mantiene progreso y resultado tecnico del mapa. |

### Informacion persistida actualmente

- Usuarios, roles, estado de aprobacion y datos de acceso.
- Metadata de imagenes medicas y rutas de archivos.
- Casos clinicos.
- Documentos RAG, chunks y embeddings.
- Logs individuales del chatbot.
- Configuracion IA y configuracion de correo.
- Tests SCT guardados.
- Intentos SCT por estudiante mediante `SCTAttempt`.
- Sesiones ROI histopatologicas con imagen, usuario, ROI 1, ROI 2, estado, clase, confianza, probabilidades, metricas QC y `trace_id`.
- Jobs asincronicos de heatmap con progreso y resultado resumido en base de datos.
- Artefactos de heatmap en archivos JSON bajo `artifacts/histopathology/heatmaps`.

### Aclaraciones solicitadas

| Punto | Estado real |
|---|---|
| Intentos SCT por estudiante | Implementados mediante `SCTAttempt` y endpoints protegidos. |
| Heatmaps | El job y su progreso se guardan en base de datos; los mapas/resultados detallados tambien se almacenan como artefactos JSON. |
| Sesiones ROI | Se guardan con imagen, usuario, coordenadas, resultado, probabilidades, metricas de calidad y `trace_id`. |
| Correcciones docentes | Existen en codigo, pero no deben ser entidad principal del informe. |
| Reentrenamiento con correcciones | No debe declararse implementado; corresponde a trabajo futuro con datos validados. |

### Evidencias recomendadas

- Diagrama entidad-relacion actualizado.
- Captura de tablas principales en cliente SQL.
- Registro de usuario pendiente/aprobado.
- Registro de `histopathology_sessions` con `trace_id`.
- Registro de `sct_attempts`.
- Registro de `heatmap_jobs`.
- Documento RAG con chunks asociados.

### Limitaciones actuales

- Falta integrar Alembic para migraciones versionadas.
- El almacenamiento de artefactos histopatologicos combina base de datos y filesystem.
- La politica de retencion de artefactos, patches y heatmaps debe definirse antes de produccion.
- La entidad experimental de correccion debe quedar fuera del relato principal del informe.

## 4. Informacion actualizada para 4.3.7. Implementacion del Visor Histopatologico

### Tecnologia usada

El visor histopatologico utiliza OpenSeadragon en el frontend para navegar imagenes en formato DZI. En el backend se utiliza OpenSlide para leer regiones de imagenes WSI y generar tiles bajo demanda. Pillow se usa como respaldo para formatos raster convencionales.

### Formatos soportados

El sistema acepta archivos como SVS, TIFF/TIF, PNG, JPG y JPEG. Para imagenes WSI de gran tamano, se recomienda trabajar con DZI/tiles para evitar cargar archivos completos en el navegador.

### Flujo de carga e importacion

1. El administrador o usuario autorizado carga una imagen con `POST /api/medical-images/upload` o registra una imagen CAMELYON17 local con `POST /api/medical-images/import-local/camelyon17`.
2. El backend guarda metadata de la imagen y prepara la informacion DZI.
3. El frontend lista las imagenes disponibles.
4. Al abrir una imagen, OpenSeadragon solicita el manifiesto DZI.
5. El visor pide tiles progresivamente segun zoom y posicion.
6. Si el tile no existe fisicamente, el backend puede generarlo dinamicamente usando OpenSlide.

### Endpoints usados

| Funcion | Endpoint |
|---|---|
| Listar imagenes | `GET /api/medical-images/list` |
| Subir imagen | `POST /api/medical-images/upload` |
| Importar CAMELYON17 local | `GET /api/medical-images/local/camelyon17`, `POST /api/medical-images/import-local/camelyon17` |
| Obtener imagen raster | `GET /api/medical-images/view/{image_id}` |
| Obtener DZI | `GET /api/medical-images/dzi/{image_id}.dzi` |
| Obtener tile | `GET /api/medical-images/dzi/{image_id}_files/{level}/{col}_{row}.{fmt}` |
| Obtener metadata DZI | `GET /api/medical-images/dzi/{image_id}/info` |

### Integracion frontend-backend

`frontend/src/pages/ImagesPage.jsx` gestiona biblioteca y seleccion de imagen. `frontend/src/components/OpenSeadragonViewer.jsx` carga el visor, administra ROI y muestra resultados. El backend entrega DZI, tiles, metadata y endpoints de inferencia.

### Evidencias visuales recomendadas

- Biblioteca de imagenes medicas.
- Registro de imagen CAMELYON17 local.
- Visor OpenSeadragon con lamina cargada.
- Zoom progresivo sobre tejido.
- Solicitudes de tiles en navegador o Swagger.

### Validaciones realizadas

- Pruebas manuales de carga de imagenes y apertura del visor.
- Pruebas de DZI/tiles con imagenes CAMELYON17.
- Validacion de importacion local para evitar carga de archivos de varios GB por navegador.

### Limitaciones actuales

- Requiere OpenSlide en el servidor para WSI.
- La carga directa por navegador no es recomendable para laminas de varios GB.
- La cache de tiles fisicos puede optimizarse para escenarios multiusuario.
- La preparacion de laminas depende de que los archivos existan en el servidor.

## 5. Informacion actualizada para 4.3.8. Implementacion del Modulo ROI

### Funcionamiento de ROI 1 y ROI 2

ROI 1 representa una region amplia de exploracion dentro de la lamina. ROI 2 representa una subregion especifica, contenida dentro de ROI 1, que se extrae como patch para analisis visual. Esta separacion permite mantener contexto visual para el usuario y reducir la carga computacional del modelo.

### Validaciones geometricas

| Validacion | Estado |
|---|---|
| Coordenadas dentro de los limites de imagen | Implementado |
| ROI 2 contenida dentro de ROI 1 | Implementado |
| Tamano minimo de ROI 2 | Implementado, al menos 32x32 pixeles |
| Tamano maximo de ROI 2 | Implementado, hasta 4096x4096 pixeles |
| Validacion backend ademas de frontend | Implementado |

### Extraccion de patch y trazabilidad

El backend extrae la region seleccionada con OpenSlide o Pillow. Cada analisis genera un `trace_id`, que permite vincular la solicitud con el resultado, las metricas de calidad, los artefactos de depuracion y el registro persistido en base de datos.

### Datos guardados en la sesion ROI

- Usuario asociado.
- Imagen asociada.
- ROI 1 y ROI 2.
- Estado del analisis.
- Clase educativa resultante.
- Confianza/probabilidad.
- Probabilidades por clase.
- Metricas de calidad del tejido.
- `trace_id`.
- Timestamp de creacion.

### Flujo completo

1. Usuario abre imagen en visor DZI.
2. Selecciona ROI 1.
3. Selecciona ROI 2 dentro de ROI 1.
4. Frontend valida ubicacion y tamano.
5. Backend vuelve a validar contra dimensiones reales.
6. Backend extrae patch.
7. Se aplica control de calidad.
8. Si la region es evaluable, se ejecuta inferencia visual.
9. Se entrega resultado educativo con probabilidades y advertencia no diagnostica.
10. Se guarda una sesion ROI con `trace_id`.

### Endpoints utilizados

- `POST /api/histopathology/analyze-roi`.
- `POST /api/histopathology/scan-roi`.
- `GET /api/histopathology/sessions`.
- `GET /api/histopathology/sessions/{session_id}`.
- `DELETE /api/histopathology/sessions/{session_id}`.

### Evidencias visuales recomendadas

- ROI 1 seleccionada en azul.
- ROI 2 seleccionada dentro de ROI 1.
- Resultado educativo con clase, probabilidades, QC y `trace_id`.
- Historial de sesiones ROI.
- Patch de depuracion asociado al analisis.

### Limitaciones actuales

- La seleccion manual de ROI puede requerir mejor UX para ajuste fino.
- La interpretacion del resultado sigue siendo educativa y no diagnostica.
- No se incluye revision experta como parte del flujo actual.
- Se requiere ampliar datos validados para mejorar robustez del modelo.

## 6. Informacion actualizada para 4.3.9. Implementacion del Modelo Visual CONCH/PyTorch

### Modelo visual utilizado

El prototipo integra CONCH como extractor visual especializado en histopatologia y una cabeza clasificadora implementada en PyTorch. CONCH funciona como backbone congelado, es decir, no se reentrena durante el uso del prototipo. La cabeza clasificadora recibe embeddings de 512 dimensiones y produce la salida educativa.

### Arquitectura general

| Componente | Descripcion |
|---|---|
| Backbone | CONCH `conch_ViT-B-16` |
| Estado del backbone | Congelado |
| Entrada | Patch RGB extraido desde ROI 2 |
| Preprocesamiento | Transformacion CONCH, usualmente hacia entrada tipo 224x224 |
| Embedding | Vector de 512 dimensiones |
| Clasificador | Cabeza PyTorch entrenada sobre embeddings |
| Checkpoint activo | `tri_head_camelyon17_stage10_balanced_v1_weighted.pt` |

### Clases de salida actuales

- `no_metastasico`.
- `metastasico`.
- `estroma`.

Ademas, el sistema puede entregar estados derivados como `roi_no_evaluable`, `resultado_incierto` o baja sospecha/no metastasico probable cuando las condiciones de calidad o confianza lo justifican.

### Control de calidad de ROI

Antes de forzar una prediccion, el sistema evalua la calidad de la region. El objetivo es evitar clasificaciones sobre fondo, tejido insuficiente, estroma predominante o regiones no evaluables.

| Criterio | Uso |
|---|---|
| Fondo blanco | Detectar region sin tejido suficiente. |
| Fraccion de tejido | Estimar si hay material util para analizar. |
| Fraccion nuclear/celular | Evaluar celularidad orientativa. |
| Predominio estromal | Evitar confundir estroma/fibrosis con tumor. |
| Confianza del modelo | Evitar conclusiones cerradas si la probabilidad no supera el umbral. |

### Forma de inferencia

1. Se extrae patch desde ROI 2.
2. Se convierte/preprocesa para CONCH.
3. CONCH genera embedding.
4. La cabeza PyTorch calcula probabilidades.
5. Se aplica logica de decision educativa y control de calidad.
6. El backend devuelve clase, confianza, probabilidades, QC, `trace_id` y advertencia de uso no diagnostico.

### Uso de CAMELYON17

CAMELYON17 se utiliza como base estructurada para entrenamiento y evaluacion preliminar. Las anotaciones XML oficiales permiten diferenciar regiones tumorales y no tumorales sin depender de etiquetado manual del desarrollador. Las etapas offline documentadas permiten comparar checkpoints y evitar reemplazar el modelo activo si una nueva etapa no mejora de forma suficiente.

### Heatmaps

El heatmap divide ROI 1 en tiles, analiza cada tile y genera una visualizacion de sospecha educativa. Los jobs se ejecutan de forma asincronica, mantienen progreso y permiten cargar mapas previamente generados. Este flujo esta pensado para evitar bloquear la interfaz y controlar la carga computacional.

### Endpoints principales

- `GET /api/histopathology/status`.
- `POST /api/histopathology/analyze-roi`.
- `POST /api/histopathology/scan-roi`.
- `POST /api/histopathology/heatmaps/jobs`.
- `GET /api/histopathology/heatmaps/jobs/{job_id}`.
- `GET /api/histopathology/heatmaps/image/{image_id}/latest`.
- `GET /api/histopathology/heatmaps/{trace_id}`.

### Evidencias recomendadas

- Endpoint `/api/histopathology/status` mostrando modelo listo.
- Resultado ROI metastasico con probabilidades.
- Resultado ROI no metastasico o no evaluable.
- Heatmap de ROI con tiles coloreados.
- Registro de `trace_id`.
- Reportes offline de CAMELYON17 si estan disponibles.

### Limitaciones actuales

- No existe validacion clinica formal.
- No existe revision experta como parte de esta etapa.
- El modelo esta orientado a uso educativo, no diagnostico.
- La robustez depende de ampliar datos validados, especialmente regiones no metastasicas, estroma y negativos dificiles.
- El rendimiento depende de disponibilidad de GPU/CUDA o ejecucion CPU.

## 7. Informacion actualizada para 4.3.10. Implementacion del RAG y Retroalimentacion Educativa

### Estado actual del RAG

El prototipo cuenta con un RAG documental implementado de forma parcial-funcional y un RAG basico basado en casos clinicos. El RAG documental permite registrar contenido textual, dividirlo en fragmentos, generar embeddings y recuperar fragmentos relevantes durante una consulta. Cuando pgvector esta disponible, se utiliza busqueda vectorial en PostgreSQL. Si no esta disponible, se recurre a un fallback con embeddings almacenados y similitud local.

### Componentes implementados

| Componente | Evidencia tecnica | Estado |
|---|---|---|
| Casos clinicos como contexto | `backend/app/routers/cases.py`, modelo `Case` | Implementado API |
| Documentos RAG | `backend/app/routers/rag.py`, modelo `Document` | Implementado/parcial |
| Chunks | `DocumentChunk`, `rag_utils.py` | Implementado |
| Embeddings | `embedding_service.py` | Implementado/parcial |
| pgvector | `pgvector_store.py`, Docker con `pgvector/pgvector:pg15` | Implementado/parcial |
| Fallback | Embeddings JSON/similitud local | Implementado |
| Integracion chatbot | `chat.py`, recuperacion de fuentes/contexto | Implementado/parcial |
| Panel admin RAG | `frontend/src/pages/ConfigPage.jsx` | Implementado/parcial |

### Flujo RAG

1. Un administrador registra contenido documental.
2. El backend divide el contenido en chunks.
3. Cada chunk se vectoriza.
4. Los embeddings se guardan en pgvector o fallback JSON.
5. El usuario realiza una consulta al chatbot.
6. El backend recupera contexto relevante desde documentos/casos.
7. El contexto se incorpora al prompt educativo.
8. El chatbot responde con retroalimentacion contextualizada.

### Endpoints principales

- `GET /api/rag/documents`.
- `POST /api/rag/documents`.
- `GET /api/rag/documents/{document_id}`.
- `PUT /api/rag/documents/{document_id}`.
- `DELETE /api/rag/documents/{document_id}`.
- `POST /api/rag/documents/{document_id}/reindex`.
- `GET /api/rag/search`.
- `POST /api/chat`.

### Evidencias recomendadas

- Panel de documentos RAG.
- Documento creado con titulo, contenido y tags.
- Estado de integracion RAG/pgvector/embeddings.
- Resultado de busqueda RAG.
- Respuesta del chatbot usando contexto documental.

### Validaciones realizadas

- Pruebas unitarias de utilidades RAG y servicio de embeddings.
- Pruebas manuales recomendadas de creacion, reindexacion, busqueda y respuesta con fuentes.

### Limitaciones actuales

- La ingestion automatica de PDF/URL no esta completamente resuelta; el flujo principal trabaja con contenido textual cargado.
- La calidad de citacion y trazabilidad de fuentes puede mejorar.
- La disponibilidad del modelo neuronal de embeddings puede depender del entorno.
- Falta una evaluacion formal de recuperacion con preguntas y respuestas esperadas.

## 8. Informacion actualizada para 4.3.11. Implementacion del Chatbot Educativo y Modulo SCT

### A) Chatbot educativo

El chatbot educativo se implementa mediante una interfaz React y el endpoint `POST /api/chat`. El backend se conecta con Ollama/LLaMA para generar respuestas educativas. El sistema incorpora restricciones de alcance, contexto RAG y registro de intercambios.

| Aspecto | Estado |
|---|---|
| Modelo usado | Ollama/LLaMA, configurable segun entorno. |
| Endpoint principal | `POST /api/chat`. |
| Uso de RAG | Implementado/parcial con documentos y casos. |
| Historial | Intercambios guardados en `ChatLog`; hilos completos principalmente en cliente/localStorage. |
| Acciones del hilo | Gestionadas en frontend. |
| Exportacion | Si existe en UI, debe documentarse como funcion de apoyo, no como modulo central. |
| Restriccion educativa | El prompt y la logica limitan el uso no diagnostico y consultas fuera de ambito. |

Flujo:

1. Usuario ingresa una consulta.
2. Frontend envia mensaje al backend.
3. Backend valida contenido y usuario si hay token.
4. Se recupera contexto de casos/documentos si RAG esta activo.
5. Backend consulta Ollama.
6. Se guarda el intercambio en `ChatLog`.
7. Frontend muestra respuesta educativa.

Evidencias recomendadas:

- Pantalla del chatbot.
- Consulta medica y respuesta educativa.
- Respuesta con contexto/fuentes RAG.
- Registro `ChatLog` en base de datos.

Limitaciones:

- Las conversaciones completas como hilos no estan completamente normalizadas en base de datos.
- La calidad depende del modelo local.
- No debe usarse como herramienta diagnostica.

### B) Modulo SCT

El modulo SCT permite generar, guardar, listar, responder y registrar intentos de pruebas Script Concordance Test.

| Funcion | Estado real |
|---|---|
| Generacion SCT | Implementada con Ollama/LLaMA. |
| Parametros | Tema/foco, dificultad, cantidad de items y escala -2 a +2. |
| Guardado de tests | Implementado en `SCTTest`. |
| Listado de tests | Implementado. |
| Eliminacion | Implementada. |
| Resolucion por estudiante | Implementada en frontend. |
| Retroalimentacion | Implementada por item y puntaje. |
| Calculo de puntaje | Implementado para coincidencia directa/parcial segun logica del backend/frontend. |
| Persistencia individual de intentos | Implementada mediante `SCTAttempt`. |
| Revision docente SCT | No incluir como funcionalidad activa; reformular como futuro control de calidad de items y retroalimentaciones. |

Endpoints principales:

- `POST /api/sct/generate`.
- `GET /api/sct/example`.
- `POST /api/sct/save`.
- `GET /api/sct/list`.
- `GET /api/sct/{test_id}`.
- `DELETE /api/sct/{test_id}`.
- `POST /api/sct/{test_id}/attempt`.
- `GET /api/sct/my-attempts`.
- `GET /api/sct/attempts/{attempt_id}`.

Flujo:

1. Usuario define tema, dificultad y numero de items.
2. Backend genera items SCT con LLM.
3. Frontend muestra vineta, hipotesis, nueva informacion y escala.
4. Estudiante responde cada item.
5. Sistema calcula resultado y retroalimentacion.
6. Si el test no estaba guardado, el frontend lo guarda primero.
7. Backend registra intento individual en `SCTAttempt`.

Evidencias recomendadas:

- Formulario de generacion SCT.
- Test generado.
- Resolucion de items con escala.
- Retroalimentacion y puntaje.
- Registro de intento en base de datos.

Limitaciones:

- Falta analitica institucional por cohorte.
- Falta control de calidad formal de items generados.
- La generacion depende de Ollama y del modelo configurado.

## 9. Evidencias y capturas recomendadas para el informe

| Apartado | Figura sugerida | Que debe mostrar | Que valida | Prioridad |
|---|---|---|---|---|
| 4.3.5 | Figura 4.X. Swagger/OpenAPI del backend | Tags y endpoints principales | Existencia de API modular | Alta |
| 4.3.5 | Figura 4.X. Backend en ejecucion | Consola Uvicorn/Docker sin errores | Servicio activo | Alta |
| 4.3.5 | Figura 4.X. Endpoint de salud | Respuesta `/health` | Disponibilidad basica | Alta |
| 4.3.6 | Figura 4.X. Tablas principales en PostgreSQL | `users`, `medical_images`, `histopathology_sessions`, `sct_attempts`, `heatmap_jobs` | Persistencia | Alta |
| 4.3.6 | Figura 4.X. Registro de sesion ROI | Fila con `trace_id`, coordenadas y resultado | Trazabilidad ROI | Alta |
| 4.3.6 | Figura 4.X. Intento SCT persistido | Registro `sct_attempts` | Persistencia individual SCT | Alta |
| 4.3.7 | Figura 4.X. Biblioteca de imagenes | Lista de imagenes medicas | Gestion de imagenes | Alta |
| 4.3.7 | Figura 4.X. Importacion CAMELYON17 | Panel o respuesta de importacion local | Flujo para WSI pesadas | Media |
| 4.3.7 | Figura 4.X. Visor OpenSeadragon | Lamina DZI con zoom | Visualizacion histopatologica | Alta |
| 4.3.8 | Figura 4.X. Seleccion ROI 1 | Region amplia marcada | Delimitacion de contexto | Alta |
| 4.3.8 | Figura 4.X. Seleccion ROI 2 | Subregion contenida en ROI 1 | Validacion geometrica | Alta |
| 4.3.8 | Figura 4.X. Resultado ROI | Clase, probabilidades, QC y `trace_id` | Flujo completo ROI | Alta |
| 4.3.9 | Figura 4.X. Estado del modelo visual | `/api/histopathology/status` | Modelo listo y dispositivo | Alta |
| 4.3.9 | Figura 4.X. Heatmap ROI | Overlay por tiles | Analisis por region | Alta |
| 4.3.9 | Figura 4.X. Resultado no evaluable | Fondo/estroma/baja calidad | Control de calidad | Media |
| 4.3.10 | Figura 4.X. Panel documentos RAG | Documento creado y chunks | RAG documental | Alta |
| 4.3.10 | Figura 4.X. Configuracion IA/RAG | Flags de RAG, pgvector, embeddings | Parametrizacion IA | Media |
| 4.3.10 | Figura 4.X. Respuesta con contexto | Chatbot usando fuentes | Recuperacion aumentada | Alta |
| 4.3.11 | Figura 4.X. Chatbot educativo | Consulta y respuesta | Asistente IA | Alta |
| 4.3.11 | Figura 4.X. Generacion SCT | Tema, dificultad, cantidad | Creacion de test | Alta |
| 4.3.11 | Figura 4.X. Resolucion SCT | Escala y respuestas | Interaccion estudiante | Alta |
| 4.3.11 | Figura 4.X. Puntaje SCT | Retroalimentacion e intento guardado | Evaluacion y persistencia | Alta |
| General | Figura 4.X. Configuracion/usuarios | Gestion de cuenta aprobada | Seguridad y roles | Media |

## 10. Pruebas y validaciones

| Prueba | Modulo | Descripcion | Resultado esperado | Resultado actual a registrar | Evidencia disponible | Estado |
|---|---|---|---|---|---|---|
| Build frontend | Frontend | Ejecutar `npm.cmd run build` en `frontend` | Build exitoso | Build exitoso; 58 modulos transformados; warning de bundle >500 kB | Vite build | Alta |
| Pruebas backend | Backend | Ejecutar `python -m pytest tests -q` | Suite aprobada | 126 passed, 4 warnings de Pydantic v2 | Pytest | Alta |
| Login | Auth | Iniciar sesion con usuario aprobado | Token y dashboard | Captura login/dashboard | UI + `/api/auth/me` | Alta |
| Usuarios/roles | Seguridad | Verificar estudiante vs administrador | Menus restringidos | Captura sidebar por rol | UI + endpoints admin | Alta |
| Carga de imagenes | Imagenes | Subir/importar imagen | Registro en biblioteca | Captura biblioteca | Endpoint upload/import | Alta |
| DZI/tiles | Visor | Abrir DZI y navegar | Tiles cargan con zoom | Captura visor/red | OpenSeadragon | Alta |
| ROI | Histopatologia | Seleccionar ROI 1 y ROI 2 | Coordenadas validas | Captura ROI | UI + endpoint ROI | Alta |
| Modelo IA | Histopatologia | Analizar ROI 2 | Resultado con probabilidades | Captura resultado | `/analyze-roi` | Alta |
| Heatmap | Histopatologia | Generar mapa de ROI 1 | Job progresa y overlay aparece | Captura progreso/mapa | Jobs heatmap | Alta |
| Chatbot | IA educativa | Enviar consulta medica | Respuesta educativa | Captura chat | `/api/chat` | Alta |
| RAG | RAG | Crear documento y consultar | Recupera contexto | Captura documento/respuesta | `/api/rag/search` | Alta |
| Generacion SCT | SCT | Crear test por tema | Items generados | Captura test | `/api/sct/generate` | Alta |
| Persistencia SCT | SCT | Completar test | Intento guardado | Tabla `sct_attempts` | `/api/sct/{id}/attempt` | Alta |
| Base de datos | DB | Revisar tablas y registros | Datos persistidos | Captura cliente SQL | PostgreSQL | Alta |
| Configuracion IA | Admin | Cambiar flags/modelos | Config guardada | Captura config | `/api/admin/ai-config` | Media |

## 11. Textos academicos base

### 4.3.5. Implementacion del Back-End

El back-end de ASOFAMECH se implemento mediante FastAPI, organizando la logica del sistema en routers especializados segun dominio funcional. Esta decision permitio separar autenticacion, administracion de usuarios, imagenes medicas, analisis histopatologico, RAG, chatbot, casos clinicos y modulo SCT. La aplicacion principal configura CORS, registra los routers, expone un endpoint de salud y establece la conexion con la base de datos.

La comunicacion con el front-end se realiza mediante servicios REST que retornan respuestas JSON. Las rutas protegidas utilizan autenticacion mediante JWT y validacion de usuario desde base de datos. Para los servicios de inteligencia artificial, el back-end se comunica con Ollama en el caso del chatbot y SCT, mientras que el modulo histopatologico integra OpenSlide, Pillow, PyTorch y CONCH para el procesamiento de imagenes y patches. Esta arquitectura permite mantener separada la logica de interfaz, persistencia, inferencia visual y recuperacion documental.

Como evidencia tecnica se consideran la documentacion Swagger/OpenAPI, el endpoint `/health`, las pruebas automatizadas del backend y los endpoints funcionales de autenticacion, imagenes, histopatologia, RAG, chatbot y SCT. El estado actual es funcional para el prototipo educativo, aunque quedan pendientes mejoras de despliegue productivo, migraciones formales, endurecimiento de seguridad y validaciones de integracion en entorno real.

### 4.3.6. Implementacion de la Base de Datos

La base de datos se implemento con PostgreSQL y SQLAlchemy como capa ORM. El entorno contempla soporte para pgvector, permitiendo almacenar representaciones vectoriales de documentos para el modulo RAG. Las entidades principales representan usuarios, imagenes medicas, casos clinicos, documentos, fragmentos documentales, configuracion IA, logs de chatbot, pruebas SCT, intentos SCT, jobs de heatmap y sesiones histopatologicas ROI.

Una decision relevante fue persistir la trazabilidad tecnica del modulo histopatologico mediante sesiones ROI. Cada sesion almacena la imagen, el usuario, las coordenadas de ROI 1 y ROI 2, el resultado educativo, probabilidades, metricas de calidad y un `trace_id`. Esto permite reconstruir el proceso de analisis sin declarar una validacion clinica. Asimismo, los intentos SCT por estudiante se almacenan mediante una entidad especifica, permitiendo conservar respuestas, puntaje y fecha de realizacion.

Los heatmaps combinan persistencia en base de datos y filesystem: el job asincronico mantiene estado y progreso en PostgreSQL, mientras que los artefactos detallados del mapa se guardan como JSON. Como limitacion principal, el proyecto aun requiere migraciones formales y una politica clara de retencion de artefactos. Las entidades experimentales asociadas a correccion docente no se consideran parte del alcance principal del informe.

### 4.3.7. Implementacion del Visor Histopatologico

El visor histopatologico se implemento con OpenSeadragon para permitir la navegacion de imagenes de alta resolucion mediante DZI. Esta tecnologia permite cargar progresivamente tiles de la imagen en funcion del nivel de zoom y la posicion visible, evitando transferir una lamina completa al navegador. En el backend, OpenSlide permite leer regiones de archivos WSI y generar tiles dinamicamente cuando corresponde.

El sistema permite cargar imagenes convencionales y registrar laminas CAMELYON17 disponibles localmente en el servidor. Esta ultima decision resuelve una limitacion practica importante, ya que las laminas histopatologicas pueden pesar varios gigabytes y no resulta eficiente subirlas por navegador. El flujo consiste en registrar la imagen, preparar o exponer su DZI, abrirla desde la biblioteca y navegarla con zoom y desplazamiento.

La evidencia funcional recomendada incluye capturas de la biblioteca de imagenes, importacion CAMELYON17, visor OpenSeadragon, zoom sobre tejido y respuesta de endpoints DZI/tiles. El modulo se encuentra implementado para el flujo principal, aunque su uso con WSI depende de la disponibilidad de OpenSlide y de una estrategia de cache adecuada para escenarios multiusuario.

### 4.3.8. Implementacion del Modulo ROI

El modulo ROI se diseno para que el usuario seleccione una region amplia de exploracion y una subregion especifica de analisis. ROI 1 representa el contexto visual dentro de la lamina, mientras que ROI 2 corresponde al patch enviado al modelo visual. Esta separacion reduce la carga computacional y mejora la comprension pedagogica del flujo, ya que el estudiante visualiza donde se origina la inferencia.

La seleccion se realiza sobre el visor OpenSeadragon y las coordenadas se transforman al sistema de referencia de la imagen original. El backend valida limites, tamano y contencion de ROI 2 dentro de ROI 1 antes de extraer el patch. Posteriormente se genera un `trace_id`, se aplica control de calidad y se ejecuta el analisis visual cuando la region es evaluable. El resultado se guarda como sesion ROI junto con probabilidades, metricas y coordenadas.

El estado actual del modulo permite completar el flujo imagen, ROI, extraccion, analisis y trazabilidad. Las evidencias recomendadas son capturas de ROI 1, ROI 2, resultado educativo, coordenadas y registro de sesion. Como limitacion, la seleccion manual podria mejorar con herramientas de ajuste fino y comparacion pedagogica entre regiones.

### 4.3.9. Implementacion del Modelo Visual CONCH/PyTorch

El modelo visual del prototipo utiliza CONCH como extractor congelado de caracteristicas histopatologicas y una cabeza clasificadora implementada en PyTorch. Esta arquitectura permite aprovechar representaciones visuales especializadas sin reentrenar el backbone completo, reduciendo costo computacional y riesgo de sobreajuste. La inferencia se realiza sobre patches extraidos desde ROI 2 y preprocesados segun los requerimientos de CONCH.

Antes de clasificar, el sistema aplica control de calidad sobre la region para detectar fondo, baja proporcion de tejido, baja celularidad o predominio estromal. Si la ROI no es adecuada, el sistema entrega un estado no evaluable o incierto en lugar de forzar una prediccion. Cuando la inferencia procede, se devuelven clase, confianza, probabilidades por clase, metricas de calidad y advertencia de uso educativo no diagnostico.

El checkpoint activo corresponde a una cabeza de tres clases para distinguir tejido no metastasico, metastasico y estroma. CAMELYON17 se utiliza como base estructurada para entrenamiento y evaluacion preliminar mediante anotaciones oficiales, evitando depender de etiquetado manual no experto. El modelo no cuenta con validacion clinica formal ni revision por patologo en esta etapa; por ello, sus resultados se presentan exclusivamente como retroalimentacion educativa.

### 4.3.10. Implementacion del RAG y Retroalimentacion Educativa

El componente RAG se implemento para enriquecer las respuestas educativas del chatbot mediante recuperacion de informacion desde documentos y casos clinicos. El sistema permite almacenar documentos textuales, dividirlos en fragmentos, generar embeddings y recuperar los fragmentos mas relevantes frente a una consulta. Cuando pgvector esta disponible, la busqueda se realiza mediante vectores en PostgreSQL; en caso contrario, se utiliza un mecanismo de similitud con embeddings almacenados.

Durante una consulta, el backend recupera contexto documental y casos clinicos relacionados, construye un prompt educativo y solicita la respuesta al modelo generativo. Esta decision reduce la dependencia de respuestas genericas y permite orientar la retroalimentacion hacia contenidos cargados en la plataforma. La configuracion administrativa permite controlar la activacion del RAG, el modelo de embeddings y el numero de documentos usados como contexto.

El estado actual es funcional para contenido textual cargado manualmente. Como limitaciones se identifican la ingestion automatica de PDF/URL, la calidad de citacion de fuentes y la necesidad de evaluar formalmente la recuperacion con preguntas de prueba. Estas mejoras pueden incorporarse en iteraciones posteriores.

### 4.3.11. Implementacion del Chatbot Educativo y Modulo SCT

El chatbot educativo se implemento mediante una interfaz conversacional conectada a FastAPI y Ollama/LLaMA. El sistema procesa consultas de caracter medico-educativo, recupera contexto desde documentos RAG o casos clinicos cuando corresponde, genera una respuesta y registra el intercambio. El prompt limita el uso no diagnostico y busca mantener la respuesta dentro de un marco formativo.

El modulo SCT permite generar pruebas Script Concordance Test a partir de un tema, dificultad y cantidad de items. Cada test contiene una vineta, hipotesis, nueva informacion, escala de respuesta y explicacion. El estudiante responde los items, recibe retroalimentacion y el sistema calcula un puntaje. Los tests pueden guardarse y listarse, y los intentos individuales quedan persistidos con respuestas, puntaje y timestamps.

Ambos modulos se encuentran implementados como herramientas educativas. Las principales limitaciones son la dependencia del modelo generativo local, la necesidad de control de calidad de los items SCT y la normalizacion futura de historiales conversacionales completos en base de datos. No se considera dentro del alcance actual una revision docente formal de respuestas SCT; se plantea como posible mejora futura orientada al control de calidad de contenidos y retroalimentaciones.
