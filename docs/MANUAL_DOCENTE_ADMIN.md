# Manual de Usuario — Docente y Administrador

Este manual describe las funciones de gestion disponibles para los roles de **Docente** y **Administrador** en la plataforma ASOFAMECH.

Los docentes tienen acceso a la gestion de contenido educativo (imagenes, casos, SCT, RAG). Los administradores tienen adicionalmente control sobre usuarios y configuracion del sistema.

---

## Indice

1. [Gestion de usuarios (solo Admin)](#1-gestion-de-usuarios-solo-admin)
2. [Gestion de imagenes histopatologicas](#2-gestion-de-imagenes-histopatologicas)
3. [Gestion de casos clinicos](#3-gestion-de-casos-clinicos)
4. [Gestion de documentos RAG](#4-gestion-de-documentos-rag)
5. [Gestion de tests SCT](#5-gestion-de-tests-sct)
6. [Evaluacion de usabilidad](#6-evaluacion-de-usabilidad)
7. [Configuracion del sistema (solo Admin)](#7-configuracion-del-sistema-solo-admin)
8. [Historial de actividad](#8-historial-de-actividad)

---

## 1. Gestion de usuarios (solo Admin)

La gestion de usuarios requiere el rol **Administrador**. Se accede desde **Configuracion** en la barra lateral.

### Aprobar o rechazar cuentas pendientes

Cuando un nuevo usuario se registra, su cuenta queda en estado **pendiente** hasta ser revisada:

1. Ir a **Configuracion** → seccion **Usuarios pendientes**.
2. Revisar los datos del solicitante (nombre, correo, rol solicitado).
3. Hacer clic en **Aprobar** para activar la cuenta, o en **Rechazar** para denegarla.

El sistema puede enviar notificacion por correo electronico si el SMTP esta configurado.

### Modificar roles y estado de cuentas

1. Ir a **Configuracion** → seccion **Todos los usuarios**.
2. Usar el buscador para encontrar a un usuario por nombre, correo o rol.
3. Hacer clic sobre el usuario para editar su rol o desactivar su cuenta.

### Roles disponibles

| Rol | Descripcion |
|---|---|
| `estudiante` | Acceso de lectura y uso de modulos educativos |
| `docente` | Gestion de contenido educativo |
| `administrador` | Gestion completa del sistema |

### Filtros disponibles

- **Por estado:** activo, pendiente.
- **Por rol:** estudiante, docente, administrador.
- **Por nombre o correo:** campo de busqueda de texto libre.

---

## 2. Gestion de imagenes histopatologicas

Requiere permiso `manage_images` (Docente o Admin).

### Subir una imagen

La carga de laminas se realiza siempre desde **Configuracion > Imagenes**. La pantalla **Imagenes IA** solo consume la biblioteca ya publicada.

1. Navegar a **Configuracion > Imagenes** desde la barra lateral.
2. Hacer clic en el boton de carga o subida de imagen.
3. Seleccionar el archivo WSI (formatos soportados: `.tiff`, `.svs`, `.ndpi`, segun configuracion del servidor).
4. Completar los metadatos: titulo, descripcion, tipo de patologia, descripcion de referencia.
5. Hacer clic en **Guardar**.

El campo **tipo de patologia** determina bajo que enfermedad aparece la lamina en el selector de **Imagenes IA** (por ejemplo `Necrosis coagulativa`, `Trombosis venosa`, `CAMELYON17`). Si el valor no coincide con ninguna categoria del catalogo, se crea una entrada propia con ese nombre.

El backend convierte automaticamente el archivo a tiles DZI para el visor OpenSeadragon.

Para laminas WSI grandes que ya estan copiadas en el servidor, usar **Configuracion > Imagenes > Importar CAMELYON17 local**. Esta ruta registra el archivo sin volver a transferirlo por el navegador y es mucho mas rapida que subirlo por el navegador.

### Elegir la enfermedad a analizar

En **Imagenes IA**, la barra lateral lista las enfermedades analizables (cancer de mama, necrosis, inflamacion, patologia infecciosa, trastornos vasculares, adaptaciones celulares y las patologias propias registradas). Al seleccionar una enfermedad se despliegan las laminas disponibles para esa categoria; el contador indica cuantas hay cargadas.

### Administrar imagenes existentes

El panel de gestion permite:
- Ver listado completo de imagenes (activas e inactivas).
- Editar metadatos.
- Desactivar una imagen (la imagen deja de estar disponible para estudiantes).
- Eliminar permanentemente (requiere permiso `delete_sensitive_resources`, solo Admin).

---

## 3. Gestion de casos clinicos

Requiere permiso `manage_cases` (Docente o Admin).

### Crear un caso clinico

1. Navegar a **Casos Clinicos** desde la barra lateral.
2. Hacer clic en **Nuevo caso** o en el boton equivalente (visible solo para docentes y admins).
3. Completar los campos del formulario:

| Campo | Descripcion | Obligatorio |
|---|---|---|
| Titulo | Nombre identificador del caso | Si |
| Descripcion | Resumen breve (2-3 lineas) | Si |
| Cuerpo | Desarrollo completo del caso | Si |
| Contexto clinico | Informacion adicional de contexto | No |
| Objetivos de aprendizaje | Competencias que el caso desarrolla | No |
| Dificultad | pregrado / internado / residente | No |
| Tema | Area medica (ej. neumologia, infectologia) | No |
| Imagen asociada | ID de imagen histopatologica relacionada | No |
| Test SCT asociado | ID de test SCT para este caso | No |
| Recursos externos | Enlaces a material complementario y actividades | No |

4. Seleccionar el estado inicial: **Borrador** o **Publicado**.
5. Hacer clic en **Guardar**.

### Recursos externos del caso

Un caso ofrece tres vias de retroalimentacion al estudiante, y el panel lateral
del caso las presenta juntas:

| Via | Recurso | Donde se configura |
|---|---|---|
| Logica | Test SCT de razonamiento clinico | Campo *Test SCT asociado* |
| Visual | Lamina histopatologica en el visor | Campo *Imagen asociada* |
| Interactiva | Actividad Wooclap | Recurso externo de tipo *Actividad interactiva* |

En **Recursos externos** se agrega cualquier enlace que el estudiante deba abrir
fuera de la plataforma. Cada recurso tiene tipo, titulo visible, URL y una
descripcion opcional:

| Tipo | Uso previsto |
|---|---|
| Actividad interactiva | Wooclap u otra actividad en vivo. Aparece junto al SCT y a la lamina |
| Material complementario | Libros y capitulos. El estudiante sigue el enlace y busca la obra |
| Guia clinica | Guias MINSAL, protocolos institucionales |
| Articulo | Publicaciones y revisiones |
| Video | Clases grabadas, procedimientos |
| Otro recurso | Cualquier otro enlace |

Los recursos se ordenan con las flechas ↑ ↓ y ese orden es el que ve el
estudiante. Un caso admite hasta 15.

**Restricciones de seguridad:** solo se aceptan direcciones `http://` y
`https://`. Cualquier otro esquema (`javascript:`, `data:`, `file:`) se rechaza
al guardar y, si existiera un enlace historico con uno de ellos, no se muestra
al estudiante. La plataforma no aloja ni copia el contenido remoto: solo guarda
el enlace, y este se abre en una pestana nueva sin dar acceso a la sesion.

### Estados de un caso

| Estado | Visible para estudiantes | Descripcion |
|---|---|---|
| `draft` (Borrador) | No | En preparacion, no publicado |
| `published` (Publicado) | Si | Disponible para todos los estudiantes |
| `archived` (Archivado) | No | Retirado de circulacion, conservado en BD |

### Cambiar el estado

Desde la vista de detalle del caso o desde la lista de casos (vista docente):
- **Publicar:** cambia de borrador a publicado.
- **Archivar:** retira el caso de la lista de estudiantes.
- **Republicar:** reactiva un caso archivado.

### Editar y eliminar

- **Editar:** hace clic en el boton de edicion del caso. Todos los campos son modificables.
- **Eliminar (soft-delete):** el caso se marca como inactivo pero no se borra de la base de datos. Solo Admin con permiso `delete_sensitive_resources`.

---

## 4. Gestion de documentos RAG

Requiere permiso `manage_rag` (Docente o Admin).

El sistema RAG (Retrieval-Augmented Generation) utiliza documentos para enriquecer las respuestas del chatbot con informacion validada.

### Agregar un documento

**Opcion A — Crear manualmente:**
1. Ir a **Configuracion** → seccion **Documentos RAG**.
2. Hacer clic en **Nuevo documento**.
3. Ingresar titulo, etiquetas y el texto del documento.
4. Hacer clic en **Guardar y reindexar**.

**Opcion B — Subir archivo (PDF o TXT):**
1. Ir a **Configuracion** → seccion **Documentos RAG**.
2. Hacer clic en **Subir archivo**.
3. Seleccionar el archivo del sistema.
4. El sistema extrae el texto, lo fragmenta y genera embeddings automaticamente.

### Reindexar documentos

Si se modifica el texto de un documento, es necesario reindexarlo para que los cambios se reflejen en las busquedas:

- **Reindexar un documento:** boton **Reindexar** junto al documento.
- **Reindexar corpus completo:** boton **Reindexar todo** en la parte superior del panel.

El reindexado puede tardar varios segundos segun el volumen de documentos.

### Probar la busqueda

El campo de busqueda semantica en el panel RAG permite probar que la recuperacion de contexto funciona correctamente antes de que los estudiantes realicen consultas.

---

## 5. Gestion de tests SCT

Requiere permiso `manage_sct` (Docente o Admin).

### Generar un test con IA

1. Navegar a **Test SCT** desde la barra lateral.
2. En el panel de configuracion, seleccionar:
   - **Area medica:** una o varias areas tematicas.
   - **Dificultad:** Pregrado, Internado o Residente.
   - **Numero de items:** 3, 5, 10 o 15.
   - **Enfoque especifico:** texto libre para precisar el tema (ej. "tuberculosis pulmonar resistente").
3. Hacer clic en **Generar test**.
4. El sistema llama al modelo LLaMA 3 y devuelve los items generados (puede tardar de 30 a 90 segundos).

### Revisar y editar items generados

Tras la generacion, revisar cada item:
- **Vigneta clinica:** situacion del paciente.
- **Hipotesis:** diagnostico o procedimiento evaluado.
- **Nueva informacion:** hallazgo que el estudiante debe interpretar.
- **Respuesta correcta:** valor de referencia (-2 a +2).
- **Explicacion:** justificacion educativa de la respuesta.

Editar cualquier item antes de guardar si es necesario.

### Guardar y publicar el test

1. Hacer clic en **Guardar test**.
2. Asignar un nombre identificador al test.
3. Seleccionar el estado: **Borrador** o **Publicado**.
4. Hacer clic en **Guardar**.

Un test en estado **Publicado** aparece automaticamente en la biblioteca de tests de todos los estudiantes.

### Estados de un test SCT

| Estado | Visible para estudiantes | Descripcion |
|---|---|---|
| `draft` | No | En preparacion |
| `published` | Si | Disponible para evaluacion |
| `archived` | No | Retirado de circulacion |

### Revisar intentos de estudiantes

1. En la pagina **Test SCT**, desplazarse a la seccion de intentos (panel docente).
2. Ver: nombre del estudiante, test resuelto, puntaje, fecha y numero de items correctos.
3. Los datos pueden exportarse si se implementa la funcion de exportacion.

---

## 6. Evaluacion de usabilidad

Requiere permiso `view_feedback` (Docente o Admin).

### Ver resumen de evaluaciones

1. Navegar a **Evaluacion** desde la barra lateral.
2. Seleccionar la pestana **Resumen general** (visible solo para docentes y admins).

El resumen incluye:
- **Promedio por dimension:** claridad de navegacion, facilidad del visor, facilidad de ROI, claridad de IA, utilidad del chatbot, utilidad del SCT.
- **Desglose por rol:** promedios separados para estudiantes y docentes (se oculta si hay menos de 3 respuestas por rol para proteger el anonimato).
- **Observaciones recientes:** ultimas observaciones textuales enviadas.
- **Tabla de respuestas:** vista individual por rol (sin identificacion personal).

### Exportar datos

Hacer clic en **Exportar CSV** para descargar un archivo con todas las respuestas anonimizadas en formato CSV.

---

## 7. Configuracion del sistema (solo Admin)

Requiere rol **Administrador**.

### Proveedor del modelo generativo

Desde **Configuracion** → **Configuracion de IA** → tarjeta **Proveedor del
modelo generativo** se elige donde se ejecuta el modelo:

| Proveedor | Cuando conviene |
|---|---|
| `ollama` | El modelo corre en este servidor. Sin costo por consulta, depende de la GPU local |
| `groq` | API externa. Sirve Llama 3.x con latencias muy inferiores a una GPU local |
| `openai_compatible` | Cualquier otro endpoint `/v1/chat/completions` (OpenRouter, Together, vLLM) |

**Configurar Groq:**

1. Crear una clave en `https://console.groq.com/keys` (empieza por `gsk_`).
2. En el panel, elegir proveedor **Groq**.
3. Dejar `LLM_API_BASE_URL` en `https://api.groq.com/openai/v1`.
4. Pegar la clave en `LLM_API_KEY`.
5. Elegir el modelo en `LLM_API_MODEL` (p. ej. `openai/gpt-oss-20b`).
6. **Guardar configuracion** y luego **Probar conexion**.

La prueba usa la configuracion ya guardada e informa latencia real, credencial
invalida o modelo inexistente por separado, para no descubrir el error en medio
de una consulta de un estudiante.

**Sobre la clave:** se guarda en base de datos y la API nunca la devuelve en
claro; el formulario solo muestra si esta puesta. Volver a guardar sin tocar el
campo conserva la clave existente; para borrarla hay que vaciar el campo
explicitamente.

**El RAG no cambia con el proveedor.** Los embeddings se siguen calculando en
este servidor con sentence-transformers y pgvector. Al proveedor externo solo
viaja el prompt de cada consulta, con los fragmentos documentales ya
seleccionados localmente: cambiar de proveedor no obliga a reindexar el corpus
ni sube los documentos a un tercero.

### Verificar estado de integracion

El panel de configuracion muestra el estado de conexion con:
- Proveedor LLM activo (local o externo) y modelo en uso.
- Modulo de embeddings RAG y backend vectorial.
- Envio de correo (SMTP).

---

## 8. Historial de actividad

El **Dashboard** muestra estadisticas globales de uso de la plataforma:

- Numero total de usuarios activos.
- Numero de consultas al chatbot.
- Tests SCT completados.
- Sesiones histopatologicas registradas.

El historial individual de cada usuario (intentos SCT, sesiones ROI, consultas) puede consultarse desde el panel de administracion si el estudiante tiene historial registrado.
