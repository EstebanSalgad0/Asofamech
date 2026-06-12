# Reporte tecnico Stage 17 - componente visual histopatologico

Fecha: 2026-06-07.

> Los resultados corresponden a una evaluacion tecnica interna del componente
> visual y no constituyen validacion clinica, diagnostica, prospectiva, externa
> ni regulatoria.

## Modelo

- Backbone: CONCH `conch_ViT-B-16` preentrenado por MahmoodLab.
- Componente usado: encoder visual CONCH.
- Estado del backbone: completamente congelado.
- Entrada efectiva: 448 x 448 RGB mediante el preprocesamiento de CONCH.
- Embedding: 512 dimensiones.
- Cabeza: Linear 512-256, ReLU, Dropout 0.25, Linear 256-3.
- Clases: `no_metastasico`, `metastasico`, `estroma`.
- `estroma` se mantiene como clase auxiliar de separacion y abstencion tecnica;
  no se presenta como categoria clinica independiente.

## Split

Manifest: `camelyon17_manifest_stage17_patient_split_v1.csv`.

Semilla: `20260607`. Todos los parches de un paciente pertenecen a un solo
split. No fue necesario usar el fallback por lamina.

| Split | Pacientes | Laminas | Parches | No metastasico | Metastasico | Estroma |
|---|---:|---:|---:|---:|---:|---:|
| Train | 24 | 41 | 3.434 | 1.829 | 1.214 | 391 |
| Validacion | 5 | 9 | 741 | 407 | 244 | 90 |
| Test | 5 | 8 | 730 | 397 | 244 | 89 |

Validacion automatica: cero pacientes, laminas o `patch_id` compartidos entre
train, validacion y test.

## Datos y etiquetas

Los parches provienen de CAMELYON17 y de los manifests derivados ya presentes
en el proyecto. Las etiquetas tumorales se originan en anotaciones/coordenadas
oficiales cuando estan disponibles; los negativos y hard negatives conservan
su procedencia en `label_source`, `annotation_status` y `hard_negative_type`.

Los datos son imagenes histopatologicas reales de un dataset publico. Este
trabajo no incorpora una cohorte local independiente ni validacion por
patologos sobre las salidas del prototipo.

## Augmentations

Preset `histo_moderate_v1`, aplicado solo a train:

- Vistas con rotaciones fijas de 90, 180 y 270 grados.
- Flip horizontal y vertical con probabilidad 0.5.
- Random resized crop controlado, escala 0.90-1.00.
- Color jitter moderado: brillo/contraste 0.08, saturacion 0.06, hue 0.02.
- Tres vistas aumentadas mas la vista original por parche.
- Semilla `20260607`.

La normalizacion de tincion se dejo desactivada porque no existe una lamina de
referencia validada. Introducir Macenko/Reinhard sin ese control podria cambiar
la distribucion de color de forma no defendible.

## Variantes

| Variante | Balance | Augmentation | Accuracy | Macro-F1 | AUC tumor OVR | P tumor | R tumor | F1 tumor |
|---|---|---|---:|---:|---:|---:|---:|---:|
| A | Ninguno | No | 0.8411 | 0.7691 | 0.9657 | 0.9212 | 0.7664 | 0.8367 |
| B | Pesos de clase | No | 0.8233 | 0.7684 | 0.9569 | 0.9465 | 0.7254 | 0.8213 |
| C | Ninguno | Si | **0.8562** | **0.7931** | **0.9661** | 0.8929 | **0.8197** | **0.8547** |
| D | Pesos de clase | Si | 0.8315 | 0.7718 | 0.9592 | 0.9059 | 0.7500 | 0.8206 |

Los pesos de clase aumentaron el recall de estroma, pero redujeron el balance
global y el recall tumoral. C se recomienda como candidato tecnico.

El entrenador deja configurables `class_weights`, `oversample` y `focal`.
El undersampling controlado sigue disponible mediante
`balance_patch_manifest.py`. Para la comparacion principal se eligieron pesos
de clase porque no descartan datos; oversampling y focal no se promovieron a
candidatos al observar que el balanceo ponderado ya desplazaba el modelo hacia
estroma a costa del recall tumoral.

