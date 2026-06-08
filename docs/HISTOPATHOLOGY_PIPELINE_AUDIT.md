# Auditoria del pipeline histopatologico ASOFAMECH

Fecha de auditoria: 2026-06-07.

## Arquitectura del software

ASOFAMECH no implementa microservicios para el modulo histopatologico. La
arquitectura de aplicacion es un **monolito modular con organizacion por capas**:

- Presentacion: React/Vite en `frontend/src`.
- API y controladores: routers FastAPI en `backend/app/routers`.
- Servicios y dominio: `backend/app/histopathology`.
- Persistencia: PostgreSQL y almacenamiento de artefactos.
- ML offline: `backend/histopathology_offline`.
- Infraestructura: Docker Compose separa frontend, backend, PostgreSQL y Ollama
  como contenedores, pero el analisis histopatologico vive dentro del backend.

Por tanto, en la defensa corresponde hablar de arquitectura cliente-servidor,
backend modular por capas y despliegue multicontenedor. No corresponde afirmar
que el clasificador sea un microservicio independiente.

## Mapa de archivos

| Responsabilidad | Archivo principal |
|---|---|
| Carga de CONCH | `backend/app/histopathology/ml/conch_feature_extractor.py` |
| Inferencia y checkpoint | `backend/app/histopathology/ml/inference_service.py` |
| Cabeza MLP | `backend/app/histopathology/ml/classifier_head.py` |
| Extraccion offline de embeddings | `backend/histopathology_offline/extract_manifest_embeddings.py` |
| Dataset y esquema de manifest | `backend/histopathology_offline/manifest_dataset.py` |
| Entrenador historico Stage 16 | `backend/histopathology_offline/train_manifest_head_3class.py` |
| Entrenador riguroso Stage 17 | `backend/histopathology_offline/train_manifest_head_rigorous.py` |
| Split por paciente/lamina | `backend/histopathology_offline/split_manifest_grouped.py` |
| Balance de manifests | `backend/histopathology_offline/balance_patch_manifest.py` |
| Augmentations | `backend/histopathology_offline/histology_augmentations.py` |
| Metricas y calibracion | `backend/histopathology_offline/rigorous_evaluation.py` |
| Agregacion ROI/tiles | `backend/histopathology_offline/roi_aggregation.py` |
| Evaluacion proxy ROI | `backend/histopathology_offline/evaluate_roi_aggregation.py` |
| Decision espacial heatmap | `backend/app/histopathology/heatmap_decision.py` |
| Endpoints e integracion | `backend/app/routers/histopathology.py` |
| Vista y leyenda | `frontend/src/components/OpenSeadragonViewer.jsx` |
| Docker y variables | `docker-compose.yml`, `.env.example`, `backend/Dockerfile` |
| Registro de modelos | `backend/model_registry` |

## Baseline conservado

- Checkpoint: `tri_head_camelyon17_stage16_sane_tuned_v1.pt`.
- Backbone: CONCH `conch_ViT-B-16`, encoder visual congelado.
- Embedding: 512 dimensiones.
- Cabeza: Linear 512-256, ReLU, Dropout 0.25, Linear 256-3.
- Clases: no metastasico, metastasico y estroma auxiliar.
- Umbral productivo: 0.90.

El baseline no fue eliminado ni reemplazado.

## Problema detectado

El manifest anterior contenia 4.905 parches, 58 laminas y 34 pacientes, pero
presentaba solapamiento entre train, validacion y test:

- 4 laminas compartidas entre train y test.
- 7 laminas compartidas entre train y validacion.
- 1 lamina compartida entre validacion y test.
- 9 de 11 pacientes del test aparecian en otro split.

Las metricas Stage 16 son utiles como referencia historica, pero no como
estimacion independiente de generalizacion.

## Pipeline Stage 17

El nuevo flujo conserva CONCH congelado y agrega:

1. Split agrupado por paciente con fallback por lamina.
2. Validacion automatica de ausencia de solapamiento.
3. Balanceo configurable.
4. Augmentations reproducibles solo en train.
5. Seleccion de epoch, umbral y temperatura solo con validacion.
6. Test bloqueado para reporte final.
7. Metricas por clase, matriz de confusion, AUC, calibracion y umbrales.
8. Agregacion de tiles y advertencia explicita de que el mapa no es Grad-CAM.
