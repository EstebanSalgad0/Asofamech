# 🏥 MediChat - Chatbot Educativo de Tuberculosis

Sistema de chatbot médico educativo basado en IA para consultas sobre tuberculosis y otras patologías. Integra FastAPI, LLaMA 3 vía Ollama y sistema RAG (Retrieval-Augmented Generation) con casos clínicos.

## 🚀 Características

- **Asistente conversacional** con Ollama (LLaMA 3)
- **Integración LLaMA 3** (8B) vía Ollama para respuestas médicas
- **Sistema RAG** con base de datos de casos clínicos
- **Módulo SCT** (Script Concordance Test) para evaluación del razonamiento clínico
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
git clone https://github.com/EstebanSalgad0/asofamech.git
cd asofamech
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
| Ollama | http://localhost:11434 | Servicio LLaMA 3 |
| PostgreSQL | localhost:5432 | Base de datos |

## 📚 Estructura del Proyecto

```
asofamech/
├── backend/              # API FastAPI
│   ├── app/
│   │   ├── main.py      # Punto de entrada
│   │   ├── db.py        # Configuración DB
│   │   ├── models.py    # Modelos SQLAlchemy
│   │   ├── schemas.py   # Schemas Pydantic
│   │   └── routers/
│   │       ├── cases.py # Endpoints casos clínicos
│   │       ├── chat.py  # Endpoints chat (Ollama)
│   │       └── sct.py   # Endpoints SCT
│   └── Dockerfile
│
├── frontend/             # React App
│   ├── src/
│   │   ├── components/  # Componentes React
│   │   ├── pages/       # Páginas
│   │   ├── api.js       # Cliente API
│   │   ├── app.jsx      # App principal
│   │   └── styles.css   # Estilos globales
│   └── Dockerfile
│
├── docs/                 # Documentación del proyecto
├── uploads/              # Archivos subidos y tiles generados
└── docker-compose.yml    # Orquestación servicios
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

## 🧪 Módulo SCT (Script Concordance Test)

El sistema incluye un módulo de **evaluación del razonamiento clínico** mediante SCT:

### ¿Qué es el SCT?
El Script Concordance Test evalúa cómo los estudiantes ajustan sus hipótesis diagnósticas cuando reciben nueva información clínica.

### Características:
- ✅ **Generación automática** de ítems con LLaMA 3
- ✅ **Configuración personalizada**: nivel de dificultad y enfoque
- ✅ **Escala de respuesta** -2 a +2 (descarta ↔ apoya fuertemente)
- ✅ **Retroalimentación detallada** con explicaciones médicas
- ✅ **Puntuación automática** y revisión de respuestas

### Uso:
1. Accede a la sección SCT en http://localhost:3000
2. Configura número de ítems, dificultad (pregrado/internado/residente) y enfoque
3. Genera test con IA o carga un ejemplo
4. Responde cada ítem considerando cómo la nueva información afecta tu hipótesis
5. Revisa resultados con explicaciones detalladas

Ver documentación completa en [SCT_MODULE.md](SCT_MODULE.md)
- "¿Cómo se diagnostica la tuberculosis pleural?"

## 🔄 Sistema RAG

El sistema RAG (Retrieval-Augmented Generation) funciona:

1. Usuario hace pregunta
2. Backend busca casos clínicos relevantes en PostgreSQL
3. Backend construye contexto clínico con los casos encontrados
4. LLaMA 3 genera respuesta enriquecida con contexto de casos
5. Respuesta se muestra al usuario

## 🛠️ Comandos Útiles

### Ver logs de un servicio
```bash
docker logs -f tb_frontend
docker logs -f tb_backend
docker logs -f tb_ollama
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

### Descargar modelo en Ollama
```bash
docker exec -it asofamech_ollama ollama pull llama3:8b
```

### Acceder a la DB
```bash
docker exec -it asofamech_db psql -U app_user -d app_db
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
POSTGRES_USER=app_user
POSTGRES_PASSWORD=app_pass
POSTGRES_DB=app_db

# Backend
DATABASE_URL=postgresql://app_user:app_pass@db:5432/app_db
OLLAMA_URL=http://ollama:11434
LLM_MODEL=llama3:8b

# Frontend
VITE_API_BASE=http://localhost:8001
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

- Meta AI (LLaMA 3)
- Ollama
- FastAPI
- React
