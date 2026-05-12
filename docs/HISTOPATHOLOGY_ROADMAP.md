# Hoja de ruta del modulo histopatologico

Este documento resume los objetivos pendientes para convertir el modulo actual
en un prototipo histopatologico mas robusto, defendible y operable. El foco
recomendado no es diagnostico clinico general, sino una tarea concreta:

```text
Deteccion educativa de regiones compatibles con metastasis en ganglio linfatico H&E.
```

El sistema debe presentarse siempre como apoyo educativo y exploratorio, no como
herramienta diagnostica.

## Estado actual

Ya existe una version funcional ampliada:

- visor con ROI 1 y ROI 2;
- validacion geometrica de ROIs;
- extraccion de patch desde WSI o imagen raster;
- endpoint `/api/histopathology/status`;
- endpoint `/api/histopathology/analyze-roi`;
- CONCH como extractor congelado de embeddings;
- cabeza 3-class entrenada con CAMELYON17 local ampliado;
- clases `no_metastasico`, `metastasico` y `estroma`;
- checkpoint configurado en backend y Docker;
- inferencia CUDA;
- trazabilidad con `trace_id`;
- auditoria JSONL;
- guardado de patches debug por `trace_id`;
- control de calidad de ROI con compuerta de stroma dominante;
- salida `clasificado`, `resultado_incierto` o `roi_no_evaluable`;
- UI que muestra estado del modelo, umbral, probabilidades, QC y advertencia educativa;
- importacion local de laminas CAMELYON17 ya descargadas en servidor;
- DZI dinamico para WSI `.tif/.svs` grandes sin subir varios GB por navegador;
- primer escaneo tipo heatmap sobre ROI 1, dividiendo en tiles y pintando
  sospecha metastasica en el visor.

Limitacion principal actual:

```text
CONCH + cabeza 3-class Stage 6 funciona como clasificador educativo de ROI y ya
detecta metastasis en regiones tumorales anotadas de CAMELYON17, pero aun no es
un sistema robusto de lamina completa. Puede fallar en regiones mixtas, stroma,
fibrosis, inflamacion, artefactos o tejido linfoide no representativo.
```

Resultado practico mas reciente:

```text
Stage 6 3-class CAMELYON17 ampliado:
accuracy test=0.836
macro F1=0.827
ROC-AUC tumor OVR=0.942
stroma->tumor=11/50 = 22%

Validacion visual controlada:
patient_017_node_2.tif, ROI dentro de XML tumoral oficial
P(metastasico)=99.8%

Primer heatmap ROI 1:
POST /api/histopathology/scan-roi
tile 512x512 sobre coordenada tumoral oficial
P(metastasico)=99.8%
```

## Objetivo general

Construir un flujo mas solido:

```text
Lamina completa
-> division en tiles/patches
-> filtro de tejido util
-> embeddings CONCH/otro foundation model
-> clasificador por patch
-> heatmap de sospecha
-> agregador MIL/CLAM
-> resultado educativo de lamina: positiva, negativa o incierta
```

## Alcance defendible

Alcance recomendado para tesis/prototipo:

- tejido: ganglio linfatico H&E;
- tarea: metastasis vs no metastasis;
- nivel 1: resultado por ROI/patch;
- nivel 2: heatmap de regiones sospechosas;
- nivel 3: clasificacion educativa de lamina completa con MIL/CLAM.

No se recomienda prometer:

- diagnostico clinico autonomo;
- deteccion de cualquier cancer;
- clasificacion de subtipos tumorales;
- grado histologico;
- reemplazo del patologo;
- reentrenamiento completo de CONCH/UNI/GigaPath desde cero.

## Hardware y recursos

Con el equipo actual es viable:

- GPU NVIDIA con 16 GB VRAM;
- extraccion de embeddings CONCH en CUDA;
- entrenamiento de cabezas ligeras;
- hard negative mining;
- heatmaps por lamina;
- MIL/CLAM sobre embeddings precomputados.

No conviene hacer localmente:

- entrenar CONCH desde cero;
- fine-tuning pesado del backbone completo;
- entrenar foundation models gigantes desde cero;
- procesar datasets WSI completos sin control de espacio y cache.

Espacio recomendado:

```text
200 GB libres: minimo razonable
500 GB libres: comodo
1 TB libre: ideal para CAMELYON/SLN-Breast extensivo
```

## Fase 1: Robustecer ROI con hard negatives

Objetivo:

Mejorar el clasificador de ROI/patch para reducir falsos positivos en regiones
que visualmente no corresponden a metastasis.

Datos a agregar como negativos dificiles:

- estroma;
- tejido adiposo;
- fondo blanco;
- fibrosis;
- zonas inflamatorias;
- tejido conectivo;
- tejido linfoide normal;
- artefactos de corte/tincion;
- patches con poca densidad celular;
- falsos positivos generados por el modelo actual.

Fuentes sugeridas:

- PCam como base inicial;
- SLN-Breast para patches reales cercanos al uso del prototipo;
- CAMELYON16/17 para WSI y anotaciones de metastasis;
- ROIs manuales seleccionadas desde nuestras pruebas reales.

