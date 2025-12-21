# ASOFAMECH - Guía de Desarrollo Local

> **Nota**: Proyecto renombrado de chatbot_tb a asofamech

## 🚀 Inicio Rápido

### 1. Iniciar Servicios Docker (DB, Rasa, Ollama)
```bash
docker-compose up -d
```
O usa el script:
```bash
start-services.bat
```

### 2. Iniciar Frontend (Terminal 1)
```bash
cd frontend
npm install  # Solo la primera vez
npm run dev
```
Frontend disponible en: http://localhost:3000

### 3. Iniciar Backend (Terminal 2)
```bash
cd backend
pip install -r requirements.txt  # Solo la primera vez
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```
Backend API disponible en: http://localhost:8001

## 🛑 Detener Todo

Para detener los servicios Docker:
```bash
docker-compose down
```
O usa:
```bash
stop-services.bat
```

Para detener frontend/backend, simplemente presiona `Ctrl+C` en cada terminal.

## 📝 Servicios y Puertos

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| Frontend | 3000 | Interfaz React (desarrollo local) |
| Backend | 8001 | API FastAPI (desarrollo local) |
| PostgreSQL | 5432 | Base de datos (Docker) |
| Rasa | 5005 | Chatbot engine (Docker) |
| Ollama | 11434 | Modelo AI (Docker) |

## 🔧 Configuración

### Frontend (.env)
```
VITE_API_BASE=http://localhost:8001
```

### Backend (.env)
```
DATABASE_URL=postgresql://app_user:app_pass@localhost:5432/app_db
RASA_URL=http://localhost:5005/webhooks/rest/webhook
OLLAMA_HOST=http://localhost:11434
```

## ✅ Ventajas del Desarrollo Local

- ✅ Hot reload automático en frontend (cambios instantáneos)
- ✅ Hot reload automático en backend con `--reload`
- ✅ No necesitas rebuilder containers
- ✅ Más rápido para desarrollo
- ✅ Los servicios pesados (DB, AI) siguen en Docker
