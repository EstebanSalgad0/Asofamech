# Dossier técnico-clínico de evidencias

Fecha de revisión: 2026-05-31  
Proyecto: ASOFAMECH, plataforma educativa médica con inteligencia artificial  
Alcance de la revisión: inspección de repositorio, documentación, backend, frontend, configuraciones, endpoints, métricas y evidencias sanitizadas. No se ejecutaron entrenamientos ni se modificó código fuente.

## 1. Resumen ejecutivo de hallazgos

La plataforma ASOFAMECH corresponde a un prototipo educativo para formación médica. Integra autenticación por roles, gestión de casos clínicos, chatbot médico educativo con RAG, generación y resolución de SCT, visor de imágenes histopatológicas, análisis de ROI mediante IA, heatmaps educativos acotados a una ROI y registro de historial/feedback.

* Evidencia: `README.md`, descripción del proyecto como plataforma educativa médica con IA, módulos RAG, SCT, histopatología, casos clínicos y roles.
* Evidencia: `backend/app/main.py`, inclusión de routers `chat`, `cases`, `rag`, `history`, `admin`, `sct`, `auth`, `medical_images`, `histopathology` y `feedback`.
* Evidencia: `frontend/src/app.jsx`, rutas visibles `/dashboard/chat`, `/dashboard/sct`, `/dashboard/images`, `/dashboard/cases`, `/dashboard/feedback` y `/dashboard/config`.

La finalidad médica identificada es principalmente académica: apoyo al aprendizaje, razonamiento clínico, revisión de casos y entrenamiento visual en histopatología. No se encontró evidencia de que el sistema esté validado para uso asistencial formal ni de que pueda reemplazar criterio profesional.

* Evidencia: `README.md`, advertencia de uso educativo y no diagnóstico.
* Evidencia: `backend/app/routers/chat.py`, advertencia educativa: no constituye diagnóstico, indicación terapéutica ni reemplazo de criterio clínico.
* Evidencia: `backend/app/routers/histopathology.py`, advertencia: módulo educativo no diagnóstico, limitado a patches de ganglio linfático tipo CAMELYON/PCam.

El modelo de imágenes no es radiológico ni genera tomografía computarizada sintética. El módulo de imagen corresponde a histopatología digital, principalmente láminas H&E de ganglio linfático en contexto CAMELYON/PCam/SLN-Breast. La tarea real del modelo es clasificar una ROI/patch o tiles de una ROI como `metastasico`, `no_metastasico` o `estroma`, con posibilidad de abstención mediante `roi_no_evaluable` o resultado incierto. No determina si una persona tiene cáncer.

