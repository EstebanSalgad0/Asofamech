# Comparacion tecnica Stage 16 versus Stage 17

Fecha: 2026-06-07.

> Esta es una evaluacion tecnica interna del componente visual de ASOFAMECH.
> No constituye validacion clinica, diagnostica, prospectiva, externa ni
> regulatoria.

## Alcance metodologico

Se presentan dos perspectivas:

1. Metricas historicas de cada ejecucion, que usan tests diferentes.
2. Referencia de ambos checkpoints sobre las mismas 730 imagenes del test
   Stage 17.

La segunda perspectiva controla las imagenes evaluadas, pero no elimina la fuga
historica de Stage 16: 333 de los 730 parches, 4 de los 5 pacientes y 4 de las
8 laminas del test Stage 17 habian aparecido en el train Stage 16. Por tanto,
las cifras Stage 16 sobre estas imagenes pueden estar optimistamente sesgadas.
El test solo es independiente respecto del entrenamiento Stage 17.

## Datos y particiones

| Modelo | Split de entrenamiento | Train | Validacion | Test | Solapamiento |
|---|---|---|---|---|---|
| Stage 16 baseline | Manifest historico Stage 15 | 3.023 parches, 30 pacientes, 47 laminas | 1.160 parches, 11 pacientes, 12 laminas | 722 parches, 11 pacientes, 11 laminas | Si: train-val 9 pacientes/7 laminas; train-test 8/4; val-test 4/1 |
| Stage 17 candidato C | Split agrupado por paciente, semilla 20260607 | 3.434 parches, 24 pacientes, 41 laminas | 741 parches, 5 pacientes, 9 laminas | 730 parches, 5 pacientes, 8 laminas | No: cero pacientes, laminas o parches compartidos |

Stage 17 genero tres vistas aumentadas mas la original para train, equivalentes
a 13.736 embeddings. Los conteos de la tabla corresponden a los 3.434 parches
originales unicos.

## Metricas historicas

Estas cifras no deben compararse como un experimento controlado porque los tests
son diferentes y Stage 16 presenta fuga.

| Metrica | Stage 16, test historico | Stage 17, test independiente |
|---|---:|---:|
| Parches de test | 722 | 730 |
| Accuracy | 0.8144 | 0.8562 |
| Macro F1 | 0.7378 | 0.7931 |
| ROC-AUC tumor vs resto | 0.9489 | 0.9661 |
| Precision metastasico | 0.9146 | 0.8929 |
| Recall metastasico | 0.7459 | 0.8197 |
| F1 metastasico | 0.8217 | 0.8547 |

## Comparacion sobre las mismas imagenes

Ambos checkpoints fueron ejecutados sobre los mismos 730 parches del test
Stage 17. La columna Stage 16 sigue afectada por exposicion previa a parte de
esos pacientes, laminas y parches.

| Metrica argmax multiclase | Stage 16 | Stage 17 | Diferencia Stage 17 |
|---|---:|---:|---:|
| Accuracy | 0.8411 | **0.8562** | +1.51 puntos porcentuales |
| Macro F1 | **0.7934** | 0.7931 | -0.02 puntos porcentuales |
| ROC-AUC tumor vs resto | 0.9659 | **0.9664** | +0.05 puntos porcentuales |
| ROC-AUC macro OVR | **0.9602** | 0.9573 | -0.29 puntos porcentuales |

El macro F1 se considera practicamente empatado. Stage 17 mejora accuracy y
AUC tumoral a pesar de que Stage 16 tiene ventaja metodologica por fuga.

## Metricas por clase

| Clase | Modelo | Precision | Recall | F1 | Soporte |
|---|---|---:|---:|---:|---:|
| No metastasico | Stage 16 | **0.9586** | 0.8741 | **0.9144** | 397 |
| No metastasico | Stage 17 | 0.8894 | **0.9320** | 0.9102 | 397 |
| Metastasico | Stage 16 | **0.9538** | 0.7623 | 0.8474 | 244 |
| Metastasico | Stage 17 | 0.8929 | **0.8197** | **0.8547** | 244 |
| Estroma | Stage 16 | 0.4682 | **0.9101** | **0.6183** | 89 |
| Estroma | Stage 17 | **0.6111** | 0.6180 | 0.6145 | 89 |

Stage 17 intercambia parte de la precision metastasica por mayor sensibilidad:
detecta mas parches tumorales y obtiene mejor F1 metastasico. En estroma,
Stage 17 reduce las predicciones excesivas de esa clase y mejora su precision,
pero pierde recall. El F1 de estroma queda practicamente igual.

## Matrices de confusion

Orden de filas y columnas: no metastasico, metastasico, estroma.

Stage 16 sobre las 730 imagenes comunes:

| Real / Predicha | No metastasico | Metastasico | Estroma |
|---|---:|---:|---:|
| No metastasico | 347 | 7 | 43 |
| Metastasico | 9 | 186 | 49 |
| Estroma | 6 | 2 | 81 |

Stage 17 sobre su test independiente:

| Real / Predicha | No metastasico | Metastasico | Estroma |
|---|---:|---:|---:|
| No metastasico | 370 | 14 | 13 |
| Metastasico | 22 | 200 | 22 |
| Estroma | 24 | 10 | 55 |

Stage 17 clasifica correctamente 200 parches metastasicos frente a 186 de
Stage 16 y reduce de 49 a 22 los metastasicos enviados erroneamente a estroma.

## Umbrales operativos

Se usa temperatura 1.0, correspondiente a la configuracion recomendada para
integracion. Stage 16 usa su umbral productivo 0.90. Stage 17 usa 0.35,
seleccionado en validacion.

