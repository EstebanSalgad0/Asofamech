# Informe preliminar sobre plataforma ASOFAMECH para educación médica asistida por inteligencia artificial

Fecha de preparación: 2026-05-31  
Documento: borrador orientado a docentes y profesionales de la Facultad de Medicina  
Base del informe: revisión técnica del repositorio, documentación, interfaz, API, modelos, pruebas y evidencias sanitizadas disponibles.

## 1. Título del informe

**ASOFAMECH: plataforma educativa médica con inteligencia artificial para razonamiento clínico, apoyo documental e interpretación formativa de imágenes histopatológicas**

## 2. Antecedentes y propósito de la plataforma

ASOFAMECH es una plataforma web desarrollada como prototipo educativo para apoyar procesos de formación médica. Su diseño integra herramientas de consulta, evaluación, gestión de casos clínicos y análisis formativo de imágenes histopatológicas.

La finalidad principal identificada no es asistencial, sino académica: facilitar el aprendizaje, la práctica de razonamiento clínico y la interacción con recursos docentes. El sistema incorpora advertencias explícitas de uso educativo y no debe presentarse como sustituto del criterio clínico, docente o anatomopatológico.

## 3. Descripción general de la solución

La plataforma cuenta con una aplicación web para estudiantes, docentes y administradores. Sus componentes principales son:

* un asistente conversacional médico educativo;
* un sistema de recuperación de documentos para apoyar respuestas del chatbot;
* un módulo SCT para evaluación de razonamiento clínico;
* una biblioteca de imágenes histopatológicas;
* un visor de láminas digitales con selección de regiones de interés;
* un modelo experimental de inteligencia artificial para clasificar regiones histopatológicas;
* gestión de casos clínicos, historial de uso, feedback y administración de usuarios.

La arquitectura técnica utiliza frontend web, backend API, base de datos, modelos de lenguaje local mediante Ollama/LLaMA 3 y un modelo de visión histopatológica basado en CONCH.

## 4. Aplicación en el ámbito médico

La aplicación médica real del sistema, según la evidencia revisada, es educativa. Puede apoyar:

* entrenamiento de estudiantes en razonamiento clínico mediante SCT;
* revisión de casos clínicos preparados por docentes;
* consulta educativa con respaldo documental cuando existen fuentes cargadas;
* aprendizaje visual de histopatología mediante selección de ROI y revisión de resultados del modelo;
* preparación docente de mapas o regiones de interés para discusión académica.

No se encontró evidencia suficiente para afirmar que la plataforma esté validada para decisiones asistenciales, tamizaje clínico, confirmación diagnóstica, planificación terapéutica o seguimiento de pacientes.

## 5. Patología, condición clínica o finalidad asistencial analizada

El componente de imágenes médicas se enfoca en histopatología digital de ganglio linfático teñido con hematoxilina-eosina. La tarea del modelo es clasificar regiones seleccionadas de una lámina como compatibles con:

* tejido no metastásico;
* tejido metastásico;
* estroma o tejido no evaluable/menos adecuado para la tarea.

El contexto técnico proviene de datasets y flujos compatibles con CAMELYON/PCam/SLN-Breast, relacionados con metástasis en ganglio linfático. Por tanto, el alcance defendible es: **apoyo educativo al análisis de regiones histopatológicas compatibles con metástasis en ganglio linfático H&E**.

No corresponde afirmar que el sistema determina si una persona tiene cáncer. Tampoco clasifica cánceres en general, órganos en general, subtipos tumorales, grados histológicos ni lesiones fuera de su dominio de entrenamiento.

## 6. Funcionamiento del modelo de inteligencia artificial

El modelo de imágenes utiliza CONCH como extractor de características visuales y una cabeza clasificadora entrenada para tres clases: `no_metastasico`, `metastasico` y `estroma`.

El flujo general es:

```text
Lámina histopatológica
-> selección de ROI amplia y ROI pequeña
-> extracción del patch
-> control de calidad de la región
-> procesamiento por CONCH
-> clasificación por cabeza entrenada
-> resultado educativo con probabilidades, confianza y advertencia
```

