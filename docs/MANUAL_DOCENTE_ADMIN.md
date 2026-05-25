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

1. Navegar a **Imagenes IA** desde la barra lateral.
2. Hacer clic en el boton de carga o subida de imagen.
3. Seleccionar el archivo WSI (formatos soportados: `.tiff`, `.svs`, `.ndpi`, segun configuracion del servidor).
4. Completar los metadatos: titulo, descripcion, tipo de tejido, diagnostico de referencia.
5. Hacer clic en **Guardar**.

El backend convierte automaticamente el archivo a tiles DZI para el visor OpenSeadragon.

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

4. Seleccionar el estado inicial: **Borrador** o **Publicado**.
5. Hacer clic en **Guardar**.

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

### Configuracion del modelo IA

Desde **Configuracion** → seccion **Configuracion IA**:
- Ajustar parametros del modelo LLM (temperatura, contexto, instrucciones de sistema).
- Verificar el estado de la integracion con Ollama.

### Verificar estado de integracion

El panel de configuracion muestra el estado de conexion con:
- Ollama (modelo LLM activo).
- Modulo de embeddings RAG.

---

## 8. Historial de actividad

El **Dashboard** muestra estadisticas globales de uso de la plataforma:

- Numero total de usuarios activos.
- Numero de consultas al chatbot.
- Tests SCT completados.
- Sesiones histopatologicas registradas.

El historial individual de cada usuario (intentos SCT, sesiones ROI, consultas) puede consultarse desde el panel de administracion si el estudiante tiene historial registrado.