Tareas:

- Crear un manifiesto versionable de patches:

```csv
patch_id,source,slide_id,path,label,hard_negative_type,x,y,width,height,split
```

- Extraer patches positivos desde zonas tumorales anotadas.
- Extraer patches negativos desde tejido normal y hard negatives.
- Guardar patches fuera de Git en `backend/data` o `backend/artifacts`.
- Extraer embeddings CONCH por lotes.
- Entrenar una cabeza binaria nueva:
  - logistic regression o linear head;
  - MLP pequeno si la cabeza lineal no basta;
  - class weights si hay desbalance.
- Evaluar por dataset y por tipo de negativo.
- Ajustar umbral de confianza.
- Mantener salida `resultado_incierto` para probabilidades intermedias.

Metricas minimas:

- AUC ROC;
- accuracy;
- sensibilidad;
- especificidad;
- precision;
- F1;
- matriz de confusion;
- falsos positivos por tipo de hard negative;
- falsos negativos en patches tumorales.

Criterio de cierre:

- el modelo reduce falsos positivos en estroma/adiposo/fondo frente al modelo PCam inicial;
- se documenta el dataset usado;
- se versiona el script de extraccion;
- se guarda checkpoint nuevo;
- se deja reporte JSON/CSV con metricas.

Tiempo estimado:

```text
3 a 5 dias para una primera version robusta de ROI.
```

## Fase 2: Heatmap de lamina completa

Objetivo:

Que el sistema no dependa solo de una ROI manual, sino que pueda explorar la
lamina y sugerir zonas sospechosas.

Estado implementado:

- endpoint inicial `/api/histopathology/scan-roi`;
- escaneo acotado a una ROI de entrada para controlar costo;
- grid configurable con `tile_size`, `stride` y `max_tiles`;
- cada tile pasa por QC, CONCH y cabeza 3-class;
- respuesta con `tumor_score`, clase, probabilidades, QC y mejor tile;
- overlay en OpenSeadragon sobre ROI 1;
- persistencia JSON del heatmap por `trace_id` y ultimo mapa por `image_id`;
- recuperacion automatica del ultimo mapa guardado al abrir una imagen;
- jobs asincronicos en memoria para ejecutar heatmaps con progreso.

Pendiente para cerrar la fase completa:

- ejecutar el escaneo por bandas/lotes en laminas completas;
- cachear embeddings/scores por coordenada;
- convertir scores guardados en heatmap persistente.

Flujo:

```text
WSI
-> generar grid de tiles
-> filtrar tiles sin tejido util
-> extraer embeddings CONCH
-> clasificar cada tile
-> suavizar/normalizar scores
-> mostrar heatmap sobre el visor
```

Tareas:

- Crear extractor de tiles WSI con OpenSlide.
- Definir tamano de tile:
  - 224/256 px para patch compatible directo;
  - 512/1024 px si se quiere mas contexto antes del resize CONCH.
- Aplicar filtro de tejido util antes de inferir.
- Cachear embeddings por `slide_id`, coordenadas y checkpoint.
- Ejecutar inferencia en batches con CUDA.
- Guardar scores por tile:

```csv
slide_id,x,y,width,height,score_metastasico,score_no_metastasico,status
```

- Agregar endpoint para consultar heatmap.
- Pintar overlay en OpenSeadragon.
- Permitir seleccionar una tile sospechosa como ROI 2.

Criterio de cierre:

- una lamina `.svs` puede producir un heatmap reproducible;
- el usuario puede ver zonas con mayor sospecha;
- los tiles sin tejido no se clasifican;
- se registran coordenadas y scores.

Tiempo estimado:

```text
4 a 7 dias.
```

## Fase 3: MIL/CLAM para lamina completa

Objetivo:

Pasar de clasificacion de patch a clasificacion educativa de lamina completa.

Motivacion:

En patologia real, una lamina positiva puede tener muchas zonas normales. Un
clasificador por patch no basta para decir si una lamina completa es positiva.
MIL/CLAM permite usar etiquetas de lamina y aprender que tiles son importantes.

Flujo:

```text
slide label
-> bolsa de embeddings por slide
-> attention MIL/CLAM
-> score de lamina
-> tiles con mayor atencion
-> heatmap interpretable
```

Tareas:

- Preparar bolsas de embeddings por lamina.
- Usar etiquetas:
  - `target=1`: lamina positiva/metastasica;
  - `target=0`: lamina negativa/no metastasica.
- Separar train/val/test por lamina, no por patch.
- Entrenar MIL/CLAM sobre embeddings.
- Evaluar a nivel de lamina.
- Exportar atencion por tile para visualizacion.
- Comparar con agregacion simple:
  - max score;
  - top-k mean;
  - percentile score.

Metricas minimas:

- AUC por lamina;
- sensibilidad por lamina;
- especificidad por lamina;
- matriz de confusion;
- analisis de errores;
- ejemplos visuales con heatmap.

Criterio de cierre:

- el sistema entrega resultado de lamina completa;
- el resultado incluye incertidumbre;
- hay heatmap/atencion para justificar visualmente;
- se documentan limitaciones y splits.

