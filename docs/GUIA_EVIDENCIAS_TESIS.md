# Guia de Evidencias para Tesis — ASOFAMECH

Esta guia describe que capturas de pantalla tomar, que comandos ejecutar y que datos ocultar al documentar el funcionamiento del prototipo para la tesis.

---

## Indice

1. [Preparacion del entorno](#1-preparacion-del-entorno)
2. [Evidencias del sistema en ejecucion](#2-evidencias-del-sistema-en-ejecucion)
3. [Evidencias por modulo](#3-evidencias-por-modulo)
4. [Evidencias de pruebas automatizadas](#4-evidencias-de-pruebas-automatizadas)
5. [Evidencias de arquitectura y base de datos](#5-evidencias-de-arquitectura-y-base-datos)
6. [Datos a ocultar antes de capturar](#6-datos-a-ocultar-antes-de-capturar)
7. [Checklist de evidencias](#7-checklist-de-evidencias)

---

## 1. Preparacion del entorno

Antes de tomar capturas, verificar que el sistema este funcionando correctamente.

### Verificar servicios activos

```bash
# Verificar contenedores Docker
docker compose ps

# Verificar respuesta del backend
curl http://localhost:8001/health

# Verificar que el frontend carga
curl -s http://localhost:3000 -o /dev/null -w "%{http_code}"
```

Salida esperada para health: `{"status":"ok"}`
Salida esperada para frontend: `200`

### Verificar modelo LLM

```bash
docker exec -it asofamech_ollama ollama list
```

Debe aparecer `llama3:8b` en la lista.

### Verificar base de datos

```bash
docker exec -it asofamech_db psql -U app_user -d app_db -c "\dt"
```

Debe mostrar las 13 tablas del esquema.

---

## 2. Evidencias del sistema en ejecucion

### Captura 1 — Servicios Docker activos

Ejecutar el siguiente comando y capturar la salida completa:

```bash
docker compose ps
```

La captura debe mostrar los 4 servicios (db, backend, frontend, ollama) con estado `running` o `healthy`.

### Captura 2 — Health check del backend

```bash
curl http://localhost:8001/health
# Salida: {"status":"ok"}
```

O abrir `http://localhost:8001/health` en el navegador y capturar la respuesta JSON.

### Captura 3 — Documentacion automatica de la API

Abrir `http://localhost:8001/docs` en el navegador. Capturar la pagina completa de Swagger UI con todos los endpoints visibles. Esta captura evidencia los 11 modulos de la API REST.

### Captura 4 — Logs de arranque del backend

```bash
docker compose logs backend --tail=30
```

La salida debe mostrar:
- Ejecucion de migraciones Alembic.
- Mensaje de inicio del servidor uvicorn.
- Confirmacion de modulos cargados.

---

## 3. Evidencias por modulo

### Modulo de autenticacion

**Captura 5 — Pagina de login**
- URL: `http://localhost:3000/auth`
- Mostrar el formulario de inicio de sesion completo.
- Ocultar cualquier correo real antes de capturar.

**Captura 6 — Dashboard post-login**
- Iniciar sesion con un usuario de prueba.
- Capturar el panel principal con la barra lateral completa visible.
- Asegurarse de que se ven los modulos de navegacion.

### Modulo de chatbot con RAG

**Captura 7 — Interfaz del chatbot**
- URL: `http://localhost:3000/dashboard/chat`
- Capturar el panel de tres columnas: conversaciones, chat y contexto RAG.

**Captura 8 — Respuesta del chatbot con fuentes RAG**
- Enviar una consulta medica (ejemplo: *"Explica el tratamiento de primera linea para tuberculosis pulmonar"*).
- Capturar la respuesta completa del asistente.
- Asegurarse de que el panel derecho muestra las fuentes citadas con porcentaje de relevancia.
- La captura evidencia el funcionamiento del sistema RAG.

**Captura 9 — Respuesta fuera de alcance**
- Enviar una pregunta no medica (ejemplo: *"¿Cuánto vale un dolar hoy?"*).
- Capturar la respuesta del asistente mostrando el aviso de fuera de alcance.

### Modulo histopatologico

**Captura 10 — Visor de imagenes cargado**
- URL: `http://localhost:3000/dashboard/images`
- Abrir una imagen histopatologica.
- Capturar el visor OpenSeadragon con la imagen cargada a zoom intermedio.

**Captura 11 — ROI dibujado**
- Dibujar una region de interes sobre el tejido.
- Capturar el visor con el ROI visible antes de analizar.

**Captura 12 — Resultado del analisis con heatmap**
- Despues de analizar el ROI, capturar el resultado completo.
- Debe mostrar: clasificacion formativa, nivel de confianza, y heatmap superpuesto.

**Captura alternativa — Log del backend durante analisis**

```bash
docker compose logs backend --tail=50 | grep -i "histopatol\|roi\|heatmap\|patch"
```

### Modulo SCT

**Captura 13 — Vista de tests disponibles (estudiante)**
- Iniciar sesion con un usuario estudiante.
- Capturar la biblioteca de tests publicados.

**Captura 14 — Item SCT durante resolucion**
- Abrir un test y capturar un item completo con la escala de respuesta visible.
- El item debe mostrar: caso clinico, hipotesis, nueva informacion y las opciones de respuesta.

**Captura 15 — Resultado del test SCT**
- Completar un test y capturar la pantalla de resultados.
- Debe mostrar: puntaje final, numero de items correctos y comparacion con respuestas de referencia.

**Captura 16 — Panel docente con intentos de estudiantes**
- Iniciar sesion con docente o admin.
- Capturar la tabla de intentos de estudiantes.
- Ocultar nombres y correos reales.

### Modulo de casos clinicos

**Captura 17 — Lista de casos (vista estudiante)**
- Capturar la cuadricula de casos con filtros visibles.

**Captura 18 — Detalle de un caso clinico**
- Abrir un caso publicado y capturar el modal de detalle completo.
- Debe mostrar al menos: titulo, descripcion, cuerpo y objetivos de aprendizaje.

**Captura 19 — Formulario de creacion de caso (vista docente/admin)**
- Iniciar sesion con docente o admin.
- Abrir el formulario de nuevo caso.
- Capturar el formulario completo con todos los campos visibles.

### Modulo de evaluacion de usabilidad

**Captura 20 — Formulario de evaluacion (vista estudiante)**
- Capturar el formulario con las 6 dimensiones y la escala de botones.

**Captura 21 — Resumen de evaluaciones (vista docente/admin)**
- Iniciar sesion con docente o admin.
- Capturar el panel de resumen con promedios y desglose por rol.

---

## 4. Evidencias de pruebas automatizadas

### Backend — pytest

**Captura 22 — Ejecucion de tests backend**

```bash
docker exec -it asofamech_backend pytest tests/ -v --tb=short 2>&1 | head -80
```

Capturar la salida completa mostrando la lista de tests y el resumen final.

**Captura 23 — Resumen de resultados**

```bash
docker exec -it asofamech_backend pytest tests/ -v --tb=short 2>&1 | tail -20
```

La captura debe mostrar el numero de tests pasados, fallados y omitidos.

### Frontend — Playwright E2E

**Captura 24 — Ejecucion de suite E2E**

```powershell
# Desde la carpeta frontend/
$env:E2E_ADMIN_EMAIL="admin@dominio.com"
$env:E2E_ADMIN_PASS="contraseña"
npm run test:e2e
```

Capturar la salida completa de la terminal con todos los tests listados y el resultado final.

**Captura 25 — Reporte HTML de Playwright**

```bash
npm run test:e2e:report
```

El reporte se abre en el navegador. Capturar la pagina principal del reporte mostrando el resumen de resultados por modulo.

---

## 5. Evidencias de arquitectura y base de datos

### Esquema de la base de datos

**Captura 26 — Listado de tablas**

```bash
docker exec -it asofamech_db psql -U app_user -d app_db -c "\dt"
```

**Captura 27 — Esquema de una tabla clave (por ejemplo, users)**

```bash
docker exec -it asofamech_db psql -U app_user -d app_db -c "\d users"
```

Repetir para `sct_tests`, `cases`, `usability_feedback` si se requiere mayor detalle.

**Captura 28 — Migraciones Alembic aplicadas**

```bash
docker exec -it asofamech_backend alembic history --verbose
```

### Estructura del repositorio

**Captura 29 — Estructura de archivos**

```bash
# Desde la raiz del proyecto
find . -not -path './.git/*' -not -path './node_modules/*' \
       -not -path './.venv/*' -not -path './backend/artifacts/*' \
       -not -path './backend/data/*' \
       -type f -name "*.py" -o -type f -name "*.jsx" \
       -o -type f -name "*.js" | sort | head -60
```

O capturar el arbol de carpetas desde el explorador de archivos del IDE.

### Variables de entorno (sin secretos)

**Captura 30 — Archivo .env.example**

Abrir `.env.example` en el editor y capturar el contenido completo. Este archivo no contiene secretos reales, por lo que puede mostrarse directamente.

---

## 6. Datos a ocultar antes de capturar

Antes de tomar cualquier captura de pantalla, verificar y ocultar:

| Dato | Metodo de ocultacion |
|---|---|
| Correos electronicos reales | Reemplazar con `usuario@dominio.com` o usar herramienta de edicion |
| Nombres completos de usuarios reales | Reemplazar con "Usuario Estudiante" o "Docente Demo" |
| Tokens JWT | Nunca visible en capturas; si aparece en logs, recortar la captura |
| `HISTO_HF_TOKEN` | No capturar ninguna pantalla que muestre este valor |
| `ASOFAMECH_JWT_SECRET` | No capturar ninguna pantalla que muestre este valor |
| Contrasenas | Nunca mostrar en capturas; los campos de tipo password ocultan por defecto |
| IPs de produccion | Usar `localhost` o reemplazar con `[IP_SERVIDOR]` |
| Credenciales de BD | `app_user:app_pass` es el valor por defecto de desarrollo, aceptable en tesis |

### Herramientas de edicion recomendadas

- **Sistemas Windows:** Recorte y Anotacion, o MS Paint para pixelar areas.
- **Sistemas Linux/Mac:** GIMP, Flameshot (con funcion de blur).
- **Edicion en linea:** Photopea.com (sin instalacion).

---

## 7. Checklist de evidencias

Marcar cada item al completarlo:

### Sistema general
- [ ] Captura 1 — `docker compose ps` con 4 servicios activos
- [ ] Captura 2 — Health check del backend
- [ ] Captura 3 — Swagger UI con endpoints visibles
- [ ] Captura 4 — Logs de arranque del backend

### Autenticacion
- [ ] Captura 5 — Pagina de login
- [ ] Captura 6 — Dashboard post-login con sidebar

### Chatbot con RAG
- [ ] Captura 7 — Interfaz del chatbot (tres paneles)
- [ ] Captura 8 — Respuesta con fuentes RAG citadas
- [ ] Captura 9 — Respuesta fuera de alcance

### Histopatologia
- [ ] Captura 10 — Visor con imagen cargada
- [ ] Captura 11 — ROI dibujado sobre tejido
- [ ] Captura 12 — Resultado con heatmap

### SCT
- [ ] Captura 13 — Lista de tests (estudiante)
- [ ] Captura 14 — Item SCT durante resolucion
- [ ] Captura 15 — Resultados del test
- [ ] Captura 16 — Panel docente con intentos

### Casos clinicos
- [ ] Captura 17 — Lista de casos
- [ ] Captura 18 — Detalle de un caso
- [ ] Captura 19 — Formulario de creacion (docente)

### Evaluacion de usabilidad
- [ ] Captura 20 — Formulario de evaluacion
- [ ] Captura 21 — Resumen de evaluaciones (docente)

### Pruebas automatizadas
- [ ] Captura 22 — Ejecucion pytest con lista de tests
- [ ] Captura 23 — Resumen de resultados pytest
- [ ] Captura 24 — Ejecucion Playwright E2E
- [ ] Captura 25 — Reporte HTML Playwright

### Arquitectura y BD
- [ ] Captura 26 — `\dt` con lista de tablas
- [ ] Captura 27 — Esquema de tabla `users`
- [ ] Captura 28 — Historial de migraciones Alembic
- [ ] Captura 29 — Estructura de archivos del repositorio
- [ ] Captura 30 — Archivo `.env.example`