## Matriz de confusion de C

Filas: etiqueta real. Columnas: prediccion.

| Real / Predicha | No metastasico | Metastasico | Estroma |
|---|---:|---:|---:|
| No metastasico | 370 | 14 | 13 |
| Metastasico | 22 | 200 | 22 |
| Estroma | 24 | 10 | 55 |

Metricas por clase:

| Clase | Precision | Recall | F1 | Soporte |
|---|---:|---:|---:|---:|
| No metastasico | 0.8894 | 0.9320 | 0.9102 | 397 |
| Metastasico | 0.8929 | 0.8197 | 0.8547 | 244 |
| Estroma | 0.6111 | 0.6180 | 0.6145 | 89 |

Figura: `docs/assets/histopathology_stage17/confusion_test.png`.

## Umbral operativo

El umbral se eligio exclusivamente sobre validacion, imponiendo precision
tumoral minima de 0.85 y maximizando F1/balanced accuracy.

- Umbral seleccionado: `P(tumor) >= 0.35`.
- Test bloqueado: TP 209, FP 29, FN 35, TN 457.
- Precision: 0.8782.
- Sensibilidad: 0.8566.
- Especificidad: 0.9403.
- F1: 0.8672.
- Balanced accuracy: 0.8984.

El umbral 0.35 es mas adecuado para apoyo educativo que 0.90 porque reduce la
perdida de sensibilidad. Debe combinarse con salida `incierto`, control de
calidad de tejido y advertencia no diagnostica.

En backend se configura como `HISTO_TUMOR_OPERATING_THRESHOLD=0.35`. No debe
confundirse con `HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD`, que controla la
abstencion multiclase y permanece en 0.90 para conservar el comportamiento
historico fuera de la politica tumor-vs-resto.

## Calibracion

Temperature scaling ajustado en validacion produjo `T=1.0967`.

| Split | Estado | Brier multiclase | Brier tumor | ECE | NLL |
|---|---|---:|---:|---:|---:|
| Validacion | Antes | 0.2629 | 0.0984 | 0.0525 | 0.4789 |
| Validacion | Despues | 0.2614 | 0.0982 | 0.0540 | 0.4767 |
| Test | Antes | 0.2080 | 0.0759 | 0.0376 | 0.3863 |
| Test | Despues | 0.2104 | 0.0775 | 0.0470 | 0.3940 |

La mejora en validacion es marginal y no se replica en test. Por ello la
calibracion queda implementada, pero desactivada por defecto. Para el candidato
se recomienda temperatura 1.0 hasta disponer de una cohorte de calibracion mas
amplia e independiente.

## Limitaciones y trabajo futuro

- Solo hay 34 pacientes y 5 pacientes en el test agrupado.
- No existe validacion externa, prospectiva, multicentrica ni regulatoria.
- No hay etiquetas ROI revisadas especificamente por patologos.
- La clase estroma sigue teniendo precision/recall moderados.
- No se calcularon intervalos de confianza ni variabilidad entre varias semillas.
- No se ejecuto el ajuste parcial opcional del encoder CONCH.
- No se aplico normalizacion de tincion por falta de referencia validada.
- La evaluacion ROI es una aproximacion por bolsas de parches, no el flujo real
  completo de ROI de usuarios.

Trabajo futuro prioritario: cohorte externa, agrupacion por centro, anotacion ROI
por especialistas, repeticion multisemilla, intervalos bootstrap y evaluacion
controlada de fine-tuning parcial.

## Agregacion ROI/tiles

Se compararon media, maximo, top-k y proporcion positiva sobre 97 bolsas de
validacion y 94 de test, cada una con hasta 8 parches ordenados por lamina.

| Estrategia | Umbral val | Precision test | Sensibilidad test | Especificidad test | Balanced acc. |
|---|---:|---:|---:|---:|---:|
| Media | 0.20 | 0.8974 | 0.9211 | 0.9286 | 0.9248 |
| Maximo | 0.80 | 0.9655 | 0.7368 | 0.9821 | 0.8595 |
| Top-k media, k=3 | 0.45 | 0.9444 | 0.8947 | 0.9643 | **0.9295** |
| Proporcion positiva | 0.30 | 0.9677 | 0.7895 | 0.9821 | 0.8858 |

