# Manual de Usuario — Estudiante

ASOFAMECH es una plataforma educativa de medicina con inteligencia artificial. Este manual describe como utilizar cada modulo disponible para el rol de estudiante.

> **Aviso importante:** Todos los analisis, respuestas y evaluaciones de esta plataforma son exclusivamente educativos. No constituyen diagnostico medico ni reemplazan la opinion de un profesional de salud.

---

## Indice

1. [Acceder a la plataforma](#1-acceder-a-la-plataforma)
2. [Panel principal (Dashboard)](#2-panel-principal-dashboard)
3. [Asistente IA (Chatbot)](#3-asistente-ia-chatbot)
4. [Imagenes IA — Visor histopatologico](#4-imagenes-ia--visor-histopatologico)
5. [Test SCT — Razonamiento clinico](#5-test-sct--razonamiento-clinico)
6. [Casos clinicos](#6-casos-clinicos)
7. [Evaluacion de usabilidad](#7-evaluacion-de-usabilidad)
8. [Cerrar sesion](#8-cerrar-sesion)

---

## 1. Acceder a la plataforma

### Crear una cuenta

1. Ir a la direccion web de la plataforma (ejemplo: `http://localhost:3000`).
2. Hacer clic en **Regístrate aquí**.
3. Completar los campos: nombre completo, correo electronico y contraseña (minimo 8 caracteres, con letras y numeros).
4. Hacer clic en **Registrarse**.

La cuenta quedara en estado **pendiente** hasta que un administrador la apruebe. Se notificara por correo electronico una vez aprobada (si el sistema de correo esta configurado).

### Iniciar sesion

1. Ir a la pagina de inicio de la plataforma.
2. Hacer clic en **Ingresar** o ir directamente a `/auth`.
3. Ingresar correo electronico y contraseña.
4. Hacer clic en **Iniciar sesion**.

Tras el login exitoso, la plataforma redirige automaticamente al panel principal.

---

## 2. Panel principal (Dashboard)

El panel principal muestra un resumen de la actividad reciente y accesos directos a todos los modulos.

### Barra lateral de navegacion

La barra lateral (sidebar) permite navegar entre los modulos disponibles:

| Icono | Modulo | Descripcion |
|---|---|---|
| Inicio | Dashboard | Panel principal con estadisticas |
| Chat | Asistente IA | Chatbot educativo medico |
| Test | Test SCT | Evaluacion de razonamiento clinico |
| Imagen | Imagenes IA | Visor histopatologico |
| Documento | Casos Clinicos | Biblioteca de casos clinicos |
| Cara | Evaluacion | Formulario de usabilidad |

La barra lateral incluye una funcion de busqueda: escribir el nombre del modulo en el campo de busqueda para filtrarlo rapidamente.

### Racha de uso

La esquina inferior de la barra lateral muestra la racha de dias consecutivos de uso de la plataforma.

---

## 3. Asistente IA (Chatbot)

El Asistente IA responde preguntas educativas sobre medicina, enfermedades, sintomas, tratamientos y patologias. Las respuestas se apoyan en documentos validados por el equipo docente (sistema RAG).

### Realizar una consulta

1. Navegar a **Asistente IA** desde la barra lateral.
2. Escribir la pregunta en el campo de texto inferior (ejemplo: *"¿Cuales son los sintomas principales de la tuberculosis pulmonar?"*).
3. Presionar **Enter** o hacer clic en el boton de enviar (flecha).
4. Esperar la respuesta del asistente (puede tardar algunos segundos).

### Interpretar la respuesta

Las respuestas pueden incluir:
- **Texto educativo** con la informacion solicitada.
- **Fuentes citadas desde RAG:** fragmentos de documentos de referencia utilizados para construir la respuesta, con porcentaje de relevancia.
- **Aviso de alcance:** si la pregunta esta fuera del ambito medico, el asistente lo indicara y no respondera.

### Gestionar conversaciones

- **Nueva conversacion:** hacer clic en **+ Nueva conversacion** para iniciar un hilo separado.
- **Guardar conversacion:** hacer clic en el icono de estrella (☆) sobre la conversacion para guardarla.
- **Exportar a PDF:** hacer clic en **Exportar PDF** para guardar el historial de la conversacion.
- **Filtrar por tema:** las conversaciones se clasifican automaticamente por area medica (cardiologia, infectologia, etc.).

### Limitaciones

- El asistente solo responde preguntas de ambito medico y educativo.
- Las respuestas no reemplazan el juicio clinico profesional.
- El tiempo de respuesta depende de la disponibilidad del servidor de IA.

---

## 4. Imagenes IA — Visor histopatologico

Este modulo permite explorar imagenes de cortes histologicos en alta resolucion y solicitar analisis de regiones de interes (ROI) con inteligencia artificial.

### Explorar imagenes disponibles

1. Navegar a **Imagenes IA** desde la barra lateral.
2. La pagina muestra el listado de imagenes cargadas por el equipo docente.
3. Hacer clic en una imagen para abrirla en el visor.

### Navegar en el visor

- **Zoom:** usar la rueda del raton o los botones de zoom en pantalla.
- **Desplazamiento:** hacer clic y arrastrar para mover la imagen.
- **Panel de herramientas:** disponible a la derecha del visor para seleccionar modos.

### Seleccionar una region de interes (ROI)

1. En el visor, seleccionar la herramienta de dibujo (lapiz o rectangulo).
2. Dibujar la region de interes sobre el tejido que se desea analizar.
3. Hacer clic en **Analizar ROI** o el boton equivalente.
4. Esperar mientras el sistema procesa la region (puede tardar de 10 a 60 segundos segun el tamano).

### Interpretar el resultado formativo

El sistema devuelve una evaluacion formativa que incluye:
- **Clasificacion orientativa:** presencia o ausencia de patrones compatibles con metastasis.
- **Nivel de confianza:** porcentaje que indica la certeza del modelo.
- **Heatmap:** mapa de calor superpuesto sobre la imagen que resalta las zonas de mayor interes.
- **Retroalimentacion educativa:** descripcion de los criterios morfologicos relevantes.

La interpretacion es exclusivamente formativa. No constituye diagnostico patologico.

### Historial de sesiones

Las sesiones de analisis ROI quedan registradas y pueden consultarse en el **Dashboard** o en el historial de imagenes.

---

## 5. Test SCT — Razonamiento clinico

El Script Concordance Test (SCT) es una herramienta de evaluacion del razonamiento clinico bajo incertidumbre. Cada item presenta una situacion clinica y solicita evaluar como nueva informacion modifica la probabilidad de una hipotesis diagnostica.

### Seleccionar y abrir un test

1. Navegar a **Test SCT** desde la barra lateral.
2. En la seccion **Mis tests guardados** (Biblioteca), aparecen los tests publicados por los docentes.
3. Hacer clic en **Abrir** para iniciar el test.

### Responder los items

Cada item del test presenta:
- **Caso clinico:** descripcion del paciente y contexto.
- **Hipotesis:** diagnostico o procedimiento en consideracion.
- **Nueva informacion:** un nuevo hallazgo o resultado de examen.
- **Escala de respuesta:** cinco opciones de -2 a +2.

| Valor | Significado |
|---|---|
| -2 | Esta informacion descarta completamente la hipotesis |
| -1 | Hace la hipotesis menos probable |
| 0 | No modifica la probabilidad |
| +1 | Hace la hipotesis mas probable |
| +2 | Apoya fuertemente la hipotesis |

Seleccionar la opcion que mejor represente el razonamiento clinico para cada item.

### Enviar el test y ver resultados

1. Responder todos los items del test.
2. Hacer clic en **Enviar** o **Finalizar**.
3. El sistema muestra el puntaje obtenido y la comparacion con las respuestas de referencia.

### Historial de intentos

Los intentos completados quedan registrados. El progreso acumulado se visualiza en el panel principal (Dashboard) con graficos de evolucion por area tematica.

---

## 6. Casos clinicos

La seccion de Casos Clinicos ofrece una biblioteca de casos preparados por los docentes para estudio autonomo.

### Explorar casos

1. Navegar a **Casos Clinicos** desde la barra lateral.
2. Usar los filtros de busqueda: palabras clave, dificultad o tema.
3. Hacer clic en un caso para ver su detalle completo.

### Contenido de un caso

Cada caso puede incluir:
- Descripcion general y contexto clinico.
- Objetivos de aprendizaje.
- Cuerpo del caso (anamnesis, examen fisico, examenes).
- Imagen histopatologica asociada (si aplica).
- Test SCT asociado (si aplica).

Solo estan disponibles los casos con estado **publicado**.

---

## 7. Evaluacion de usabilidad

Al finalizar el uso de la plataforma, el estudiante puede completar el formulario de evaluacion de usabilidad.

1. Navegar a **Evaluacion** desde la barra lateral.
2. Calificar cada dimension en una escala del 1 al 5.
3. Agregar observaciones adicionales en el campo de texto (opcional).
4. Hacer clic en **Enviar evaluacion**.

El formulario puede editarse una vez enviado. Las respuestas son anonimas para el analisis estadistico por grupo de rol.

---

## 8. Cerrar sesion

Hacer clic en el icono de cierre de sesion ubicado en la esquina inferior de la barra lateral (icono de flecha saliente). La sesion se cierra y el navegador redirige a la pagina de inicio.

La sesion expira automaticamente despues de 12 horas de inactividad.