| Metrica tumor vs resto | Stage 16, umbral 0.90 | Stage 17, umbral 0.35 |
|---|---:|---:|
| TP | 84 | **208** |
| FP | **1** | 28 |
| FN | 160 | **36** |
| TN | **485** | 458 |
| Precision | **0.9882** | 0.8814 |
| Sensibilidad | 0.3443 | **0.8525** |
| Especificidad | **0.9979** | 0.9424 |
| F1 | 0.5106 | **0.8667** |
| Balanced accuracy | 0.6711 | **0.8974** |

El reporte Stage 17 original aplico temperature scaling `T=1.0967` y obtuvo
TP 209, FP 29, FN 35 y TN 457. La diferencia frente a temperatura 1.0 es de un
solo caso y no cambia la conclusion. Como la calibracion no mejoro de forma
consistente en test, se mantiene desactivada por defecto.

## Falsos positivos de Stage 17

Con umbral 0.35 y sin temperature scaling:

- 28 falsos positivos entre 486 casos no tumorales: 5.76%.
- 18 de 397 no metastasicos se marcan como tumor: 4.53%.
- 10 de 89 estromas se marcan como tumor: 11.24%.
- Entre las 236 alertas tumorales, 28 son falsas: 11.86%.

No es un aumento despreciable respecto de Stage 16, que produce solo un falso
positivo a 0.90. Sin embargo, Stage 17 obtiene 124 verdaderos positivos
adicionales y reduce los falsos negativos de 160 a 36: aproximadamente 4.6
verdaderos positivos adicionales por cada falso positivo adicional.

Para apoyo educativo, el compromiso es razonable porque prioriza no omitir
patrones tumorales y la salida se acompana de estados incierto/no evaluable,
control de calidad y agregacion espacial. No seria suficiente para justificar
uso diagnostico.

## Evaluacion ROI proxy

Solo Stage 17 cuenta con esta evaluacion. Se construyeron 94 bolsas de test de
hasta ocho parches ordenados por lamina. No son ROI reales contiguas ni tienen
etiquetas ROI validadas por patologos.

La estrategia recomendada fue promedio top-k, `k=3`, con umbral 0.45:

| TP | FP | FN | TN | Precision | Sensibilidad | Especificidad | F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 34 | 2 | 4 | 54 | 0.9444 | 0.8947 | 0.9643 | 0.9189 |

Este resultado sugiere que agregar tiles puede reducir falsos positivos frente
a decidir con un parche aislado, pero debe presentarse solo como analisis proxy.

## Conclusiones

### Mejora metodologica

Stage 17 mejora claramente a Stage 16: separa pacientes entre train,
validacion y test, selecciona epoch y umbral en validacion, bloquea el test y
documenta augmentations, calibracion y semillas. Es mucho mas defendible aunque
alguna metrica puntual fuese menor.

### Mejora metrica

Stage 17 no gana todas las metricas. En las mismas imagenes:

- Mejora accuracy, AUC tumoral, recall y F1 metastasico.
- Mantiene macro F1 practicamente igual.
- Pierde precision metastasica y recall de estroma.
- Mejora notablemente precision de estroma.

Ademas, Stage 16 tiene una ventaja artificial porque conocio parte del conjunto
comun durante entrenamiento. El empate o mejora de Stage 17 es por ello una
senal favorable, aunque no demuestra superioridad estadistica.

### Umbral 0.35

Es razonable para un prototipo educativo que prioriza sensibilidad. No es
adecuado para afirmar diagnostico. Los 28 falsos positivos son un costo
controlable si se mantiene:

- salida `incierto` y `no evaluable`;
- revision visual del usuario;
- advertencia no diagnostica;
- agregacion top-k/espacial;
- posibilidad de volver al baseline.

El umbral no debe reajustarse usando el test. Cualquier cambio a 0.40 o 0.45
debe seleccionarse nuevamente sobre validacion.

### Activacion recomendada

Se recomienda activar Stage 17 en una prueba controlada del prototipo educativo,
manteniendo Stage 16 como rollback. Configuracion:

```dotenv
HISTO_CLASSIFIER_CHECKPOINT=/app/model_registry/checkpoints/tri_head_stage17_variant_c_augmented.pt
HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD=0.90
HISTO_TUMOR_OPERATING_THRESHOLD=0.35
HISTO_USE_CHECKPOINT_CALIBRATION=false
```

Si la prioridad operacional fuera minimizar casi por completo falsos positivos,
Stage 16 a 0.90 seria mas conservador, pero su sensibilidad de 0.3443 lo hace
menos apropiado para exploracion educativa de patrones tumorales.

### Recomendacion para defensa

Presentar Stage 17 como modelo principal de la evaluacion tecnica y Stage 16
como baseline historico. La razon principal no es solo el aumento de accuracy,
sino la separacion por paciente, el test bloqueado y el mejor equilibrio entre
precision y sensibilidad metastasica.

## Texto breve para PPT

> Se comparo el baseline Stage 16 con el candidato Stage 17 basado en CONCH
> ViT-B/16 congelado y una cabeza MLP de tres clases. Stage 17 fue evaluado con
> un split independiente por paciente, sin solapamiento entre entrenamiento,
> validacion y test. En 730 parches de test obtuvo accuracy 0.856, macro-F1
> 0.793 y AUC tumor-vs-resto 0.966. Con un umbral tumoral de 0.35 alcanzo
> sensibilidad 0.852, precision 0.881 y especificidad 0.942. El aumento de
> sensibilidad implica mas falsos positivos que el baseline conservador, por lo
> que el sistema se mantiene como apoyo educativo, con abstencion, revision
> visual y sin interpretacion diagnostica.
