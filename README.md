# 🏥 MediChat - Chatbot Educativo de Tuberculosis

Sistema de chatbot médico educativo basado en IA para consultas sobre tuberculosis y otras patologías. Integra Rasa, LLaMA 3 y sistema RAG (Retrieval-Augmented Generation) con casos clínicos.

## 🚀 Características

- **Asistente conversacional** basado en Rasa 3.6
- **Integración LLaMA 3** (8B) vía Ollama para respuestas médicas
- **Sistema RAG** con base de datos de casos clínicos
- **API REST** con FastAPI
- **Interfaz web moderna** con React + Vite
- **Arquitectura dockerizada** completa

## 🏗️ Arquitectura

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Frontend  │─────▶│   Backend    │─────▶│  PostgreSQL │
│  React+Vite │      │   FastAPI    │      │     DB      │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │     Rasa     │
                     │   + Actions  │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │    Ollama    │
                     │   LLaMA 3    │
                     └──────────────┘
```

## 📋 Requisitos Previos

- Docker Desktop
- Git
- 8GB+ RAM disponible (para LLaMA 3)

## 🔧 Instalación

1. **Clonar el repositorio**
```bash
git clone https://github.com/EstebanSalgad0/chatbot_tb.git
cd chatbot_tb
```

2. **Iniciar los servicios con Docker Compose**
```bash
docker-compose up -d
```

3. **Esperar a que Ollama descargue LLaMA 3** (primera vez, ~4GB)
```bash
docker logs -f tb_ollama
```

4. **Verificar que todos los contenedores estén corriendo**
```bash
docker ps
```

## 🌐 Acceso a los Servicios

| Servicio | URL | Descripción |
|----------|-----|-------------|
| Frontend | http://localhost:3000 | Interfaz web del chatbot |
| Backend API | http://localhost:8001 | API REST FastAPI |
| Rasa | http://localhost:5005 | Servidor Rasa |
| Ollama | http://localhost:11434 | Servicio LLaMA 3 |
| PostgreSQL | localhost:5432 | Base de datos |

## 📚 Estructura del Proyecto

```
chatbot_tb/
├── backend/              # API FastAPI
│   ├── app/
│   │   ├── main.py      # Punto de entrada
│   │   ├── db.py        # Configuración DB
│   │   ├── models.py    # Modelos SQLAlchemy
│   │   ├── schemas.py   # Schemas Pydantic
│   │   └── routers/
│   │       ├── cases.py # Endpoints casos clínicos
│   │       └── chat.py  # Endpoints chat
│   └── Dockerfile
│
├── Chatbot/             # Rasa Bot
│   ├── actions/
│   │   └── actions.py   # Custom actions + RAG
│   ├── data/
│   │   ├── nlu.yml      # Datos de entrenamiento
│   │   ├── rules.yml    # Reglas de conversación
│   │   └── stories.yml  # Historias de ejemplo
│   ├── domain.yml       # Dominio del bot
│   ├── config.yml       # Configuración Rasa
│   └── endpoints.yml    # Endpoints externos
│
├── frontend/            # React App
│   ├── src/
│   │   ├── components/  # Componentes React
│   │   ├── pages/       # Páginas
│   │   ├── api.js       # Cliente API
│   │   ├── app.jsx      # App principal
│   │   └── styles.css   # Estilos globales
│   └── Dockerfile
│
├── llm_service/         # Servicio Ollama
│   ├── main.py          # Servidor LLaMA 3
│   └── Dockerfile
│
└── docker-compose.yml   # Orquestación servicios
```

## 💬 Uso del Chatbot

El chatbot puede responder preguntas sobre:

- **Tuberculosis**: síntomas, diagnóstico, tratamiento
- **Medicina general**: prevención, enfermedades
- **Casos clínicos**: TB pulmonar, meningitis, pleural

### Ejemplos de preguntas:

- "¿Cuáles son los síntomas de la tuberculosis?"
- "¿Qué es la prevención médica?"
- "Explica sobre el tratamiento de la TB meníngea"
- "¿Cómo se diagnostica la tuberculosis pleural?"

## 🔄 Sistema RAG

El sistema RAG (Retrieval-Augmented Generation) funciona:

1. Usuario hace pregunta
2. Backend busca casos clínicos relevantes en PostgreSQL
3. Rasa consulta el backend por casos relacionados
4. LLaMA 3 genera respuesta enriquecida con contexto de casos
5. Respuesta se muestra al usuario

## 🛠️ Comandos Útiles

### Ver logs de un servicio
```bash
docker logs -f tb_frontend
docker logs -f tb_backend
docker logs -f tb_rasa
```

### Reiniciar un servicio
```bash
docker-compose restart frontend
docker-compose restart backend
```

### Reconstruir un servicio
```bash
docker-compose up -d --build frontend
```

### Entrenar modelo Rasa
```bash
docker exec -it tb_rasa rasa train
```

### Acceder a la DB
```bash
docker exec -it tb_db psql -U postgres -d chatbot_tb
```

## 🧪 Testing

### Probar endpoint de chat
```powershell
$message = '{"text": "¿Qué es la tuberculosis?"}'
Invoke-RestMethod -Uri http://localhost:8001/api/chat -Method POST -Body $message -ContentType "application/json"
```

### Probar búsqueda de casos
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/api/cases/search?query=pulmonar" -Method GET
```

## 📝 Base de Datos

### Casos clínicos incluidos:

1. **Tuberculosis Pulmonar**
   - Tos persistente, hemoptisis, pérdida de peso
   
2. **Tuberculosis Meníngea**
   - Cefalea intensa, rigidez de nuca, fiebre
   
3. **Tuberculosis Pleural**
   - Dolor torácico, disnea, derrame pleural

## 🔐 Variables de Entorno

El proyecto usa estas variables (configuradas en `docker-compose.yml`):

```yaml
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=chatbot_tb

# Backend
DATABASE_URL=postgresql://postgres:postgres@db:5432/chatbot_tb
RASA_URL=http://rasa:5005

# LLM Service
OLLAMA_URL=http://ollama:11434
```

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Añade nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es solo para fines educativos. No reemplaza la consulta médica profesional.

## 👨‍💻 Autor

Esteban Salgado

## 🙏 Agradecimientos

- Rasa Open Source
- Meta AI (LLaMA 3)
- Ollama
- FastAPI
- React
