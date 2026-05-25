# ASOFAMECH — Guia de Desarrollo Local

Esta guia describe como levantar el entorno de desarrollo con hot-reload para frontend y backend, manteniendo solo los servicios de infraestructura (base de datos y Ollama) en Docker.

---

## Inicio rapido

### 1. Levantar servicios de infraestructura

```bash
docker compose up -d db ollama
```

### 2. Backend (Terminal 1)

```bash
cd backend
python -m venv .venv

# Activar entorno virtual
# Linux/Mac:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# Aplicar migraciones
DATABASE_URL=postgresql://app_user:app_pass@localhost:5432/app_db \
alembic upgrade head

# Iniciar servidor con hot-reload
DATABASE_URL=postgresql://app_user:app_pass@localhost:5432/app_db \
OLLAMA_URL=http://localhost:11434 \
LLM_MODEL=llama3:8b \
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### 3. Frontend (Terminal 2)

```bash
cd frontend
npm install
VITE_API_BASE=http://localhost:8001 npm run dev
```

Frontend disponible en: `http://localhost:3000`
Backend API disponible en: `http://localhost:8001`
Documentacion API: `http://localhost:8001/docs`

---

## Servicios y puertos

| Servicio | Puerto | Modo |
|---|---|---|
| Frontend (Vite dev) | 3000 | Local |
| Backend (FastAPI) | 8001 | Local |
| PostgreSQL | 5432 | Docker |
| Ollama (LLaMA 3) | 11434 | Docker |

---

## Descargar el modelo LLM (primera vez)

```bash
docker exec -it asofamech_ollama ollama pull llama3:8b
```

---

## Variables de entorno para desarrollo local

### Backend (minimas requeridas)

```
DATABASE_URL=postgresql://app_user:app_pass@localhost:5432/app_db
OLLAMA_URL=http://localhost:11434
LLM_MODEL=llama3:8b
```

Variables opcionales para el modulo histopatologico:

```
HISTO_HF_TOKEN=<token-huggingface>
HISTO_CLASSIFIER_CHECKPOINT=<ruta-al-checkpoint>
```

### Frontend

```
VITE_API_BASE=http://localhost:8001
```

Crear `frontend/.env.local` con el contenido anterior para no tener que pasarlo en cada comando.

---

## Detener servicios

```bash
# Detener Docker
docker compose down

# Detener frontend/backend: Ctrl+C en cada terminal
```

---

## Ejecutar pruebas

### Backend

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

### Frontend — E2E con Playwright

```bash
cd frontend

# Instalar navegadores (primera vez)
npx playwright install chromium

# Ejecutar suite completa
$env:E2E_ADMIN_EMAIL="admin@dominio.com"
$env:E2E_ADMIN_PASS="contraseña"
npm run test:e2e
```

---

## Migraciones en desarrollo local

```bash
cd backend
source .venv/bin/activate

# Ver estado actual
DATABASE_URL=postgresql://app_user:app_pass@localhost:5432/app_db \
alembic current

# Crear nueva migracion
DATABASE_URL=postgresql://app_user:app_pass@localhost:5432/app_db \
alembic revision --autogenerate -m "descripcion"

# Aplicar migraciones
DATABASE_URL=postgresql://app_user:app_pass@localhost:5432/app_db \
alembic upgrade head
```

---

## Build completo con Docker (produccion local)

```bash
docker compose up --build -d
```

El primer build tarda varios minutos por la instalacion de dependencias de IA.

---

## Ventajas del modo desarrollo local

- Hot-reload automatico en frontend y backend (cambios sin reconstruir imagenes).
- Los servicios pesados (DB, LLM) quedan en Docker.
- Acceso directo a logs del backend en la terminal.
- Depuracion con el debugger del IDE.
