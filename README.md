# ASOFAMECH — Plataforma Educativa Médica con Inteligencia Artificial

ASOFAMECH es un prototipo de plataforma educativa de medicina desarrollado como proyecto de tesis. Integra un asistente conversacional con RAG, evaluación de razonamiento clínico mediante SCT, análisis histopatológico asistido por IA y un módulo de gestión de casos clínicos, todo bajo control de acceso basado en roles.

> **Advertencia:** Esta plataforma es exclusivamente educativa. Los análisis de imágenes, respuestas del chatbot y evaluaciones no constituyen diagnóstico médico ni reemplazan el juicio clínico profesional.

---

## Tecnologias

| Capa | Tecnologia |
|---|---|
| Frontend | React 18, Vite 5, React Router 7 |
| Backend | FastAPI (Python 3.11), SQLAlchemy, Alembic |
| Base de datos | PostgreSQL 15 + extensión pgvector |
| Modelo LLM | Ollama — LLaMA 3 8B |
| IA histopatologica | CONCH (MahmoodLab) + clasificador PCam propio |
| Contenedores | Docker Compose (4 servicios) |
| Pruebas E2E | Playwright 1.60 |
| Pruebas backend | pytest |

---

## Requisitos previos

- **Docker Desktop** 4.x o superior (con soporte GPU opcional)
- **NVIDIA GPU** con drivers CUDA instalados (requerido para módulo histopatológico con IA; sin GPU el clasificador no estará disponible)
- **RAM:** mínimo 8 GB disponibles para LLaMA 3 (16 GB recomendados)
- **Disco:** mínimo 30 GB libres (modelo LLaMA 3 ~4 GB, imágenes Docker ~8 GB, tiles WSI variables)
- **Git**

---

## Instalación rapida con Docker Compose

### 1. Clonar el repositorio

```bash
git clone https://github.com/EstebanSalgad0/Asofamech.git
cd Asofamech
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` y configurar al menos:

```
ASOFAMECH_JWT_SECRET=<secreto-aleatorio-de-64-caracteres>
HISTO_HF_TOKEN=<token-de-huggingface-con-acceso-a-MahmoodLab/CONCH>
```

Generar un secreto seguro:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Levantar los servicios

```bash
docker compose up -d
```

La primera vez descarga LLaMA 3 (~4 GB) y los pesos CONCH (~1.5 GB). El backend puede tardar hasta 3 minutos en pasar el health check.

### 4. Descargar el modelo LLM (primera vez)

```bash
docker exec -it asofamech_ollama ollama pull llama3:8b
```

### 5. Verificar que todos los servicios estan activos

```bash
docker compose ps
curl http://localhost:8001/health
```

Respuesta esperada: `{"status":"ok"}`

### 6. Acceder a la plataforma

| Servicio | URL |
|---|---|
| Plataforma web | http://localhost:3000 |
| API REST (documentacion) | http://localhost:8001/docs |
| Ollama | http://localhost:11434 |
| PostgreSQL | localhost:5432 |

El primer usuario registrado se convierte automáticamente en administrador.

---

## Publicacion temporal con Cloudflare Tunnel

Para exponer la plataforma desde este equipo con una URL publica temporal:

```powershell
.\abrir_publicador.cmd
```

El publicador levanta Docker Compose, abre un tunel Cloudflare hacia
`http://localhost:3000`, configura el acceso publico por mismo origen, muestra
la URL y permite copiarla o detener el tunel desde una ventana simple.
Los scripts PowerShell de administracion estan en `scripts/`.

La URL `*.trycloudflare.com` cambia en cada sesion. Para la defensa, mantener
abierta la ventana del publicador mientras se use el acceso remoto.

Ver [docs/DEFENSA_DOS_EQUIPOS.md](docs/DEFENSA_DOS_EQUIPOS.md) para distinguir
lo que viaja por Git de lo que requiere backup y para el checklist de failover.

---

## Variables de entorno

Ver `.env.example` para la lista completa con descripciones. Las variables obligatorias son:

| Variable | Descripcion |
|---|---|
| `ASOFAMECH_JWT_SECRET` | Secreto HMAC-SHA256 para tokens JWT. Obligatorio en produccion. |
| `HISTO_HF_TOKEN` | Token de Hugging Face para descargar pesos CONCH. |
| `DATABASE_URL` | Cadena de conexion PostgreSQL. Gestionada automaticamente por Docker Compose. |
| `OLLAMA_URL` | URL del servicio Ollama. Por defecto `http://ollama:11434`. |
| `LLM_MODEL` | Modelo a usar. Por defecto `llama3:8b`. |
| `CORS_ORIGINS` | Origenes permitidos separados por coma. |

---

## Ejecucion en modo desarrollo (sin Docker para frontend/backend)