Tiempo estimado:

```text
1 a 2 semanas.
```

## Fase 4: Comparar foundation models

Objetivo:

Ver si otro extractor mejora frente a CONCH sin reentrenar modelos gigantes.

Modelos candidatos:

- CONCH: extractor actual, bueno para transferencia y vision-language.
- UNI: foundation model generalista de histopatologia.
- Prov-GigaPath: orientado a WSI y contexto de lamina completa.
- Virchow: pan-cancer potente, sujeto a acceso/licencia.

Tareas:

- Revisar acceso y licencia de cada modelo.
- Implementar interfaz comun de extractor:

```text
extractor.encode_pil(image) -> embedding
```

- Generar embeddings para el mismo conjunto de patches.
- Entrenar la misma cabeza sobre cada extractor.
- Comparar metricas bajo el mismo split.
- Documentar costo, velocidad, VRAM y restricciones de uso.

Criterio de cierre:

- tabla comparativa de modelos;
- eleccion justificada del extractor principal;
- fallback si un modelo no tiene acceso/licencia compatible.

Tiempo estimado:

```text
3 a 7 dias por comparacion inicial, dependiendo de acceso y descarga.
```

## Fase 5: Integracion de producto y defensa

Objetivo:

Dejar el flujo operable y explicable para demostracion.

Tareas de backend:

- Endpoint para iniciar generacion de heatmap.
- Endpoint para consultar progreso.
- Endpoint para consultar tiles/scores.
- Persistir resultados por `image_id`.
- Guardar version de modelo, checkpoint y thresholds.
- Registrar auditoria por analisis.
- Manejar errores de GPU, memoria y WSI corruptas.

Tareas de frontend:

- Mostrar progreso de analisis de lamina.
- Mostrar heatmap sobre OpenSeadragon.
- Permitir activar/desactivar overlay.
- Mostrar tiles mas sospechosas.
- Permitir saltar a una tile/ROI.
- Mostrar resultado de lamina y resultado de ROI por separado.
- Mostrar advertencia educativa fija.

Tareas de documentacion:

- explicar dataset;
- explicar splits;
- explicar CONCH y embeddings congelados;
- explicar hard negative mining;
- explicar MIL/CLAM;
- documentar limitaciones;
- incluir metricas y ejemplos;
- describir que el sistema no es diagnostico.

Tiempo estimado:

```text
2 a 4 dias para documentacion y pulido, despues de tener modelos y heatmap.
```

## Orden recomendado de ejecucion

1. Congelar el estado actual como baseline.
2. Crear manifiesto de patches y dataset local.
3. Extraer hard negatives desde SLN-Breast y/o CAMELYON.
4. Extraer embeddings CONCH para el nuevo dataset.
5. Entrenar nueva cabeza binaria.
6. Evaluar contra PCam, SLN-Breast y hard negatives.
7. Ajustar umbral `resultado_incierto`.
8. Integrar checkpoint nuevo al backend.
9. Crear pipeline de tiles para WSI.
10. Generar heatmap por lamina.
11. Entrenar MIL/CLAM con embeddings por slide.
12. Integrar resultado de lamina completa.
13. Comparar CONCH vs otro extractor si el tiempo alcanza.
14. Documentar resultados, limitaciones y defensa metodologica.

## Estimacion global

```text
Version robusta de ROI:        3 a 5 dias
Heatmap WSI:                   4 a 7 dias
MIL/CLAM por lamina:           1 a 2 semanas
Documentacion y defensa:       2 a 4 dias
Comparacion de modelos extra:  3 a 7 dias adicionales
```

Resumen:

```text
Minimo serio:        1 semana
Bueno y defendible:  2 a 3 semanas
Muy pulido:          4 semanas
```

## Riesgos principales

- Etiquetas de lamina no equivalen a etiquetas de patch.
- Una lamina positiva puede contener muchas ROIs negativas.
- Las anotaciones tumorales pueden no estar disponibles para todos los datos.
- El modelo puede aprender artefactos del dataset si no se balancean fuentes.
- Los hard negatives requieren curacion manual o semi-automatica.
- WSI grandes consumen mucho disco y tiempo de I/O.
- Algunos foundation models pueden tener restricciones de licencia o acceso.

Mitigaciones:

- separar evaluacion por fuente de datos;
- usar splits por lamina;
- guardar manifiestos reproducibles;
- mantener `roi_no_evaluable` e `incierto`;
- reportar limitaciones de forma explicita;
- no presentar la salida como diagnostico.

## Proxima accion concreta

La siguiente tarea tecnica deberia ser:

```text
Crear pipeline de dataset hard negative:
1. leer laminas SLN-Breast/CAMELYON;
2. muestrear patches positivos y negativos;
3. guardar manifiesto CSV;
4. extraer embeddings CONCH;
5. entrenar una nueva cabeza;
6. comparar contra el checkpoint PCam actual.
```

Ese paso es el que mas probablemente mejorara el comportamiento que observamos:
regiones estromales o no tumorales que el clasificador inicial marcaba como
metastasicas.