El resultado puede ser una clasificación, un resultado incierto o una abstención por ROI no evaluable. La plataforma también puede generar mapas educativos acotados a una ROI, dividiendo la región en tiles y mostrando zonas con mayor score de sospecha.

Las métricas disponibles son experimentales. Para el checkpoint configurado como Stage 16, el reporte de prueba registra accuracy 0.8144, macro F1 0.7378 y ROC-AUC tumor OVR 0.9489. Con umbral 0.90, el sistema reporta alta precisión/especificidad para tumor, pero sensibilidad baja en el barrido experimental. Esto refuerza que el modelo debe interpretarse como prototipo educativo y no como herramienta clínica autónoma.

## 7. Tipo de imágenes médicas procesadas

La modalidad procesada es histopatología digital, no radiología. El sistema admite archivos `.svs`, `.tif`, `.tiff`, `.jpg`, `.jpeg` y `.png`, y utiliza visualización tipo Deep Zoom para explorar láminas de gran tamaño.

La región anatómica documentada es ganglio linfático. El modelo está orientado a regiones histológicas compatibles con metástasis, no a imágenes CT, MRI, DICOM, mamografía, radiografía, ecografía o PET.

## 8. Descripción del módulo sCT/SCT

En este proyecto, SCT significa **Script Concordance Test**. Es una metodología de evaluación del razonamiento clínico que presenta una viñeta, una hipótesis y nueva información, solicitando al estudiante valorar cómo cambia la probabilidad de la hipótesis en una escala de -2 a +2.

El módulo permite generar ítems mediante IA, guardarlos, publicarlos, resolverlos y registrar intentos con puntaje. Está orientado a educación médica y puede adaptarse a distintos focos clínicos.

No existe evidencia de que el término SCT corresponda a tomografía computarizada sintética. No se encontró relación con MRI, CT, CBCT, radioterapia ni planificación de dosis.

## 9. Descripción del módulo de imaginería médica

El módulo de imágenes permite registrar y visualizar láminas histopatológicas. Los docentes o administradores pueden cargar imágenes o importar láminas locales CAMELYON17 ya disponibles en el servidor. Los usuarios autenticados pueden explorar imágenes con zoom y seleccionar regiones de interés.

Flujo funcional:

```text
Usuario autorizado carga o importa imagen histopatológica
-> plataforma valida formato y permisos
-> backend prepara visor Deep Zoom
-> usuario visualiza la lámina
-> usuario selecciona ROI 1 y ROI 2
-> backend valida coordenadas y calidad de ROI
-> modelo procesa la región
-> sistema entrega resultado educativo
-> resultado queda disponible en historial
```

Los resultados visibles incluyen clase estimada, confianza, probabilidades, métricas de calidad de ROI, recomendación educativa, trazabilidad mediante `trace_id` y advertencia de uso no asistencial.

## 10. Descripción del chatbot

El chatbot es un asistente médico educativo. Responde consultas del ámbito médico y de salud, usa un filtro de alcance para evitar temas no médicos y puede apoyarse en documentos cargados mediante RAG cuando existe contexto suficiente.

Sus respuestas incluyen advertencias de finalidad educativa. El sistema no debe utilizarse para indicaciones terapéuticas personalizadas ni como reemplazo de atención profesional. Su utilidad depende de la calidad de los documentos cargados, la curaduría docente y los límites del modelo de lenguaje.

## 11. Estado actual de desarrollo de la plataforma

La plataforma se encuentra en un estado funcional de prototipo avanzado. Dispone de backend, frontend, autenticación, roles, gestión de contenidos, chatbot, SCT, imágenes, análisis ROI y evidencias de pruebas automatizadas.

Sin embargo, desde el punto de vista médico, varios módulos deben considerarse en etapa de validación:

* el modelo histopatológico tiene métricas experimentales, no validación clínica formal;
* el chatbot requiere curaduría profesional de fuentes y evaluación de seguridad;
* los SCT generados por IA requieren revisión docente si se usarán para evaluación formal;
* los flujos de datos médicos requieren gobernanza institucional antes de uso con información clínica real.

## 12. Funcionalidades actualmente disponibles

