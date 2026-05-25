# Guia del Desarrollador — ASOFAMECH

Este documento describe la arquitectura, estructura y decisiones tecnicas del proyecto para facilitar la incorporacion de nuevos colaboradores y la continuidad del desarrollo.

---

## Indice

1. [Arquitectura general](#1-arquitectura-general)
2. [Estructura de carpetas](#2-estructura-de-carpetas)
3. [Backend — FastAPI](#3-backend--fastapi)
4. [Frontend — React / Vite](#4-frontend--react--vite)
5. [Base de datos](#5-base-de-datos)
6. [Autenticacion y RBAC](#6-autenticacion-y-rbac)
7. [Modulo RAG](#7-modulo-rag)
8. [Modulo histopatologico](#8-modulo-histopatologico)
9. [Modulo SCT](#9-modulo-sct)
10. [Chatbot / Asistente IA](#10-chatbot--asistente-ia)
11. [Flujo de datos end-to-end](#11-flujo-de-datos-end-to-end)
12. [Variables de entorno de referencia](#12-variables-de-entorno-de-referencia)
13. [Pruebas](#13-pruebas)
14. [Migraciones](#14-migraciones)

---

## 1. Arquitectura general

```
Navegador
    │
    ▼
┌─────────────────────┐   puerto 3000
│   Frontend          │   React 18 + Vite → Nginx (Docker)
│   (SPA)             │   authClient.js: token JWT en localStorage
└──────────┬──────────┘
           │ HTTP / REST + Bearer token
           ▼
┌─────────────────────┐   puerto 8001
│   Backend           │   FastAPI + SQLAlchemy + Alembic
│   (API REST)        │   11 routers, RBAC por permiso
└──────┬──────┬───────┘
       │      │
       │      └──────────────────────────┐
       ▼                                 ▼
┌──────────────┐  puerto 5432   ┌────────────────┐  puerto 11434
│  PostgreSQL  │                │    Ollama       │
│  15+pgvector │                │   LLaMA 3 8B    │
└──────────────┘                └────────────────┘
```

Todos los servicios se orquestan con Docker Compose. En modo desarrollo, solo DB y Ollama corren en Docker; frontend y backend se ejecutan localmente con hot-reload.

---

## 2. Estructura de carpetas

```
Asofamech/
├── backend/
│   ├── app/
│   │   ├── routers/              # Un archivo por dominio de negocio
│   │   │   ├── auth.py           # Registro, login, tokens
│   │   │   ├── admin.py          # Gestion de usuarios, configuracion IA
│   │   │   ├── cases.py          # CRUD de casos clinicos
│   │   │   ├── chat.py           # Endpoint del chatbot con RAG
│   │   │   ├── dashboard.py      # Estadisticas y ranking
│   │   │   ├── feedback.py       # Evaluacion de usabilidad
│   │   │   ├── histopathology.py # ROI, heatmap, sesiones
│   │   │   ├── history.py        # Historial de consultas y sesiones ROI
│   │   │   ├── medical_images.py # Upload/listado de imagenes WSI
│   │   │   ├── rag.py            # CRUD documentos RAG, busqueda, reindex
│   │   │   └── sct.py            # Generacion, gestion y evaluacion SCT
│   │   ├── auth.py               # RBAC: roles, permisos, JWT dependency
│   │   ├── auth_security.py      # Hashing, firma y verificacion JWT
│   │   ├── db.py                 # Session factory SQLAlchemy
│   │   ├── main.py               # Punto de entrada FastAPI, CORS, routers
│   │   ├── models.py             # Modelos ORM (13 tablas)
│   │   └── schemas.py            # Esquemas Pydantic (request/response)
│   ├── alembic/
│   │   └── versions/             # 4 migraciones versionadas
│   ├── histopathology_offline/   # Pipeline de entrenamiento offline
│   ├── tests/                    # 27 archivos pytest
│   ├── artifacts/                # Checkpoints, logs de auditoria (gitignored)
│   ├── data/rag/                 # Documentos para el corpus RAG
│   ├── uploads/                  # Archivos WSI subidos (gitignored)
│   ├── requirements.txt          # Dependencias base
│   ├── requirements-histopathology.txt
│   ├── requirements-rag-neural.txt
│   ├── start.sh                  # Entrypoint Docker: alembic upgrade + uvicorn
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/                # 11 paginas (AuthPage, DashboardPage, etc.)
│   │   ├── components/           # AppSidebar, OpenSeadragonViewer, etc.
│   │   ├── api.js                # Todas las llamadas a la API REST
│   │   ├── authClient.js         # Gestion de sesion, authFetch, RBAC helpers
│   │   ├── tracker.js            # Metricas locales de sesion y racha
│   │   └── styles.css            # Estilos globales
│   ├── e2e/                      # Tests Playwright
│   │   ├── global-setup.js       # Crea usuarios de prueba via API
│   │   ├── helpers/inject-auth.js
│   │   ├── auth.spec.js
│   │   ├── dashboard.spec.js
│   │   ├── chatbot.spec.js
│   │   ├── sct.spec.js
│   │   └── security.spec.js
│   ├── playwright.config.js
│   ├── vite.config.js
│   └── Dockerfile
├── docs/                         # Documentacion tecnica
├── docker-compose.yml
└── .env.example
```

---

## 3. Backend — FastAPI

### Punto de entrada

`backend/app/main.py` registra los 11 routers bajo el prefijo `/api` y configura CORS desde la variable `CORS_ORIGINS`.

### Patron de endpoints

Todos los endpoints protegidos usan `Depends(get_current_user)` o `Depends(require_permission(PERM_X))`. El patron es:

```python
@router.get("/recurso")
def get_recurso(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_CASES)),
):
    ...
```

### Arranque Docker

`start.sh` ejecuta:
1. `alembic upgrade head` — aplica migraciones pendientes
2. `uvicorn app.main:app` con los flags pasados por `docker-compose.yml`

---

## 4. Frontend — React / Vite

### Gestion de sesion

El modulo `authClient.js` centraliza toda la logica de autenticacion:

- `saveAuthSession(payload)` — persiste `auth_token`, `user` y `role` en `localStorage`
- `authFetch(url, options)` — wrapper de `fetch` que inyecta el header `Authorization: Bearer <token>` y redirige a `/auth` en caso de 401
- `clearAuthSession()` — limpia localStorage y cierra sesion

Todas las llamadas a la API se realizan a traves de `api.js`, que a su vez usa `authFetch`.

### Rutas

| Ruta | Componente | Acceso |
|---|---|---|
| `/` | LandingPage | Publico |
| `/auth` | AuthPage | Publico |
| `/dashboard` | DashboardPage | Autenticado |
| `/dashboard/chat` | ChatbotPage | Autenticado |
| `/dashboard/sct` | SCTPage | Autenticado |
| `/dashboard/images` | ImagesPage | Autenticado |
| `/dashboard/cases` | CasesPage | Autenticado |
| `/dashboard/feedback` | FeedbackPage | Autenticado |
| `/dashboard/config` | ConfigPage | Admin/Docente |

### Configuracion de API en runtime (Docker)

El entrypoint Docker genera `/env-config.js` antes de iniciar Nginx:

```sh
window.__ASOFAMECH_CONFIG__ = { "API_BASE": "${API_BASE}" };
```

Esto permite cambiar la URL del backend sin reconstruir la imagen. `authClient.js` lee esta variable en orden: `window.__ASOFAMECH_CONFIG__.API_BASE` → `VITE_API_BASE` → `http://localhost:8001`.

---

## 5. Base de datos

### Motor

PostgreSQL 15 con la extension `pgvector` para busqueda de similitud semantica (usada por el modulo RAG).

### Tablas principales (13)

| Tabla | Descripcion |
|---|---|
| `users` | Usuarios con rol, estado de cuenta y aprobacion |
| `medical_images` | Imagenes WSI subidas (metadatos + ruta de tiles) |
| `cases` | Casos clinicos (CRUD docente/admin, lectura estudiante) |
| `documents` | Documentos del corpus RAG |
| `document_chunks` | Fragmentos indexados con embeddings pgvector |
| `chat_logs` | Historial de conversaciones del chatbot |
| `sct_tests` | Tests SCT guardados con sus items |
| `sct_attempts` | Intentos de estudiantes con puntaje calculado |
| `histopathology_sessions` | Sesiones de analisis ROI |
| `heatmap_jobs` | Cola de trabajos de heatmap |
| `activity_log` | Actividad de usuarios |
| `dashboard_stats` | Estadisticas agregadas |
| `usability_feedback` | Evaluaciones de usabilidad (1 por usuario) |

### Migraciones con Alembic

```bash
# Crear nueva migracion
alembic revision --autogenerate -m "descripcion"

# Aplicar migraciones pendientes
alembic upgrade head

# Ver estado actual
alembic current
```

Las migraciones se nombran con formato `NNNN_hash_descripcion.py` y estan en `backend/alembic/versions/`.

---

## 6. Autenticacion y RBAC

### Roles y permisos

| Permiso | Estudiante | Docente | Admin |
|---|:---:|:---:|:---:|
| use_platform | X | X | X |
| use_chat | X | X | X |
| use_histopathology | X | X | X |
| solve_sct | X | X | X |
| view_own_history | X | X | X |
| manage_cases | | X | X |
| manage_sct | | X | X |
| manage_rag | | X | X |
| manage_images | | X | X |
| view_feedback | | X | X |
| manage_users | | | X |
| manage_ai_config | | | X |
| delete_sensitive_resources | | | X |

### Flujo de registro

1. Primer usuario: se aprueba automaticamente y recibe rol `administrador`.
2. Usuarios siguientes: quedan en estado `pending` hasta que un administrador los aprueba desde el panel de gestion.

### Token JWT

Firmado con HMAC-SHA256. Payload incluye: `sub` (user_id), `email`, `name`, `role`. Expira segun `ASOFAMECH_ACCESS_TOKEN_EXPIRE_MINUTES` (defecto 720 min = 12 h).

---

## 7. Modulo RAG

### Flujo de indexacion

1. Docente/admin sube un documento (PDF, TXT) o lo crea manualmente via `/api/rag/documents`.
2. El backend fragmenta el texto en chunks y genera embeddings con un modelo de Hugging Face (sentence-transformers).
3. Los embeddings se almacenan en `document_chunks` como vectores pgvector.

### Flujo de consulta (chat)

1. El chatbot recibe la pregunta del usuario.
2. Se genera el embedding de la pregunta y se busca similitud en `document_chunks` usando `cosine_distance` de pgvector.
3. Los fragmentos mas relevantes (score > `RAG_MIN_NEURAL_SCORE`) se inyectan como contexto en el prompt de LLaMA 3.
4. La respuesta incluye metadatos de las fuentes utilizadas (`used_rag`, `source_chunks`).

### Endpoints RAG

| Metodo | Ruta | Descripcion |
|---|---|---|
| GET | `/api/rag/documents` | Listar documentos |
| POST | `/api/rag/documents` | Crear documento |
| POST | `/api/rag/documents/upload` | Subir archivo |
| PUT | `/api/rag/documents/{id}` | Actualizar |
| DELETE | `/api/rag/documents/{id}` | Eliminar |
| POST | `/api/rag/documents/{id}/reindex` | Reindexar un documento |
| POST | `/api/rag/reindex` | Reindexar corpus completo |
| GET | `/api/rag/search?q=&limit=` | Busqueda semantica |

---

## 8. Modulo histopatologico

### Componentes

- **OpenSeadragon** (frontend): renderiza imagenes WSI en formato DZI (Deep Zoom Image) con navegacion por tiles.
- **Fabric.js** (frontend): dibuja y gestiona regiones de interes (ROI) sobre el visor.
- **Backend**: convierte archivos WSI subidos a tiles DZI con `openslide`, extrae parches del ROI, clasifica con el modelo entrenado.

### Pipeline de clasificacion

1. El usuario dibuja un ROI en el visor.
2. El frontend envia las coordenadas al backend (`POST /api/histopathology/analyze`).
3. El backend extrae parches del ROI, aplica control de calidad (fraccion de tejido, fraccion nuclear, etc.).
4. CONCH genera embeddings de los parches.
5. La cabeza clasificadora binaria predice metastasis por parche.
6. El backend agrega los resultados, genera un heatmap y devuelve la evaluacion formativa.

### Variables de entorno relevantes

```
HISTO_CLASSIFIER_CHECKPOINT     # Ruta al checkpoint .pt del clasificador
HISTO_CONCH_CHECKPOINT_REF      # Referencia Hugging Face del modelo CONCH
HISTO_HF_TOKEN                  # Token con acceso aprobado a MahmoodLab/CONCH
HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD   # Umbral de confianza (0-1, default 0.90)
HISTO_QC_MAX_WHITE_FRACTION     # Control de calidad de parches
```

---

## 9. Modulo SCT

El Script Concordance Test evalua razonamiento clinico mediante items de 5 opciones (-2 a +2).

### Flujo de generacion (docente)

1. Docente configura: area medica, dificultad (pregrado/internado/residente), numero de items.
2. El backend construye un prompt estructurado y llama a Ollama/LLaMA 3.
3. La respuesta JSON se valida y devuelve como `SCTResponse`.
4. El docente revisa, edita y guarda el test (estado `draft` o `published`).

### Flujo de resolucion (estudiante)

1. Estudiante selecciona un test publicado.
2. Por cada item, selecciona su respuesta en la escala -2 a +2.
3. Al finalizar, el backend calcula el puntaje por concordancia con expertos y persiste el intento.

### Scoring

```
puntaje_item = 1.0 si respuesta == correct_answer, 0.0 si no
puntaje_test = (aciertos / total_items) * 100
```

### Endpoints SCT principales

| Metodo | Ruta | Descripcion |
|---|---|---|
| POST | `/api/sct/generate` | Generar items con IA |
| POST | `/api/sct/save` | Guardar test |
| GET | `/api/sct/list` | Listar tests |
| GET | `/api/sct/{id}` | Detalle de test |
| PATCH | `/api/sct/{id}` | Actualizar estado/nombre |
| DELETE | `/api/sct/{id}` | Eliminar |
| POST | `/api/sct/{id}/attempt` | Registrar intento |
| GET | `/api/sct/my-attempts` | Historial del usuario |
| GET | `/api/sct/admin/attempts` | Todos los intentos (docente/admin) |

---

## 10. Chatbot / Asistente IA

### Arquitectura

```
Usuario → POST /api/chat → RAG retrieval → Prompt LLaMA 3 → Ollama → Respuesta
```

### Prompt engineering

El backend construye un prompt con:
- Instrucciones de rol (asistente educativo medico, solo responde temas medicos)
- Contexto RAG (fragmentos de documentos relevantes)
- Historial de la conversacion actual
- Pregunta del usuario

### Tipos de respuesta

| Tipo | Descripcion |
|---|---|
| `answer` | Respuesta educativa normal |
| `out_of_scope` | Tema fuera del ambito medico |
| `ambiguous` | Consulta ambigua que requiere clarificacion |

### Limitaciones de tasa

El backend implementa rate limiting para proteger el servicio Ollama. Los estudiantes tienen limites mas bajos que docentes/admin (configurable via variables de entorno).

---

## 11. Flujo de datos end-to-end

### Consulta al chatbot con RAG

```
1. Frontend → authFetch POST /api/chat { text: "..." }
2. Backend  → Genera embedding de la pregunta
3. Backend  → SELECT chunks ORDER BY embedding <=> query_vec LIMIT 4
4. Backend  → Construye prompt con chunks recuperados
5. Backend  → POST http://ollama:11434/api/generate
6. Backend  → { messages: [...], used_rag: true, source_chunks: [...] }
7. Frontend → Renderiza respuesta con fuentes citadas
```

### Analisis de ROI histopatologico

```
1. Frontend → Usuario dibuja ROI con Fabric.js
2. Frontend → POST /api/histopathology/analyze { roi_coords, image_id }
3. Backend  → Extrae parches del ROI (OpenSlide)
4. Backend  → Aplica QC (filtra parches de baja calidad)
5. Backend  → CONCH genera embeddings por parche
6. Backend  → Clasificador binario predice metastasis
7. Backend  → Agrega resultados → respuesta formativa + heatmap
8. Frontend → OpenSeadragon muestra heatmap superpuesto
```

---

## 12. Variables de entorno de referencia

Ver `.env.example` en la raiz del repositorio para la lista completa con descripciones y valores por defecto.

Las variables de entorno criticas que NO deben omitirse en produccion:

```
ASOFAMECH_JWT_SECRET          # OBLIGATORIO — sin esto el backend usa valor inseguro
HISTO_HF_TOKEN                # Requerido para descargar pesos CONCH
CORS_ORIGINS                  # Definir el dominio de produccion
```

---

## 13. Pruebas

### Backend — pytest (27 archivos)

```bash
# Todos los tests
pytest tests/ -v

# Un modulo especifico
pytest tests/test_feedback.py -v
pytest tests/test_sct_scoring.py -v

# Con cobertura (requiere pytest-cov)
pytest tests/ --cov=app --cov-report=html
```

Los tests de histopatologia y RAG neural usan mocks para no requerir GPU ni modelos descargados.

### Frontend — Playwright (35 tests)

```bash
cd frontend

# Suite completa (headless)
$env:E2E_ADMIN_EMAIL="admin@dominio.com"; $env:E2E_ADMIN_PASS="contraseña"
npm run test:e2e

# Con navegador visible
npm run test:e2e:headed

# Interfaz grafica interactiva
npm run test:e2e:ui

# Ver reporte HTML
npm run test:e2e:report
```

El `global-setup.js` crea un usuario estudiante de prueba automaticamente via la API de administracion.

---

## 14. Migraciones

### Migraciones existentes

| Archivo | Descripcion |
|---|---|
| `0001_..._initial_schema.py` | Esquema inicial completo (13 tablas + pgvector) |
| `0002_..._sct_status_created_by.py` | Estado y autor en tests SCT |
| `0003_..._extend_cases_table.py` | Campos extendidos en casos clinicos |
| `0004_..._create_usability_feedback.py` | Tabla de evaluaciones de usabilidad |

### Agregar una nueva migracion

```bash
# 1. Modificar models.py con los nuevos campos/tablas
# 2. Generar la migracion
cd backend
alembic revision --autogenerate -m "descripcion_del_cambio"
# 3. Revisar el archivo generado en alembic/versions/
# 4. Aplicar
alembic upgrade head
```

En Docker, las migraciones se aplican automaticamente en cada arranque del backend.