Util para desarrollo con hot-reload. Los servicios de infraestructura (DB y Ollama) siguen en Docker.

```bash
# Terminal 1 — Servicios de infraestructura
docker compose up -d db ollama

# Terminal 2 — Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
DATABASE_URL=postgresql://app_user:app_pass@localhost:5432/app_db \
OLLAMA_URL=http://localhost:11434 \
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Terminal 3 — Frontend
cd frontend
npm install
VITE_API_BASE=http://localhost:8001 npm run dev
```

---

## Migraciones de base de datos

Las migraciones se ejecutan automaticamente al iniciar el contenedor backend (`start.sh` llama a `alembic upgrade head`). Para ejecutarlas manualmente:

```bash
docker exec -it asofamech_backend alembic upgrade head
```

---

## Pruebas

### Backend (pytest)

```bash
# Dentro del contenedor
docker exec -it asofamech_backend pytest tests/ -v

# En entorno local (requiere DB activa)
cd backend
pytest tests/ -v
```

### Frontend — pruebas E2E (Playwright)

Requiere frontend y backend activos en `localhost:3000` y `localhost:8001`.

```bash
cd frontend

# Primera ejecucion (con credenciales de admin existente)
$env:E2E_ADMIN_EMAIL="admin@dominio.com"
$env:E2E_ADMIN_PASS="contraseña"
npm run test:e2e

# Ver reporte HTML
npm run test:e2e:report
```

Ver `frontend/.env.test.example` para todas las variables de configuracion E2E.

### Build del frontend

```bash
cd frontend
npm run build
# Artefactos generados en frontend/dist/
```

### Rendimiento API - k6

Prueba liviana de endpoints principales:

```powershell
.\scripts\run_k6_smoke.ps1 -Email "admin@correo.cl" -IncludeAdmin
```

Para incluir el chat con Ollama sin exigir umbral de tiempo estricto:

```powershell
.\scripts\run_k6_smoke.ps1 -Email "usuario@correo.cl" -Vus 2 -Iterations 2 -MaxDuration "5m" -IncludeChat
```

Si quieres exigir una meta al chat, agrega `-ChatP95Ms`, por ejemplo
`-ChatP95Ms 120000`.

Ver [docs/PERFORMANCE_TESTS.md](docs/PERFORMANCE_TESTS.md).

---

## Estructura del proyecto

```
Asofamech/
├── backend/
│   ├── app/                  # Codigo FastAPI
│   │   ├── routers/          # 11 modulos de endpoints
│   │   ├── models.py         # Modelos ORM SQLAlchemy
│   │   ├── schemas.py        # Esquemas Pydantic
│   │   ├── auth.py           # RBAC y JWT
│   │   └── main.py           # Punto de entrada
│   ├── alembic/              # Migraciones de BD
│   ├── tests/                # 27 archivos de pruebas
│   ├── requirements*.txt     # Dependencias
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/            # 11 paginas React
│   │   ├── components/       # Componentes reutilizables
│   │   ├── api.js            # Funciones de llamada a API
│   │   └── authClient.js     # Gestion de sesion JWT
│   ├── e2e/                  # Tests Playwright
│   └── Dockerfile
├── docs/                     # Documentacion tecnica
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Comandos utiles

```bash
# Ver logs del backend en tiempo real
docker compose logs -f backend

# Reiniciar solo el backend
docker compose restart backend

# Acceder a la base de datos
docker exec -it asofamech_db psql -U app_user -d app_db

# Detener todos los servicios
docker compose down

# Detener y eliminar volumenes (borra la BD)
docker compose down -v
```

---

## Documentacion adicional

| Documento | Descripcion |
|---|---|
| [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | Guia completa para desarrolladores |
| [docs/MANUAL_ESTUDIANTE.md](docs/MANUAL_ESTUDIANTE.md) | Manual de usuario estudiante |
| [docs/MANUAL_DOCENTE_ADMIN.md](docs/MANUAL_DOCENTE_ADMIN.md) | Manual docente y administrador |
| [docs/MIGRACION_EQUIPOS.md](docs/MIGRACION_EQUIPOS.md) | Manual de transferencia e instalacion en otros equipos |
| [docs/GUIA_EVIDENCIAS_TESIS.md](docs/GUIA_EVIDENCIAS_TESIS.md) | Guia de capturas para tesis |
| [docs/SCT_MODULE.md](docs/SCT_MODULE.md) | Documentacion del modulo SCT |
| [docs/HISTOPATHOLOGY_AI.md](docs/HISTOPATHOLOGY_AI.md) | Entrenamiento del clasificador histopatologico |

---

## Autor

Esteban Salgado — Proyecto de tesis, 2026.

**Uso educativo exclusivo. No apto para diagnostico clinico.**