Funcionalidades implementadas según evidencia revisada:

* registro, login y aprobación de usuarios;
* roles de estudiante, docente y administrador;
* carga y visualización de imágenes histopatológicas;
* visor con zoom y selección de ROI;
* análisis IA de ROI histopatológica;
* generación de heatmaps educativos acotados;
* historial de análisis ROI;
* correcciones docentes de sesiones;
* chatbot médico educativo con RAG;
* gestión de documentos RAG;
* generación, publicación y resolución de SCT;
* gestión de casos clínicos con recursos asociados;
* feedback de usabilidad;
* configuración administrativa de usuarios e integraciones;
* pruebas backend y build frontend documentados.

## 13. Funcionalidades pendientes o en proceso de validación

Pendientes principales:

* validación clínica formal del modelo histopatológico;
* revisión por patólogos o profesionales de salud;
* evaluación prospectiva y multicéntrica;
* clasificación robusta de lámina completa;
* cola durable o infraestructura más robusta para heatmaps extensos;
* protocolo institucional de privacidad, anonimización y retención de imágenes;
* revisión formal de seguridad;
* curaduría de fuentes RAG;
* validación docente de SCT generados por IA;
* documentación alineada con el checkpoint actual, ya que existen documentos históricos que mencionan checkpoints anteriores.

## 14. Limitaciones clínicas y consideraciones éticas

El principal riesgo es la sobreinterpretación del resultado. Una clasificación `metastasico` en una ROI no equivale a confirmar cáncer en un paciente. Una clasificación `no_metastasico` tampoco descarta enfermedad en la lámina completa, porque una región puntual puede no contener tejido tumoral.

El sistema depende de la calidad de la imagen, de la selección de ROI, del dominio del dataset y del umbral de decisión. Puede fallar ante artefactos, estroma, fibrosis, inflamación, baja celularidad, variaciones de tinción, scanners diferentes o tejidos fuera del dominio esperado.

Desde una perspectiva ética, cualquier uso con imágenes o datos de pacientes requiere políticas explícitas de anonimización, consentimiento o autorización institucional, seguridad de acceso, retención de datos y trazabilidad. La revisión del repositorio muestra mecanismos técnicos de roles y autenticación, pero no reemplaza una evaluación institucional de privacidad y cumplimiento regulatorio.

## 15. Próximos pasos recomendados

1. Alinear documentación técnica con la configuración actual del modelo Stage 16.
2. Definir formalmente el alcance clínico-académico: herramienta educativa de histopatología, no asistencial.
3. Preparar un protocolo de validación con patólogos, incluyendo criterios de inclusión, exclusión, datasets, splits por lámina/paciente y métricas.
4. Evaluar el modelo en láminas negativas, positivas, regiones mixtas, estroma, artefactos y centros distintos.
5. Separar claramente evaluación de patch, ROI, heatmap y lámina completa.
6. Curar el corpus RAG con fuentes aprobadas por docentes.
7. Establecer revisión docente obligatoria para SCT usados en evaluación formal.
8. Crear política de privacidad y manejo de imágenes clínicas.
9. Mantener advertencias visibles de finalidad educativa en interfaz e informes.
10. Documentar resultados con trazabilidad de versión de modelo, umbral y dataset.

## 16. Conclusión

ASOFAMECH es un prototipo educativo integrado y técnicamente avanzado para apoyar formación médica mediante inteligencia artificial. Su mayor valor actual está en combinar razonamiento clínico, consulta educativa, casos y análisis formativo de histopatología digital.

El modelo de imágenes analiza regiones de ganglio linfático H&E y entrega una clasificación experimental relacionada con metástasis, limitada a ROI/patch o tiles de una ROI. No debe presentarse como herramienta diagnóstica ni como sistema capaz de determinar si un paciente tiene cáncer.

Para su presentación ante la Facultad de Medicina, la formulación recomendada es: **plataforma educativa de apoyo al aprendizaje médico con un módulo experimental de análisis histopatológico de regiones compatibles con metástasis en ganglio linfático, sujeto a validación clínica y docente antes de cualquier uso formal en contexto asistencial o evaluativo institucional**.