Se recomienda `top-k mean` como resumen informativo. Esta evaluacion es solo un
proxy: las bolsas no son ROI contiguas seleccionadas por usuarios y no tienen
etiqueta ROI validada por especialistas.

## Heatmap

El heatmap es una grilla de probabilidades por tiles. No es Grad-CAM, mapa de
atencion ni explicacion causal. El backend mantiene las reglas espaciales
existentes y agrega media, maximo, top-k y proporcion positiva como resumen
compatible. El frontend muestra la advertencia de uso educativo.

## Comparacion con Stage 16

Stage 16 reportaba accuracy 0.8144, macro-F1 0.7378 y AUC 0.9489, pero su test
tenia fuga por paciente/lamina. Stage 17 C obtiene mejores cifras sobre un test
agrupado, aunque **no debe afirmarse superioridad estadistica directa** porque
los conjuntos de test no son equivalentes.

## Recomendacion

- Mantener Stage 16 como productivo hasta una prueba controlada de integracion.
- Registrar C como candidato tecnico.
- Usar umbral 0.35 al activar C.
- Mantener temperature scaling desactivado.
- Mantener `estroma` como clase auxiliar y salida no evaluable.
- No presentar ROC/AUC como validacion clinica. Puede incluirse como evaluacion
  tecnica interna, junto con split, matriz de confusion, metricas por clase e
  intervalos de incertidumbre como trabajo futuro.

## Defensa

En el PPT presentar:

1. CONCH ViT-B/16 congelado y cabeza MLP 512-256-3.
2. Rol auxiliar de estroma.
3. Split por paciente 24/5/5 y ausencia de solapamiento.
4. Matriz de confusion y metricas por clase de C.
5. Umbral 0.35 seleccionado en validacion.
6. Heatmap como grilla de tiles, no Grad-CAM.
7. Alcance educativo y limitaciones.

Preguntas probables:

- Por que se congelo CONCH y no se hizo fine-tuning completo.
- Como se evito fuga de datos.
- Por que AUC no implica utilidad clinica.
- Por que se conserva estroma.
- Como se eligio el umbral.
- Que ocurre con ROI fuera de dominio o de mala calidad.
- Si las probabilidades estan calibradas.
- Si un patologo valido las salidas.

Respuesta metodologica central: el sistema demuestra integracion tecnica y
desempeno exploratorio en datos publicos agrupados por paciente; no demuestra
generalizacion clinica, seguridad diagnostica ni validez externa.

## Reproduccion

Ejecutar desde `backend` con la venv activa.

```powershell
python histopathology_offline/split_manifest_grouped.py `
  --manifest artifacts/histopathology/manifests/camelyon17_manifest_stage15_heavy_neg.csv `
  --output artifacts/histopathology/manifests/camelyon17_manifest_stage17_patient_split_v1.csv `
  --summary-json artifacts/histopathology/reports/stage17_patient_split_v1_summary.json `
  --summary-csv artifacts/histopathology/reports/stage17_patient_split_v1_distribution.csv `
  --seed 20260607 --search-trials 30000

python histopathology_offline/reuse_manifest_embeddings.py `
  --source-embeddings-dir artifacts/histopathology/embeddings-stage15-heavy-neg `
  --target-manifest artifacts/histopathology/manifests/camelyon17_manifest_stage17_patient_split_v1.csv `
  --output-dir artifacts/histopathology/embeddings-stage17-patient-split-v1

python histopathology_offline/extract_manifest_embeddings.py `
  --manifest artifacts/histopathology/manifests/camelyon17_manifest_stage17_patient_split_v1.csv `
  --output-dir artifacts/histopathology/embeddings-stage17-augmented-v1 `
  --splits train --augmentation-preset histo_moderate `
  --augmented-train-views 3 --seed 20260607
```

Las variantes se entrenan con
`histopathology_offline/train_manifest_head_rigorous.py`, cambiando
`--balance-strategy` entre `none` y `class_weights` y seleccionando el
directorio de embeddings determinista o aumentado. Los JSON completos se
encuentran en `backend/model_registry/reports`.