* Evidencia: `docs/HISTOPATHOLOGY_AI.md`, tarea educativa de clasificación metastásico vs no metastásico en patches de ganglio linfático.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API06_histopathology_status_sanitizado.json`, modelo listo con tarea `camelyon_patch_classification_with_stroma_abstention`, clases `no_metastasico`, `metastasico`, `estroma`.
* Evidencia: `backend/app/histopathology/ml/inference_service.py`, carga de CONCH congelado y cabeza clasificadora.

El término SCT en este repositorio significa `Script Concordance Test`, una herramienta de evaluación de razonamiento clínico. No hay evidencia de que signifique `synthetic CT`, tomografía sintética, radioterapia, MRI-to-CT, CBCT o generación imagen-a-imagen.

* Evidencia: `docs/SCT_MODULE.md`, título `Módulo SCT (Script Concordance Test)`.
* Evidencia: `backend/app/routers/sct.py`, prompt: generación de ítems de Script Concordance Test para evaluar razonamiento clínico.
* Evidencia: `frontend/src/pages/SCTPage.jsx`, interfaz de generación/resolución SCT con viñeta, hipótesis, nueva información y escala -2 a +2.

Existen evidencias técnicas de funcionamiento: pruebas backend aprobadas, build frontend exitoso, endpoints sanitizados, estado del modelo, respuestas de ROI, DZI y chat. Estas evidencias validan software y demostraciones técnicas, pero no equivalen a validación clínica prospectiva ni autorización regulatoria.

* Evidencia: `apendices_evidencias/B_ejecucion_terminal/B_ET04_pytest_resultado.txt`, 178 pruebas aprobadas.
* Evidencia: `apendices_evidencias/B_ejecucion_terminal/B_ET05_npm_build.txt`, build frontend Vite exitoso.
* Evidencia: `backend/artifacts/histopathology/reports/tri_head_stage16_sane_tuned_metrics.json`, métricas experimentales del checkpoint Stage 16.

## 2. Archivos y carpetas revisados

Se revisaron las siguientes áreas del repositorio:

| Área | Rutas principales revisadas | Observación |
|---|---|---|
| Documentación general | `README.md`, `docs/SCT_MODULE.md`, `docs/HISTOPATHOLOGY_AI.md`, `docs/HISTOPATHOLOGY_ROADMAP.md` | Describen alcance educativo, SCT e histopatología. |
| Backend | `backend/app/main.py`, `backend/app/models.py`, `backend/app/auth.py`, `backend/app/auth_security.py`, `backend/app/routers/*` | API FastAPI, RBAC, entidades, endpoints. |
| IA histopatología | `backend/app/histopathology/*`, `backend/histopathology_offline/*`, `backend/artifacts/histopathology/reports/*` | Inferencia, QC, heatmap, entrenamiento/evaluación offline. |
| Frontend | `frontend/src/app.jsx`, `frontend/src/api.js`, `frontend/src/pages/*`, `frontend/src/components/OpenSeadragonViewer.jsx`, `frontend/src/authClient.js`, `frontend/src/histopathologyAccess.js` | Flujos visibles de usuario. |
| Configuración | `docker-compose.yml`, `backend/requirements.txt`, `backend/requirements-histopathology.txt`, `frontend/package.json` | Servicios, dependencias y scripts. |
| Pruebas | `backend/tests/*`, `frontend/e2e/*`, `apendices_evidencias/B_ejecucion_terminal/*` | Pruebas unitarias/integración y E2E con mocks. |
| Evidencias API | `apendices_evidencias/C_api_swagger_endpoints/*` | Respuestas sanitizadas de endpoints. |

## 3. Descripción general de la plataforma

ASOFAMECH es una aplicación web con frontend React/Vite, backend FastAPI, base PostgreSQL con pgvector, servicio Ollama para LLaMA 3 y módulo de histopatología basado en CONCH/PyTorch. El sistema se organiza como plataforma educativa para estudiantes, docentes y administradores.

* Evidencia: `docker-compose.yml`, servicios `db`, `backend`, `frontend` y `ollama`; configuración `LLM_MODEL=llama3:8b` y checkpoint histopatológico.
* Evidencia: `frontend/package.json`, dependencias React, OpenSeadragon, Fabric, Playwright y Vite.
* Evidencia: `backend/requirements-histopathology.txt`, dependencias opcionales `torch`, `torchvision`, `scikit-learn`, `openslide-bin` y `CONCH`.

Módulos funcionales identificados:

* Autenticación y roles: estudiantes, docentes y administradores.
* Chatbot médico educativo con filtro de alcance y RAG.
* Gestión de documentos RAG.
* Gestión de casos clínicos con recursos asociados.
* SCT para razonamiento clínico.
* Biblioteca de imágenes histopatológicas.
* Visor OpenSeadragon con ROI 1/ROI 2.
* Análisis IA de ROI histopatológica.
* Heatmaps educativos sobre ROI acotada.
* Historial y feedback de usabilidad.
* Administración de usuarios, configuración IA e integraciones.

## 4. Propósito médico identificado

La plataforma está orientada a formación médica, simulación académica y apoyo educativo. No se encontró evidencia suficiente para presentarla como sistema asistencial validado, sistema de diagnóstico, planificación terapéutica o seguimiento clínico de pacientes.

Usuarios objetivo según implementación:

| Usuario | Rol funcional | Evidencia |
|---|---|---|
| Estudiante | Usar plataforma, chat, histopatología, resolver SCT, ver historial propio | `backend/app/auth.py`, permisos por rol; `frontend/src/pages/SCTPage.jsx`; `frontend/src/pages/ImagesPage.jsx` |
| Docente | Gestionar casos, SCT, RAG, imágenes, revisar sesiones/correcciones | `backend/app/auth.py`; `frontend/src/pages/ConfigPage.jsx`; `backend/app/routers/histopathology.py` |
| Administrador | Gestionar usuarios, configuración IA, integraciones y datos sensibles | `backend/app/auth.py`; `backend/app/routers/admin.py`; `frontend/src/pages/ConfigPage.jsx` |

Beneficio académico esperado:

* Facilitar práctica de razonamiento clínico mediante SCT.
* Permitir consultas educativas con respaldo documental cuando existe RAG.
* Entrenar la selección de ROI y lectura orientativa de imágenes histopatológicas.
* Registrar desempeño, sesiones e interacción para seguimiento docente.

* Evidencia: `backend/app/routers/sct.py`, generación/guardado/resolución de SCT.
* Evidencia: `backend/app/routers/history.py`, historial personal y revisión docente/admin.
* Evidencia: `backend/app/routers/feedback.py`, evaluación de usabilidad de módulos.

## 5. Patología o condición clínica analizada

La patología/condición definida por el modelo de imágenes es metástasis en tejido de ganglio linfático H&E, en un contexto compatible con datasets CAMELYON/PCam/SLN-Breast. El repositorio menciona cáncer de mama como contexto de algunas fuentes de datos, pero el modelo no clasifica cáncer de mama primario ni diagnostica pacientes; clasifica regiones de tejido ganglionar.

* Evidencia: `docs/HISTOPATHOLOGY_ROADMAP.md`, alcance recomendado: detección educativa de regiones compatibles con metástasis en ganglio linfático H&E.
* Evidencia: `docs/HISTOPATHOLOGY_AI.md`, PCam/CAMELYON/SLN-Breast como fuentes; tarea de patch metastásico/no metastásico.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API06_histopathology_status_sanitizado.json`, labels `no_metastasico`, `metastasico`, `estroma`.

Qué realiza realmente:

| Pregunta clínica | Respuesta según evidencia |
|---|---|
| ¿Analiza cáncer? | Analiza regiones histopatológicas compatibles con metástasis en ganglio linfático; no determina cáncer en una persona. |
| ¿Detecta tumores? | Puede asignar alta probabilidad a la clase `metastasico` en una ROI/patch o tile; no realiza detección tumoral clínica completa. |
| ¿Segmenta tumor? | No se encontró un modelo de segmentación. El heatmap colorea tiles por score, pero no entrega una máscara tumoral validada. |
| ¿Genera imágenes sintéticas? | No. No hay evidencia de generación de CT sintético ni de imagen médica sintética. |
| ¿Entrega probabilidades? | Sí, para clases del clasificador y scores por tile/heatmap. |
| ¿Entrega recomendaciones? | Sí, recomendaciones educativas y de calidad de ROI; no indicaciones clínicas. |

* Evidencia: `backend/app/histopathology/heatmap_decision.py`, estados educativos de ROI como `metastasis_probable`, `sano_probable`, `sospecha_focal`, `mixto_incierto`, `roi_no_evaluable`.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API13_roi_analisis_respuesta.json`, respuesta con `status`, `class`, `confidence`, probabilidades, `reason`, `recommendation`, `roi_quality` y advertencia.

## 6. Modalidad de imagen y región anatómica

Modalidad encontrada: histopatología digital, láminas H&E de ganglio linfático. No se encontró evidencia de DICOM, CT/TAC, MRI/RM, radiografía, mamografía, ecografía, PET o radioterapia en el módulo IA de imágenes.

| Elemento | Estado según evidencia |
|---|---|
| Modalidad | Histopatología digital, WSI/raster H&E. |
| Región anatómica | Ganglio linfático, con contexto CAMELYON/PCam/SLN-Breast. |
| Formatos aceptados | `.svs`, `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`. |
| Visualización | DZI/OpenSeadragon para WSI y raster preparado. |
| Preprocesamiento | Extracción ROI2 en coordenadas nivel 0, QC, RGB, preprocess CONCH típicamente 224x224. |
| Resultado | Clase, probabilidades, confianza, QC, trazabilidad, advertencia educativa; heatmap por tiles en ROI. |

* Evidencia: `backend/app/routers/medical_images.py`, extensiones soportadas, límite de carga 500 MB, DZI dinámico y tiles.
* Evidencia: `backend/app/histopathology/patch_extractor.py`, extracción de ROI desde OpenSlide o PIL.
* Evidencia: `backend/app/histopathology/roi_quality.py`, métricas `white_fraction`, `tissue_fraction`, `nuclear_fraction`, `stroma_fraction`.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API12_dzi_viewer_respuesta.xml.json`, DZI de imagen con dimensiones `94968 x 210579`.

Limitaciones de modalidad:

* El soporte de carga de imágenes no significa que el modelo sea válido para cualquier imagen médica.
* El modelo está acotado a patches histopatológicos de ganglio linfático compatibles con CAMELYON/PCam.
* Las láminas completas requieren muestreo/ROI/tiles; el repositorio aún describe la clasificación de lámina completa como pendiente/metodológica.

## 7. Análisis del modelo de inteligencia artificial

### Modelo de histopatología

| Aspecto | Evidencia encontrada |
|---|---|
| Arquitectura | CONCH como extractor congelado de embeddings más cabeza clasificadora 3-clases MLP/linear. |
| Framework | PyTorch, torchvision, scikit-learn, CONCH, OpenSlide/Pillow. |
| Archivo de carga | `backend/app/histopathology/ml/inference_service.py`. |
| Entrada | Patch RGB extraído desde ROI2 o tile. |
| Salida | Clase, confianza, probabilidades, mapping de clases y metadata de modelo. |
| Clases | `no_metastasico`, `metastasico`, `estroma`. |
| Checkpoint actual por configuración | `tri_head_camelyon17_stage16_sane_tuned_v1.pt`. |
| Estado | Implementado sin validación clínica formal. |

* Evidencia: `docker-compose.yml`, `HISTO_CLASSIFIER_CHECKPOINT=/app/artifacts/histopathology/checkpoints/tri_head_camelyon17_stage16_sane_tuned_v1.pt`.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API06_histopathology_status_sanitizado.json`, `model_ready=true`, `model_version=tri_head_camelyon17_stage16_sane_tuned_v1`, `device=cuda`, `feature_dim=512`, `confidence_threshold=0.9`.
* Evidencia: `backend/app/histopathology/ml/classifier_head.py`, cabezas `TriClassifierHead` y `TriMLPClassifierHead`.
* Evidencia: `backend/app/histopathology/ml/conch_feature_extractor.py`, uso del encoder visual CONCH congelado.

### Métricas experimentales disponibles

El checkpoint Stage 16 tiene métricas experimentales en test:

| Métrica | Valor |
|---|---:|
| Accuracy | 0.8144 |
| Macro F1 | 0.7378 |
| ROC-AUC tumor OVR | 0.9489 |
| Precisión `metastasico` | 0.9146 |
| Recall `metastasico` | 0.7459 |
| F1 `metastasico` | 0.8217 |
| Precisión tumor a umbral 0.90 | 1.0000 |
| Sensibilidad tumor a umbral 0.90 | 0.3607 |
| Especificidad tumor a umbral 0.90 | 1.0000 |
| TP/FP/FN/TN a umbral 0.90 | 88 / 0 / 156 / 478 |
| Tamaño test | 722 muestras |

* Evidencia: `backend/artifacts/histopathology/reports/tri_head_stage16_sane_tuned_metrics.json`, sección `test`.

Interpretación clínica prudente: los resultados sugieren desempeño experimental sobre datos derivados de CAMELYON17/manifiestos locales, pero no demuestran validación clínica prospectiva, multicéntrica ni desempeño en flujo real de patología diagnóstica.

### Contradicciones o desalineaciones detectadas

1. Documentación histórica indica como checkpoint activo Stage 10, mientras configuración y evidencia de runtime indican Stage 16.

* Evidencia: `docs/HISTOPATHOLOGY_AI.md`, sección de conexión backend menciona Stage 10 como ruta esperada.
* Evidencia: `docs/HISTOPATHOLOGY_ROADMAP.md`, múltiples decisiones históricas sobre Stage 8 a Stage 14.
* Evidencia: `docker-compose.yml`, checkpoint Stage 16 configurado.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API06_histopathology_status_sanitizado.json`, modelo Stage 16 listo.

2. Documentación SCT inicial se enfoca en tuberculosis/neumología, pero el código actual permite foco médico variable.

* Evidencia: `docs/SCT_MODULE.md`, ejemplos y objetivo educativo sobre tuberculosis.
* Evidencia: `backend/app/routers/sct.py`, prompt parametrizado por `{focus}`.
* Evidencia: `frontend/src/pages/SCTPage.jsx`, selección de áreas y enfoque médico configurable.

3. Límites de heatmap aparecen como valores documentales/configurables distintos entre documentos y frontend/configuración actual.

* Evidencia: `docs/HISTOPATHOLOGY_AI.md` y `docs/HISTOPATHOLOGY_ROADMAP.md`, describen límites 16/256 en algunos apartados históricos.
* Evidencia: `docker-compose.yml`, valores por defecto `HISTO_STUDENT_MAX_HEATMAP_TILES=128` y `HISTO_PRIVILEGED_MAX_HEATMAP_TILES=128`.
* Evidencia: `frontend/src/histopathologyAccess.js`, constantes de cliente `STUDENT_HEATMAP_MAX_TILES=128` y `PRIVILEGED_HEATMAP_MAX_TILES=128`.

## 8. Análisis del módulo sCT/SCT

Significado confirmado: SCT significa `Script Concordance Test`. Es una evaluación de razonamiento clínico donde el estudiante ajusta una hipótesis ante nueva información usando una escala -2 a +2.

* Evidencia: `docs/SCT_MODULE.md`, definición de SCT como herramienta de evaluación de razonamiento clínico.
* Evidencia: `backend/app/routers/sct.py`, prompt para generar ítems de Script Concordance Test.

Entradas:

* Número de ítems.
* Dificultad: pregrado, internado o residente.
* Foco médico.
* Respuestas del estudiante en escala -2 a +2.

Salidas:

* Ítems SCT: viñeta clínica, hipótesis, nueva información, escala, respuesta correcta y explicación.
* Intentos guardados con puntaje, respuestas correctas y total.

* Evidencia: `backend/app/routers/sct.py`, endpoint `/api/sct/generate`, `/api/sct/save`, `/api/sct/{test_id}/attempt`.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API08_sct_attempt_respuesta.json`, intento SCT con `score=1.0`, `correct_count=3`, `total_items=3`.

No hay evidencia de:

* generación de CT sintético;
* uso de MRI/RM, CT/TAC, CBCT o radioterapia;
* planificación de dosis;
* comparación anatómica imagen-a-imagen.

Estado actual: implementado como módulo educativo de razonamiento clínico, con necesidad de validación docente/experta de los ítems si se usará formalmente en evaluación académica.

## 9. Análisis del módulo de imaginería médica

Flujo real ajustado a la evidencia:

```text
Docente/admin registra o sube imagen histopatológica
-> backend valida permisos, extensión y tamaño
-> backend guarda registro MedicalImage
-> backend prepara DZI para OpenSeadragon o DZI dinámico para WSI
-> usuario autenticado visualiza lámina
-> usuario delimita ROI 1 y ROI 2
-> backend valida geometría y límites de ROI
-> backend extrae patch ROI 2
-> backend ejecuta control de calidad de ROI
-> si la ROI es evaluable: CONCH + cabeza 3-clases
-> sistema genera clase/probabilidades/recomendación/advertencia
-> resultado se guarda como HistopathologySession
-> usuario visualiza resultado, historial y eventualmente heatmap/corrección docente
```

* Evidencia: `backend/app/routers/medical_images.py`, upload, importación local CAMELYON17, DZI y tiles.
* Evidencia: `frontend/src/pages/ImagesPage.jsx`, pantalla de histopatología con lista de imágenes, upload para roles docentes/admin e historial ROI.
* Evidencia: `frontend/src/components/OpenSeadragonViewer.jsx`, selección ROI1/ROI2, análisis ROI, heatmap y correcciones docentes.
* Evidencia: `backend/app/routers/histopathology.py`, endpoints `/status`, `/analyze-roi`, `/scan-roi`, `/heatmaps/*`, `/sessions/*`, `/correction`.

Validaciones aplicadas:

* Permisos de carga limitados a docentes/admin.
* Límite de carga HTTP de 500 MB.
* DZI dinámico para WSI grandes.
* Validación de ROI dentro de lámina y ROI2 dentro de ROI1.
* Control QC previo para fondo, tejido útil, celularidad y estroma.
* Umbral de confianza antes de emitir clasificación.

* Evidencia: `backend/app/routers/medical_images.py`, `MAX_IMAGE_UPLOAD_BYTES`.
* Evidencia: `backend/tests/test_histopathology_roi.py`, validación de ROI2 dentro de ROI1 y de límites de lámina.
* Evidencia: `backend/app/histopathology/roi_quality.py`, compuerta QC.

Estado real: módulo implementado y demostrable para análisis educativo de ROI/patch y heatmap acotado a ROI. No validado como diagnóstico de lámina completa.

## 10. Análisis del chatbot

Finalidad: asistente médico educativo de alcance general, con RAG cuando hay contexto documental suficiente. El chatbot no responde de forma nativa sobre una imagen procesada como si integrara el resultado visual automáticamente; puede conversar sobre temas médicos y usar documentos/casos recuperados.

* Evidencia: `backend/app/routers/chat.py`, system prompt de asistente médico educativo general, restricción de alcance, RAG y logging.
* Evidencia: `frontend/src/pages/ChatbotPage.jsx`, interfaz `MediChat`, hilos por tema, fuentes RAG citadas y exportación PDF del hilo.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API10_chatbot_respuesta_sanitizada.json`, respuesta educativa general con `used_rag=false` y advertencia.

Capacidades:

* Filtra consultas no médicas o ambiguas.
* Usa Ollama/LLaMA 3.
* Recupera documentos RAG si el tema lo justifica.
* Devuelve fuentes RAG cuando existen.
* Registra conversaciones en `ChatLog`.
* Incluye advertencias de finalidad educativa.

Riesgos:

* Puede generar respuestas plausibles no verificadas si no hay RAG suficiente.
* Necesita curaduría de fuentes y supervisión docente/profesional.
* No debe entregar indicaciones terapéuticas personalizadas ni reemplazar atención médica.

Estado actual: implementado sin validación clínica formal.

## 11. Arquitectura e integración de componentes

| Componente | Función médica o funcional | Tecnología encontrada | Evidencia en archivos | Estado actual | Observaciones |
|---|---|---|---|---|---|
| Frontend web | Interfaz para estudiantes/docentes/admin | React, Vite, OpenSeadragon, Fabric | `frontend/src/app.jsx`, `frontend/package.json` | Implementado | Rutas principales activas. |
| Backend API | Orquestación de módulos, seguridad, persistencia | FastAPI, SQLAlchemy, Pydantic | `backend/app/main.py`, `backend/app/routers/*` | Implementado | API modular. |
| Base de datos | Usuarios, imágenes, casos, SCT, chat, ROI, heatmaps | PostgreSQL, pgvector | `docker-compose.yml`, `backend/app/models.py` | Implementado | pgvector para RAG. |
| Autenticación | Control de acceso por rol | JWT HMAC, PBKDF2-SHA256 | `backend/app/auth.py`, `backend/app/auth_security.py` | Implementado | Secret requerido fuera de desarrollo. |
| Chatbot | Tutor médico educativo | Ollama/LLaMA 3 + RAG | `backend/app/routers/chat.py` | Implementado sin validación clínica | No asistencial. |
| RAG | Base documental para respuestas | Chunks, embeddings, pgvector/fallback | `backend/app/routers/rag.py`, `backend/app/embedding_service.py` | Implementado | Requiere fuentes curadas. |
| SCT | Evaluación de razonamiento clínico | LLaMA 3 + FastAPI + React | `backend/app/routers/sct.py`, `frontend/src/pages/SCTPage.jsx` | Implementado sin validación académica formal | Ítems deben ser revisados por expertos. |
| Imágenes médicas | Biblioteca histopatológica y visor | OpenSlide, DZI, OpenSeadragon | `backend/app/routers/medical_images.py`, `frontend/src/pages/ImagesPage.jsx` | Implementado | Soporta WSI y raster. |
| IA histopatología | Clasificación ROI/patch | CONCH, PyTorch, cabeza MLP 3-clases | `backend/app/histopathology/ml/*` | Implementado sin validación clínica | Experimental. |
| Heatmap ROI | Mapa educativo de sospecha por tiles | FastAPI jobs, JSON store, overlay UI | `backend/app/histopathology/heatmap_*`, `OpenSeadragonViewer.jsx` | Parcialmente implementado | Acotado a ROI; lámina completa pendiente. |
| Feedback | Evaluación de usabilidad | FastAPI + React | `backend/app/routers/feedback.py`, `frontend/src/pages/FeedbackPage.jsx` | Implementado | No es validación clínica. |
| Administración | Usuarios, IA, RAG, SCT, imágenes, correo | FastAPI + React | `backend/app/routers/admin.py`, `frontend/src/pages/ConfigPage.jsx` | Implementado | No divulgar secretos. |

## 12. Matriz de estado actual de funcionalidades

| Módulo o funcionalidad | Qué debería hacer | Qué hace actualmente según evidencia | Estado | Evidencia | Pendientes |
|---|---|---|---|---|---|
| Autenticación | Registrar, iniciar sesión y controlar acceso | Registro, login, aprobación, JWT, roles | Implementado | `backend/app/routers/auth.py`, `backend/app/auth.py` | Endurecer configuración productiva y auditoría. |
| Roles de usuario | Separar estudiante, docente y admin | Permisos por rol en backend y UI | Implementado | `backend/app/auth.py`, `frontend/src/authClient.js` | Revisar políticas institucionales. |
| Carga de imágenes | Subir/registrar imágenes médicas | Upload de formatos soportados e import local CAMELYON17 | Implementado | `backend/app/routers/medical_images.py` | Gobernanza de datos y retención. |
| Visualización de imágenes | Ver WSI/raster con zoom | DZI/OpenSeadragon y tiles dinámicos | Implementado | `frontend/src/components/OpenSeadragonViewer.jsx`, `C_API12` | Pruebas de performance con más usuarios. |
| Procesamiento IA ROI | Clasificar ROI/patch | QC + CONCH + cabeza 3-clases + trazabilidad | Implementado sin validación clínica | `backend/app/routers/histopathology.py`, `C_API13`, `C_API06` | Validación clínica y de dominio. |
| Heatmap ROI | Explorar zona amplia por tiles | Scan/heatmap acotado a ROI, jobs, historial | Parcialmente implementado | `backend/app/histopathology/heatmap_*`, `docs/HISTOPATHOLOGY_AI.md` | Cola durable, lámina completa, evaluación sistemática. |
| Clasificación de lámina completa | Resultado por WSI completa | No encontrada como funcionalidad cerrada; roadmap MIL/CLAM | Pendiente | `docs/HISTOPATHOLOGY_ROADMAP.md` | MIL/CLAM, validación por lámina, splits por slide. |
| SCT | Generar/resolver tests de razonamiento clínico | Genera, guarda, publica y registra intentos | Implementado sin validación clínica | `backend/app/routers/sct.py`, `SCTPage.jsx`, `C_API08` | Revisión docente/profesional de ítems. |
| Chatbot | Orientación educativa médica | LLaMA 3, filtro de alcance, RAG, advertencias | Implementado sin validación clínica | `backend/app/routers/chat.py`, `ChatbotPage.jsx`, `C_API10` | Curaduría de fuentes y evaluación profesional. |
| Casos clínicos | Gestionar casos y recursos asociados | CRUD, publicación, vinculación imagen/SCT | Implementado | `backend/app/routers/cases.py`, `frontend/src/pages/CasesPage.jsx`, `backend/tests/test_cases_api.py` | Curaduría académica de contenido. |
| Almacenamiento de resultados | Guardar intentos, chats, ROI y heatmaps | Entidades y endpoints de historial | Implementado | `backend/app/models.py`, `backend/app/routers/history.py` | Políticas de privacidad/retención. |
| Reportes | Exportar o revisar resultados | Chat PDF frontend, feedback CSV, historial | Parcialmente implementado | `ChatbotPage.jsx`, `backend/app/routers/feedback.py` | Informe clínico formal no encontrado. |
| Seguridad y privacidad | Proteger datos e imágenes | JWT, roles, secretos env, sanitización de evidencias | Implementado | `auth_security.py`, `apendices_evidencias/*_sanitizado*` | Evaluación formal de seguridad/privacidad. |
| Pruebas | Verificar software | Pytest, Playwright E2E, build | Implementado | `B_ET04`, `B_ET05`, `frontend/e2e/README.md` | Ejecutar E2E real con backend/GPU en entorno controlado. |
| Despliegue | Ejecutar servicios integrados | Docker Compose backend/frontend/db/ollama | Implementado | `docker-compose.yml` | Perfil productivo y monitoreo. |

## 13. Evidencias técnicas encontradas

### Pruebas y build

* Evidencia: `apendices_evidencias/B_ejecucion_terminal/B_ET04_pytest_resultado.txt`, `178 passed, 10 warnings in 5.04s`.
* Evidencia: `apendices_evidencias/B_ejecucion_terminal/B_ET05_npm_build.txt`, `vite build` completado con assets generados.
* Evidencia: `frontend/e2e/README.md`, suite Playwright con mocks para usuarios, DZI, heatmap, ROI, SCT, RAG y feedback; modo opt-in contra backend real.

### Endpoints sanitizados

* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API06_histopathology_status_sanitizado.json`, estado modelo Stage 16 listo.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API13_roi_analisis_respuesta.json`, respuesta ROI con `roi_no_evaluable`, QC y advertencia.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API12_dzi_viewer_respuesta.xml.json`, DZI con dimensiones de lámina.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API10_chatbot_respuesta_sanitizada.json`, respuesta chatbot con advertencia y sin RAG.
* Evidencia: `apendices_evidencias/C_api_swagger_endpoints/C_API08_sct_attempt_respuesta.json`, intento SCT registrado.

### Pruebas representativas

* Evidencia: `backend/tests/test_histopathology_roi.py`, valida geometría ROI1/ROI2 y límites de lámina.
* Evidencia: `backend/tests/test_cases_api.py`, rechaza casos vinculados a imagen/SCT inexistentes y acepta recursos existentes.
* Evidencia: `backend/tests/test_chat_rag_integration.py`, prueba integración chat/RAG.
* Evidencia: `backend/tests/test_auth_security.py`, cubre aspectos de seguridad/autenticación.
* Evidencia: `backend/tests/test_heatmap_access.py`, `test_heatmap_jobs.py`, `test_heatmap_decision.py`, pruebas sobre heatmap/acceso/decisiones.

## 14. Validaciones y métricas disponibles

### Validación de software

Existe validación automatizada de software backend y build frontend. Esto indica consistencia técnica del código bajo las pruebas disponibles, pero no mide desempeño clínico.

* Evidencia: `B_ET04_pytest_resultado.txt`, 178 pruebas aprobadas.
* Evidencia: `B_ET05_npm_build.txt`, build Vite exitoso.

### Evaluación experimental del modelo

El repositorio incluye reportes experimentales de múltiples etapas de entrenamiento, minería de negativos difíciles y comparaciones contra XML CAMELYON17. El reporte actual más directamente alineado con runtime es Stage 16.

* Evidencia: `backend/artifacts/histopathology/reports/tri_head_stage16_sane_tuned_metrics.json`, checkpoint Stage 16 y métricas de test.
* Evidencia: `backend/artifacts/histopathology/reports/tri_head_stage15_heavy_neg_metrics.json`, etapa previa con métricas comparativas.
* Evidencia: `docs/HISTOPATHOLOGY_AI.md` y `docs/HISTOPATHOLOGY_ROADMAP.md`, resultados históricos Stage 8 a Stage 14.

Nivel de validación identificado:

| Tipo | Estado |
|---|---|
| Prueba técnica de API/UI | Sí, con evidencias sanitizadas. |
| Validación de software automatizada | Sí, pytest/build y suite E2E disponible. |
| Evaluación experimental del modelo | Sí, reportes JSON y métricas offline. |
| Validación clínica prospectiva | No encontrada. |
| Validación por patólogos/profesionales de salud | No encontrada como evidencia formal. |
| Cumplimiento regulatorio | No encontrado. |

## 15. Riesgos y limitaciones clínicas

1. Riesgo de sobreinterpretación: una probabilidad `metastasico` en ROI/patch no equivale a diagnóstico de paciente ni de lámina completa.

* Evidencia: `backend/app/routers/histopathology.py`, advertencia educativa fija.
* Evidencia: `docs/HISTOPATHOLOGY_AI.md`, limitaciones metodológicas del patch vs lámina completa.

2. Ausencia de validación clínica formal: no se encontraron estudios prospectivos, comparación sistemática con patólogos ni aprobación regulatoria.

* Evidencia: no se encontraron documentos de validación clínica formal en las rutas revisadas; los reportes disponibles son métricas experimentales/offline.

3. Sesgo de dataset y dominio: el modelo se apoya en CAMELYON/PCam/SLN-Breast; puede fallar ante tinciones, artefactos, centros, scanners o tejidos distintos.

* Evidencia: `docs/HISTOPATHOLOGY_ROADMAP.md`, riesgos por artefactos, stroma, fibrosis, inflamación y necesidad de más láminas/centros.

4. Dependencia de selección de ROI: el usuario decide la ROI; una ROI sana dentro de una lámina positiva puede clasificarse como no metastásica sin contradecir el estado de la lámina.

* Evidencia: `docs/HISTOPATHOLOGY_AI.md`, diferencia entre etiqueta de lámina y etiqueta de patch.

5. Falsos negativos bajo umbral conservador: Stage 16 a umbral 0.90 muestra alta precisión/especificidad, pero baja sensibilidad en sweep de tumor.

* Evidencia: `tri_head_stage16_sane_tuned_metrics.json`, umbral 0.90 con sensibilidad 0.3607 y FN 156.

6. Privacidad y seguridad: el sistema maneja imágenes médicas, usuarios e historial. Se observaron roles y sanitización de evidencias, pero falta evaluación formal de privacidad/seguridad clínica.

* Evidencia: `backend/app/models.py`, entidades `MedicalImage`, `ChatLog`, `SCTAttempt`, `HistopathologySession`.
* Evidencia: `apendices_evidencias/*_sanitizado*`, evidencias con rutas/secretos ocultos.

7. Dependencia operacional de GPU/Ollama/CONCH/OpenSlide: fallas de GPU, modelo, token Hugging Face, OpenSlide o Ollama impactan disponibilidad.

* Evidencia: `docker-compose.yml`, backend con GPU, Ollama y checkpoint CONCH.
* Evidencia: `docs/HISTOPATHOLOGY_AI.md`, requisitos de CONCH y OpenSlide.

## 16. Información faltante o no comprobable

* No se encontró protocolo clínico institucional de validación.
* No se encontró revisión formal por patólogos, oncólogos o comité docente.
* No se encontró documentación de consentimiento, anonimización o gobernanza de imágenes clínicas reales.
* No se encontró aprobación ética/regulatoria.
* No se encontró evaluación prospectiva ni multicéntrica.
* No se encontró integración DICOM ni interoperabilidad clínica HL7/FHIR.
* No se encontró evidencia de uso en decisiones asistenciales.
* No se encontró modelo de segmentación validado ni clasificación de lámina completa cerrada.
* No se encontró sCT como tomografía sintética.

## 17. Conclusiones del análisis

1. ASOFAMECH es una plataforma educativa médica integrada, no una herramienta clínica validada.
2. El módulo SCT está implementado como `Script Concordance Test` para razonamiento clínico; no corresponde a CT sintético.
3. El módulo de imágenes procesa histopatología digital, no radiología.
4. El modelo IA actual clasifica ROI/patch/tile de ganglio linfático H&E en clases `metastasico`, `no_metastasico` y `estroma`, con abstención por calidad/incertidumbre.
5. El sistema puede describirse prudentemente como herramienta educativa de apoyo al análisis de regiones histopatológicas compatibles con metástasis, no como detector clínico general de cáncer.
6. Hay evidencia técnica considerable de implementación, pruebas y métricas experimentales.
7. Antes de presentarlo como apoyo médico formal se requiere validación clínica, curaduría profesional, gobierno de datos, seguridad, regulación y evaluación robusta por lámina/paciente.

## 18. Anexo de evidencias con rutas exactas

| Ruta | Evidencia |
|---|---|
| `README.md` | Propósito educativo, módulos principales y advertencias. |
| `docs/SCT_MODULE.md` | SCT definido como Script Concordance Test. |
| `docs/HISTOPATHOLOGY_AI.md` | Guía técnica del clasificador CONCH/PCam/CAMELYON, ROI, DZI, QC, limitaciones. |
| `docs/HISTOPATHOLOGY_ROADMAP.md` | Estado/roadmap histopatológico, Stage histórico, alcance defendible y pendientes. |
| `docker-compose.yml` | Servicios, LLaMA 3, checkpoint Stage 16, variables RAG/heatmap. |
| `backend/requirements-histopathology.txt` | Dependencias IA: PyTorch, CONCH, OpenSlide, scikit-learn. |
| `backend/app/main.py` | Routers integrados y healthcheck. |
| `backend/app/models.py` | Entidades de usuarios, imágenes, casos, RAG, chat, SCT, heatmaps, ROI y correcciones. |
| `backend/app/auth.py` | Permisos por rol. |
| `backend/app/auth_security.py` | JWT, PBKDF2-SHA256, secreto requerido fuera de desarrollo. |
| `backend/app/routers/auth.py` | Registro, login, aprobación. |
| `backend/app/routers/chat.py` | Chatbot educativo, RAG, filtro de alcance, advertencias y logs. |
| `backend/app/routers/rag.py` | Gestión de documentos, chunks, embeddings y búsqueda. |
| `backend/app/routers/sct.py` | Generación, guardado, publicación e intentos SCT. |
| `backend/app/routers/medical_images.py` | Upload/import, DZI/OpenSlide, descarga y tiles. |
| `backend/app/routers/histopathology.py` | Estado modelo, análisis ROI, heatmaps, sesiones y correcciones. |
| `backend/app/histopathology/ml/inference_service.py` | Carga CONCH + cabeza clasificadora. |
| `backend/app/histopathology/roi_quality.py` | QC de ROI. |
| `backend/app/histopathology/heatmap_decision.py` | Decisión educativa agregada de heatmap. |
| `frontend/src/app.jsx` | Rutas de la aplicación. |
| `frontend/src/api.js` | Cliente API para chat, RAG, admin, SCT, ROI, imágenes, casos y feedback. |
| `frontend/src/pages/ChatbotPage.jsx` | UI de MediChat, fuentes RAG, advertencias y exportación. |
| `frontend/src/pages/SCTPage.jsx` | UI SCT para generar/resolver/revisar intentos. |
| `frontend/src/pages/ImagesPage.jsx` | UI de imágenes histopatológicas e historial ROI. |
| `frontend/src/components/OpenSeadragonViewer.jsx` | Visor DZI, ROI, análisis, heatmap y correcciones. |
| `frontend/src/pages/CasesPage.jsx` | Casos clínicos y recursos asociados imagen/SCT. |
| `frontend/src/pages/ConfigPage.jsx` | Administración de imágenes, RAG, SCT, usuarios, IA, correo y heatmaps preparados. |
| `frontend/e2e/README.md` | Alcance de pruebas E2E con mocks y modo backend real. |
| `backend/tests/test_histopathology_roi.py` | Validación de geometría ROI. |
| `backend/tests/test_cases_api.py` | Validación de asociación caso-imagen-SCT. |
| `apendices_evidencias/B_ejecucion_terminal/B_ET04_pytest_resultado.txt` | 178 pruebas backend aprobadas. |
| `apendices_evidencias/B_ejecucion_terminal/B_ET05_npm_build.txt` | Build frontend exitoso. |
| `apendices_evidencias/C_api_swagger_endpoints/C_API06_histopathology_status_sanitizado.json` | Estado modelo Stage 16. |
| `apendices_evidencias/C_api_swagger_endpoints/C_API13_roi_analisis_respuesta.json` | Respuesta real de análisis ROI sanitizada. |
| `apendices_evidencias/C_api_swagger_endpoints/C_API12_dzi_viewer_respuesta.xml.json` | DZI del visor. |
| `apendices_evidencias/C_api_swagger_endpoints/C_API10_chatbot_respuesta_sanitizada.json` | Respuesta chatbot sanitizada. |
| `apendices_evidencias/C_api_swagger_endpoints/C_API08_sct_attempt_respuesta.json` | Intento SCT registrado. |
| `backend/artifacts/histopathology/reports/tri_head_stage16_sane_tuned_metrics.json` | Métricas experimentales del checkpoint configurado actual. |
