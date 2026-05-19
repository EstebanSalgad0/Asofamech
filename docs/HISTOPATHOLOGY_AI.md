# Modulo histopatologico: entrenamiento PCam + CONCH

Esta guia cierra la parte offline del clasificador real:

1. instalar dependencias IA y validar CONCH;
2. cargar PCam y extraer embeddings CONCH;
3. entrenar y evaluar la cabeza binaria.

> Uso educativo, no diagnostico. La tarea PCam es binaria: metastasico vs no metastasico en patches de ganglio linfatico.

## 1. Entorno IA

Usa Python 3.10, 3.11 o 3.12. Python 3.13+ puede no tener wheels compatibles para PyTorch/CONCH.

Desde `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-histopathology.txt
```

El checkpoint default `MahmoodLab/CONCH` es gated en Hugging Face. Usa un token
con acceso aprobado:

```powershell
$env:HISTO_HF_TOKEN = "hf_..."
```

Valida dependencias e import de CONCH:

```powershell
python -m histopathology_offline.validate_ai_environment
```

Valida ademas que el checkpoint cargue y genere un embedding:

```powershell
python -m histopathology_offline.validate_ai_environment --load-conch
```

## 2. PCam y embeddings

Hay dos rutas soportadas:

- `--source torchvision --download`: usa `torchvision.datasets.PCAM` para descargar/cargar PCam.
- `--source hdf5`: usa archivos HDF5 locales con nombres como `camelyonpatch_level_2_split_train_x.h5` y `camelyonpatch_level_2_split_train_y.h5`.

Ejemplo con descarga de torchvision:

```powershell
python -m histopathology_offline.extract_pcam_embeddings `
  --pcam-root data/pcam `
  --source torchvision `
  --download `
  --output-dir artifacts/histopathology/embeddings
```

Smoke run con pocos ejemplos por split:

```powershell
python -m histopathology_offline.extract_pcam_embeddings `
  --pcam-root data/pcam `
  --source auto `
  --download `
  --limit-per-split 64 `
  --output-dir artifacts/histopathology/embeddings-smoke
```

Cada archivo guardado contiene `x`, `y` y `metadata`:

- `pcam_train_embeddings.pt`
- `pcam_val_embeddings.pt`
- `pcam_test_embeddings.pt`

## 3. Entrenar y evaluar

Entrena la cabeza binaria:

```powershell
python -m histopathology_offline.train_binary_head `
  --embeddings-dir artifacts/histopathology/embeddings `
  --output artifacts/histopathology/checkpoints/binary_head_pcam.pt `
  --epochs 20
```

Evalua contra test:

```powershell
python -m histopathology_offline.evaluate_binary_head `
  --embeddings artifacts/histopathology/embeddings/pcam_test_embeddings.pt `
  --checkpoint artifacts/histopathology/checkpoints/binary_head_pcam.pt `
  --output artifacts/histopathology/reports/metrics_test.json
```

Tambien se puede correr todo en una sola tuberia:

```powershell
python -m histopathology_offline.run_pcam_pipeline `
  --pcam-root data/pcam `
  --source torchvision `
  --download `
  --epochs 20
```

La tuberia escribe:

- `artifacts/histopathology/checkpoints/binary_head_pcam.pt`
- `artifacts/histopathology/reports/metrics_test.json`
- `artifacts/histopathology/pcam_pipeline_manifest.json`

## 4. Conectar al backend

Configura el checkpoint entrenado antes de levantar FastAPI:

```powershell
$env:HISTO_CLASSIFIER_CHECKPOINT = "C:\ruta\absoluta\Asofamech\backend\artifacts\histopathology\checkpoints\tri_head_camelyon17_stage10_balanced_v1_weighted.pt"
$env:HISTO_CONCH_CHECKPOINT_REF = "hf_hub:MahmoodLab/conch"
$env:HISTO_AUDIT_LOG_PATH = "artifacts/histopathology/audit_log.jsonl"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Verifica estado:

```powershell
Invoke-RestMethod -Uri http://localhost:8001/api/histopathology/status -Method GET
```

El endpoint debe responder `model_ready=true` cuando el checkpoint de la cabeza
3-class y CONCH esten disponibles. En Docker, la ruta esperada del checkpoint es:

```text
/app/artifacts/histopathology/checkpoints/tri_head_camelyon17_stage10_balanced_v1_weighted.pt
```

En ejecucion local, la ruta se define con `HISTO_CLASSIFIER_CHECKPOINT`.

## 5. Backend Docker con IA

El backend Docker instala las dependencias IA cuando Compose construye la imagen
con `INSTALL_HISTOPATHOLOGY_AI=true`. Los artefactos no se copian dentro de la
imagen; se montan desde `backend/artifacts` para mantener la imagen reproducible
y liviana.

Variables y mounts configurados en `docker-compose.yml`:

- `HISTO_CLASSIFIER_CHECKPOINT=/app/artifacts/histopathology/checkpoints/tri_head_camelyon17_stage10_balanced_v1_weighted.pt`
- `HISTO_CONCH_CHECKPOINT_REF=hf_hub:MahmoodLab/conch`
- `HISTO_AUDIT_LOG_PATH=/app/artifacts/histopathology/audit_log.jsonl`
- `HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD=0.90`
- `HISTO_LOW_SUSPICION_NO_METASTATIC_MIN=0.55`
- `HISTO_LOW_SUSPICION_TUMOR_MAX=0.25`
- `HISTO_SAVE_DEBUG_PATCHES=true`
- `HISTO_DEBUG_PATCH_DIR=/app/artifacts/histopathology/debug_patches`
- `./backend/artifacts:/app/artifacts`
- `huggingface_cache:/root/.cache/huggingface`
- GPU NVIDIA reservada para el servicio `backend`

Si el checkpoint CONCH no esta en cache, exporta un token aprobado antes del
build/run:

```powershell
$env:HISTO_HF_TOKEN = "hf_..."
```

Reconstruye y recrea el backend:

```powershell
cd C:\ruta\al\proyecto\Asofamech
docker compose up -d --build --force-recreate backend
```

Valida desde el host:

```powershell
Invoke-RestMethod "http://127.0.0.1:8001/api/histopathology/status" |
  ConvertTo-Json -Depth 10
```

Valida dentro del contenedor:

```powershell
docker compose exec backend python -m histopathology_offline.validate_ai_environment --device cuda --load-conch
```

El archivo `.env` debe contener el nombre de la variable, no solo el token:

```env
HISTO_HF_TOKEN=hf_tu_token_aprobado
```

`.env` no se versiona. El repositorio solo incluye `.env.example`.

## 6. Flujo de visor, DZI y ROI

El visor histopatologico trabaja sobre imagenes registradas en el backend. Al
subir una imagen desde la UI, el backend la guarda en `uploads/medical_images` y
genera DZI en `uploads/dzi_tiles` cuando corresponde.

Formatos soportados por carga:

- `.svs`
- `.jpg`
- `.jpeg`
- `.png`
- `.tiff`
- `.tif`

Para `.svs`, los tiles DZI se generan con OpenSlide. Para PNG/JPG/TIFF, el
backend genera una piramide DZI raster para que tambien puedan abrirse con
OpenSeadragon y usar ROI 1/ROI 2.

Reglas actuales:

- ROI 1 define una region amplia de contexto.
- ROI 2 debe estar contenida dentro de ROI 1.
- ROI 2 es el patch que se extrae e infiere.
- ROI 2 debe medir al menos `32x32` pixeles.
- ROI 2 debe medir como maximo `4096x4096` pixeles.
- El patch extraido se preprocesa con CONCH, normalmente a `224x224`.

En laminas WSI reales se recomienda probar ROI 2 entre `512x512` y `2048x2048`
pixeles. No conviene usar la lamina completa como ROI 2.

Cada analisis exitoso devuelve:

- `trace_id`
- timestamp `analyzed_at`
- `status`: `clasificado`, `resultado_incierto` o `roi_no_evaluable`
- `clase`: `metastasico`, `no_metastasico`, `incierto` o `roi_no_evaluable`
- ROI 1 y ROI 2 usadas
- prediccion y probabilidades
- motivo y recomendacion cuando la ROI no es evaluable o la prediccion es incierta
- metricas simples de control de calidad de ROI
- metadata del patch extraido
- dimensiones de la lamina
- advertencia educativa

Ademas, el backend escribe eventos JSONL en `HISTO_AUDIT_LOG_PATH`.

## 7. Control de calidad de ROI

El clasificador PCam es binario. Si se le envia una region con fondo blanco,
tejido adiposo, estroma predominante, artefactos o baja densidad celular, el
modelo igual tendera a elegir una de las dos clases. Para evitar respuestas
demasiado tajantes fuera del dominio esperado, el endpoint `/api/histopathology/analyze-roi`
ejecuta una compuerta previa de calidad:

```text
ROI 2
-> guardar patch debug
-> estimar tejido util, fondo blanco, celularidad y estroma
-> si no es evaluable: status=roi_no_evaluable
-> si es evaluable: CONCH + cabeza binaria
-> si ninguna clase supera el umbral: status=resultado_incierto
```

Variables configurables:

- `HISTO_QC_MAX_WHITE_FRACTION`: maximo fondo/espacios claros permitido. Default `0.45`.
- `HISTO_QC_MIN_TISSUE_FRACTION`: minimo tejido util requerido. Default `0.40`.
- `HISTO_QC_MIN_NUCLEAR_FRACTION`: minimo aproximado de material nuclear/celular. Default `0.035`.
- `HISTO_QC_MAX_DOMINANT_STROMA_FRACTION`: maximo estroma permitido aunque la ROI tenga celularidad. Default `0.55`.
- `HISTO_QC_MAX_STROMA_FRACTION_WHEN_LOW_NUCLEAR`: maximo estroma permitido cuando hay baja celularidad. Default `0.65`.
- `HISTO_QC_LOW_NUCLEAR_FOR_STROMA_FRACTION`: umbral de baja celularidad para activar filtro de estroma. Default `0.12`.
- `HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD`: umbral para emitir clase binaria. Default `0.90`.

La compuerta QC tambien se puede evaluar offline contra un manifest:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.evaluate_manifest_qc `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_stage3b_stroma.csv `
  --output artifacts\histopathology\reports\camelyon17_stage3b_stroma_qc_gate.json `
  --splits test
```

Para calibrar el filtro de stroma dominante:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.evaluate_manifest_qc `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_stage3b_stroma.csv `
  --output artifacts\histopathology\reports\camelyon17_stage3b_stroma_qc_gate_040.json `
  --splits test `
  --max-dominant-stroma-fraction 0.40
```

Por cada `trace_id`, si `HISTO_SAVE_DEBUG_PATCHES=true`, se guardan:

- `debug_patch_original.png`: recorte RGB exacto de ROI 2.
- `debug_patch_preprocessed.png`: visualizacion del tensor tras el preprocess de CONCH.
- `debug_patch_preprocessed.pt`: tensor normalizado exacto que entra al encoder CONCH.

Estos archivos quedan bajo `HISTO_DEBUG_PATCH_DIR` y sirven para auditar que el
modelo recibio la zona esperada. No se versionan en Git.

## 8. Pruebas con SLN-Breast

SLN-Breast es una coleccion de laminas `.svs` de ganglio linfatico axilar en el
contexto de cancer de mama. Es util para probar el prototipo con WSI reales,
pero no reemplaza una validacion clinica formal.

El CSV de referencia descargado con la coleccion tiene este formato:

```csv
slide,target
HobI16-053768896760.svs,1
HobI16-105105202254.svs,0
```

Interpretacion usada en pruebas:

- `target=1`: lamina positiva/metastasica.
- `target=0`: lamina negativa/no metastasica.

Importante: `target.csv` clasifica la lamina completa, mientras que el modelo
actual clasifica solo el patch ROI 2. Una lamina positiva puede contener zonas
normales; por eso una ROI 2 en tejido sano puede predecirse como
`no_metastasico` aunque la lamina completa sea positiva.

Durante las pruebas locales se usaron, entre otras:

- `HobI17-440719796933.svs`: `target=1`, positiva/metastasica.
- `HobI16-723628532151.svs`: `target=0`, negativa/no metastasica.

Estas laminas y cualquier muestra `.svs`/PNG generada quedan fuera de Git por
tamano y condiciones de distribucion.

## 9. Pipeline hard negatives

La siguiente etapa del modulo robustece la cabeza binaria con patches negativos
dificiles: estroma, tejido linfoide normal, baja celularidad, adiposo/fondo y
otros patrones que pueden producir falsos positivos.

El manifiesto versionable esperado contiene:

```csv
patch_id,source,slide_id,path,label,hard_negative_type,x,y,width,height,split,qc_status,qc_tissue_fraction,qc_nuclear_fraction,qc_white_fraction,qc_stroma_fraction,annotation_status,label_source
```

`label_source` indica de donde viene la verdad usada para entrenar:

- `annotation_official`: patch positivo cuyo centro cae dentro de un poligono tumoral XML oficial.
- `annotation_official_non_tumor`: patch negativo muestreado fuera de poligonos tumorales oficiales.
- `negative_slide`: patch negativo desde una lamina oficialmente negativa.
- `slide_label_weak`: patch de una lamina positiva sin coordenada tumoral fuerte.
- `heuristic_qc`: negativo inferido por reglas QC/hard-negative mining.
- `operator_review`: ROI corregida desde el panel de revision docente/admin.

### 9.1 Generar patches y manifiesto

Desde `backend`, con laminas locales SLN-Breast:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.sample_hard_negative_patches `
  --slides-dir sample_sln_breast `
  --targets-csv sample_sln_breast\target.csv `
  --output-dir artifacts\histopathology\hard_negative_patches `
  --manifest artifacts\histopathology\manifests\hard_negative_manifest.csv `
  --negative-per-slide 48 `
  --positive-per-slide 48
```

Si aun no hay anotaciones tumorales por coordenadas, no conviene tratar patches
aleatorios de laminas positivas como verdad fuerte. Para pruebas de humo se puede
activar:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.sample_hard_negative_patches `
  --slides-dir sample_sln_breast `
  --targets-csv sample_sln_breast\target.csv `
  --output-dir artifacts\histopathology\hard_negative_patches_smoke `
  --manifest artifacts\histopathology\manifests\hard_negative_manifest_smoke.csv `
  --negative-per-slide 1 `
  --positive-per-slide 1 `
  --allow-weak-positive
```

Las filas generadas con esa opcion quedan marcadas como
`annotation_status=weak_positive_slide_label` para no confundir etiqueta de
lamina con etiqueta de patch.

Para positivos fuertes, entregar un CSV de anotaciones:

```csv
slide_id,label,x,y,width,height
HobI17-440719796933.svs,1,12000,8000,2048,2048
```

Y ejecutar:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.sample_hard_negative_patches `
  --slides-dir sample_sln_breast `
  --targets-csv sample_sln_breast\target.csv `
  --annotations-csv data\annotations\tumor_rois.csv `
  --output-dir artifacts\histopathology\hard_negative_patches `
  --manifest artifacts\histopathology\manifests\hard_negative_manifest.csv
```

Con CAMELYON17, los XML ASAP se convierten automaticamente a ese formato:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.convert_camelyon17_annotations `
  --annotations-dir data\camelyon17\annotations `
  --stages-csv data\camelyon17\stages.csv `
  --output-rois data\annotations\camelyon17_tumor_rois.csv `
  --output-targets data\annotations\camelyon17_targets.csv `
  --margin 256 `
  --min-size 512
```

El conversor genera:

- `camelyon17_tumor_rois.csv`: bounding boxes de poligonos `Tumor`.
- `camelyon17_targets.csv`: etiquetas binarias por lamina (`negative=0`, `itc/micro/macro=1`).

Tambien existe un generador directo de manifiesto oficial CAMELYON17. Este lee
los XML ASAP, muestrea coordenadas positivas dentro de poligonos tumorales,
muestrea negativos fuera de esos poligonos y marca cada fila con `label_source`.
Por defecto solo crea el CSV de coordenadas; si se agrega `--save-patches`,
tambien extrae los PNG.

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.build_camelyon17_official_manifest `
  --images-dir data\camelyon17\images `
  --annotations-dir data\camelyon17\annotations `
  --manifest artifacts\histopathology\manifests\camelyon17_official_manifest.csv `
  --summary artifacts\histopathology\reports\camelyon17_official_manifest_summary.json `
  --positive-per-slide 48 `
  --negative-per-positive-slide 48 `
  --negative-per-negative-slide 48 `
  --patch-size 256 `
  --seed 29
```

Para guardar patches fisicos:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.build_camelyon17_official_manifest `
  --images-dir data\camelyon17\images `
  --annotations-dir data\camelyon17\annotations `
  --manifest artifacts\histopathology\manifests\camelyon17_official_manifest.csv `
  --patch-output-dir artifacts\histopathology\camelyon17_official_patches `
  --save-patches
```

Luego se puede extraer una muestra de patches positivos reales:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.sample_hard_negative_patches `
  --slides-dir data\camelyon17\images `
  --targets-csv data\annotations\camelyon17_targets.csv `
  --annotations-csv data\annotations\camelyon17_tumor_rois.csv `
  --output-dir artifacts\histopathology\camelyon17_patches `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest.csv `
  --source camelyon17 `
  --negative-per-slide 0 `
  --positive-per-slide 48
```

Con la muestra local inicial usada para probar la tuberia:

```text
patient_017_node_0.tif -> negative
patient_017_node_1.tif -> itc
patient_017_node_2.tif -> macro
```

se puede correr un smoke end-to-end:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.sample_hard_negative_patches `
  --slides-dir data\camelyon17\images `
  --targets-csv data\annotations\camelyon17_targets.csv `
  --annotations-csv data\annotations\camelyon17_tumor_rois.csv `
  --output-dir artifacts\histopathology\camelyon17_patches_training_smoke `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_training_smoke.csv `
  --source camelyon17 `
  --negative-per-slide 24 `
  --positive-per-slide 24 `
  --seed 8
```

Ese smoke sirve para validar el pipeline, no para reportar metricas finales:
son muy pocas laminas y la validacion puede quedar con una sola clase.

Para WSI grandes en Windows, `openslide-bin` debe estar instalado junto a
`openslide-python`; de lo contrario, PIL intentara abrir el TIFF completo y el
muestreo sera lento o inviable.

### 9.2 Extraer embeddings CONCH

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.extract_manifest_embeddings `
  --manifest artifacts\histopathology\manifests\hard_negative_manifest.csv `
  --output-dir artifacts\histopathology\embeddings-hard-negative
```

Esto crea:

- `manifest_train_embeddings.pt`
- `manifest_val_embeddings.pt`
- `manifest_test_embeddings.pt`

Cada archivo incluye `x`, `y`, `records` y metadata del checkpoint CONCH.

Smoke CAMELYON17:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.extract_manifest_embeddings `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_training_smoke.csv `
  --output-dir artifacts\histopathology\embeddings-camelyon17-smoke `
  --batch-size 16 `
  --splits train,val
```

### 9.3 Entrenar cabeza nueva y evaluar hard negatives

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.train_manifest_head `
  --embeddings-dir artifacts\histopathology\embeddings-hard-negative `
  --output artifacts\histopathology\checkpoints\binary_head_hard_negative.pt `
  --report artifacts\histopathology\reports\hard_negative_metrics.json `
  --epochs 25 `
  --class-weights
```

El reporte incluye metricas globales y desglose de falsos positivos por
`hard_negative_type`. Ese desglose es clave para comparar contra el checkpoint
PCam inicial y demostrar si bajan los falsos positivos en estroma/fondo/adiposo.

Smoke CAMELYON17:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.train_manifest_head `
  --embeddings-dir artifacts\histopathology\embeddings-camelyon17-smoke `
  --output artifacts\histopathology\checkpoints\binary_head_camelyon17_smoke.pt `
  --report artifacts\histopathology\reports\camelyon17_smoke_metrics.json `
  --epochs 8 `
  --batch-size 16 `
  --class-weights
```

Stage 1 local con 10 laminas:

```text
5 positivas: patient_004_node_4, patient_016_node_1, patient_017_node_1,
             patient_017_node_2, patient_041_node_0
5 negativas: patient_004_node_0, patient_016_node_2, patient_017_node_0,
             patient_041_node_1, patient_060_node_1
```

Comandos usados:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.sample_hard_negative_patches `
  --slides-dir data\camelyon17\images `
  --targets-csv data\annotations\camelyon17_targets.csv `
  --annotations-csv data\annotations\camelyon17_tumor_rois.csv `
  --output-dir artifacts\histopathology\camelyon17_patches_stage1 `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_stage1.csv `
  --source camelyon17 `
  --negative-per-slide 30 `
  --positive-per-slide 30 `
  --max-attempts-per-patch 200 `
  --seed 29

.\.venv\Scripts\python.exe -m histopathology_offline.extract_manifest_embeddings `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_stage1.csv `
  --output-dir artifacts\histopathology\embeddings-camelyon17-stage1 `
  --batch-size 32 `
  --splits train,val,test

.\.venv\Scripts\python.exe -m histopathology_offline.train_manifest_head `
  --embeddings-dir artifacts\histopathology\embeddings-camelyon17-stage1 `
  --output artifacts\histopathology\checkpoints\binary_head_camelyon17_stage1.pt `
  --report artifacts\histopathology\reports\camelyon17_stage1_metrics.json `
  --epochs 25 `
  --batch-size 32 `
  --class-weights `
  --seed 29
```

Resultado Stage 1:

```text
Val:  accuracy=0.708, sensibilidad=0.433, especificidad=0.983, AUC=0.913
Test: accuracy=0.450, sensibilidad=0.100, especificidad=0.800, AUC=0.330
```

Lectura: la tuberia ya funciona con splits por lamina y ambas clases, pero el
test muestra baja generalizacion con solo 10 laminas. La siguiente mejora debe
sumar mas laminas positivas/negativas y aumentar hard negatives estromales,
porque en test el falso positivo fue mayor en `stroma`.

Stage 2 local con 15 laminas:

Se agregaron 5 laminas negativas adicionales:

```text
patient_043_node_1, patient_043_node_4, patient_050_node_2,
patient_053_node_4, patient_086_node_1
```

Se genero un manifiesto priorizando hard negatives:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.sample_hard_negative_patches `
  --slides-dir data\camelyon17\images `
  --targets-csv data\annotations\camelyon17_targets.csv `
  --annotations-csv data\annotations\camelyon17_tumor_rois.csv `
  --output-dir artifacts\histopathology\camelyon17_patches_stage2 `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_stage2.csv `
  --source camelyon17 `
  --negative-per-slide 30 `
  --positive-per-slide 30 `
  --max-attempts-per-patch 100 `
  --preferred-negative-types stroma,background_or_adipose,low_tissue,low_cellularity,stroma_low_cellularity `
  --allow-non-evaluable-negatives `
  --seed 29
```

Distribucion Stage 2:

```text
450 patches totales
train: 270, val: 120, test: 60
negativos: low_cellularity=111, background_or_adipose=184, stroma=5
```

Resultado Stage 2:

```text
Val:  accuracy=0.992, sensibilidad=1.000, especificidad=0.983, AUC=1.000
Test: accuracy=0.967, sensibilidad=1.000, especificidad=0.933, AUC=0.954
```

Lectura: Stage 2 corrige mucho mejor fondo/adiposo y baja celularidad. Sin
embargo, `stroma` sigue siendo el punto debil: en test hubo 1 patch estromal y
fue falso positivo. El checkpoint `binary_head_camelyon17_stage2.pt` es mejor
candidato que Stage 1, pero todavia conviene sumar mas stroma real antes de
presentarlo como modelo robusto final.

Stage 3: mineria adicional de stroma:

Se generaron patches negativos extra priorizando `stroma` y
`stroma_low_cellularity`, y luego se combinaron con el manifiesto Stage 2.

```text
stage3_stroma: 540 patches
train: 320, val: 160, test: 60
negativos agregados: stroma=85, stroma_low_cellularity=10

Val:  accuracy=0.887, sensibilidad=0.950, especificidad=0.850, AUC=0.971
Test: accuracy=0.817, sensibilidad=0.700, especificidad=0.933, AUC=0.951
```

Lectura: mejora la exposicion a stroma en entrenamiento/validacion, pero el test
todavia queda pobremente representado para stroma, asi que no alcanza para medir
robustez real.

Stage 3b: stroma tambien en test:

Se rehizo la mineria con el mismo `seed` de los splits base para que el test
incluyera mas stroma real.

```text
stage3b_stroma: 550 patches
train: positivos=60, negativos=280
val:   positivos=60, negativos=80
test:  positivos=30, negativos=40

Test: accuracy=0.714, sensibilidad=0.733, especificidad=0.700, AUC=0.819
Test hard negatives:
low_cellularity: false_positive=0/25
background_or_adipose: false_positive=1/4
stroma: false_positive=10/10
stroma_low_cellularity: false_positive=1/1
```

Lectura: esta es la medicion mas honesta del problema. Cuando el test contiene
stroma suficiente, el modelo confunde stroma con tumor con demasiada frecuencia.

Stage 4: mas stroma real desde center 3:

Se agregaron tres laminas negativas de center 3 en entrenamiento:

```text
patient_060_node_4, patient_064_node_1, patient_067_node_0
```

Luego se minaron 90 patches negativos adicionales de stroma y se entreno otra
cabeza.

```text
stage4_center3_stroma: 640 patches
train: positivos=60, negativos=370
val:   positivos=60, negativos=80
test:  positivos=30, negativos=40

Val:  accuracy=0.821, sensibilidad=0.650, especificidad=0.950, AUC=0.948
Test: accuracy=0.600, sensibilidad=0.267, especificidad=0.850, AUC=0.774
Test hard negatives:
stroma: false_positive=5/10
stroma_low_cellularity: false_positive=1/1
```

Lectura: agregar stroma de center 3 reduce falsos positivos estromales, pero el
modelo se vuelve demasiado conservador y pierde sensibilidad tumoral. Esta
corrida confirma que el stroma ya esta influyendo, pero no esta balanceado.

Stage 5: mezcla balanceada:

Se mezclo Stage 2 con un cupo limitado de stroma extra para recuperar
sensibilidad sin perder toda la especificidad.

```text
stage5_balanced_stroma: 510 patches
train: positivos=60, negativos=250
val:   positivos=60, negativos=70
test:  positivos=30, negativos=40

Val:  accuracy=0.908, sensibilidad=0.950, especificidad=0.871, AUC=0.959
Test: accuracy=0.700, sensibilidad=0.700, especificidad=0.700, AUC=0.779
Test hard negatives:
stroma: false_positive=10/10
stroma_low_cellularity: false_positive=1/1
```

Lectura final de esta tanda: Stage 2 sigue siendo el mejor candidato global por
metricas generales, pero no debe llamarse robusto frente a stroma. Stage 4
muestra que el problema se puede empujar en la direccion correcta, aunque a
costa de sensibilidad. Por eso el backend ahora incluye una compuerta de calidad
para ROI dominadas por stroma: si `stroma_fraction` supera
`HISTO_QC_MAX_DOMINANT_STROMA_FRACTION`, la ROI se marca como
`roi_no_evaluable` antes de forzar una clase metastasico/no_metastasico.

Calibracion QC sobre `stage3b_stroma` test:

```text
umbral stroma=0.55: bloquea 40/70 total, 8/30 positivos, 32/40 negativos, 2/10 stroma
umbral stroma=0.50: bloquea 42/70 total, 10/30 positivos, 32/40 negativos, 2/10 stroma
umbral stroma=0.45: bloquea 46/70 total, 12/30 positivos, 34/40 negativos, 4/10 stroma
umbral stroma=0.40: bloquea 48/70 total, 13/30 positivos, 35/40 negativos, 5/10 stroma
```

Lectura: bajar el umbral captura mas stroma, pero tambien bloquea mas positivos.
El default `0.55` queda como opcion conservadora. Para uso exploratorio mas
estricto se puede probar `0.45` o `0.40`, siempre reportando cuantas ROI
positivas se pierden.

Stage 6: cabeza de 3 clases:

Para evitar forzar todo a `metastasico` vs `no_metastasico`, se entreno una
cabeza lineal de 3 clases sobre los mismos embeddings CONCH:

```text
0: no_metastasico
1: metastasico
2: estroma
```

Comando base:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.train_manifest_head_3class `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_stage3b_stroma.csv `
  --embeddings-dir artifacts\histopathology\embeddings-camelyon17-stage3b-stroma `
  --output artifacts\histopathology\checkpoints\tri_head_camelyon17_stage3b_stroma.pt `
  --report artifacts\histopathology\reports\tri_head_camelyon17_stage3b_stroma_metrics.json `
  --epochs 40 `
  --class-weights `
  --device cpu
```

Resultado 3-class sobre `stage3b_stroma`:

```text
Test accuracy: 0.814
ROC-AUC tumor OVR: 0.913
no_metastasico: precision=1.000, recall=0.966, F1=0.982
metastasico:    precision=0.875, recall=0.700, F1=0.778
estroma:        precision=0.444, recall=0.727, F1=0.552

estroma->tumor: 3/11 = 27.3%
```

Comparacion directa:

```text
binario stage3b:  estroma->tumor 10/10, sensibilidad tumor 73%
3-class stage3b: estroma->tumor 3/11,  sensibilidad tumor 70%
3-class stage4:  estroma->tumor 0/11,  sensibilidad tumor 26.7%
3-class stage5:  estroma->tumor 1/11,  sensibilidad tumor 30%
```

Lectura: la cabeza 3-class `stage3b` es el mejor equilibrio actual. Reduce
fuertemente los falsos positivos de stroma sin destruir la sensibilidad tumoral.
Stage 4 y Stage 5 son mas conservadores frente a stroma, pero pierden demasiados
tumores al enviarlos a la clase `estroma`.

El entrenamiento 3-class tambien reporta un barrido de umbral para P(tumor). En
`stage3b_stroma` test:

```text
threshold 0.50: sensibilidad tumor=0.667, precision tumor=0.870, stroma->tumor=3/11
threshold 0.60: sensibilidad tumor=0.567, precision tumor=0.944, stroma->tumor=1/11
threshold 0.70: sensibilidad tumor=0.533, precision tumor=1.000, stroma->tumor=0/11
```

Si el objetivo es exploratorio y se quiere conservar sensibilidad, usar argmax
3-class o threshold `0.50`. Si el objetivo es minimizar falsos positivos
estromales, usar threshold `0.60` o `0.70`, aceptando menor sensibilidad.

Stage 6: dataset ampliado:

Se agregaron 6 laminas positivas anotadas y 5 negativas nuevas:

```text
positivas:
patient_009_node_1, patient_020_node_4, patient_042_node_3,
patient_062_node_2, patient_086_node_0, patient_099_node_4

negativas:
patient_020_node_0, patient_042_node_0, patient_062_node_4,
patient_086_node_2, patient_099_node_0
```

Luego se reconvirtieron los XML ASAP:

```text
11 XML positivos
95 ROIs tumorales anotadas
29 laminas locales totales
```

Se genero `camelyon17_manifest_stage6_expanded_stroma.csv` con positivos,
negativos y mineria adicional de stroma:

```text
total: 1630 patches
train: no_metastasico=477, metastasico=300, estroma=363
val:   no_metastasico=70,  metastasico=150, estroma=50
test:  no_metastasico=70,  metastasico=100, estroma=50
```

Checkpoint:

```text
artifacts/histopathology/checkpoints/tri_head_camelyon17_stage6_expanded_stroma.pt
```

Resultado Stage 6 3-class en test:

```text
accuracy: 0.836
macro F1: 0.827
ROC-AUC tumor OVR: 0.942

no_metastasico: precision=0.937, recall=0.843, F1=0.887
metastasico:    precision=0.843, recall=0.860, F1=0.851
estroma:        precision=0.709, recall=0.780, F1=0.743

estroma->tumor: 11/50 = 22%
```

Barrido de umbral P(tumor) en test:

```text
threshold 0.50: sensibilidad tumor=0.860, precision tumor=0.851, stroma->tumor=10/50
threshold 0.60: sensibilidad tumor=0.790, precision tumor=0.878, stroma->tumor=7/50
threshold 0.70: sensibilidad tumor=0.770, precision tumor=0.895, stroma->tumor=5/50
threshold 0.90: sensibilidad tumor=0.600, precision tumor=0.968, stroma->tumor=0/50
```

Lectura: Stage 6 mejora de forma clara el equilibrio practico frente al modelo
3-class anterior. Hay que vigilar que la validacion fue mas dura que test
(`ROC-AUC tumor OVR=0.715` en val), probablemente por diferencia de laminas y
composicion del split; aun asi, el test ampliado muestra mejor sensibilidad
tumoral y mejor separacion de estroma.

Stage 7 experimental: manifiesto oficial + stroma Stage 6:

Se genero un manifiesto oficial desde las 29 laminas CAMELYON17 locales y 11 XML
tumorales:

```text
camelyon17_official_manifest.csv
slides: 29
positive_rows: 528
negative_rows: 1392
label_source:
  annotation_official: 528
  annotation_official_non_tumor: 528
  negative_slide: 864
```

Luego se combino con `camelyon17_manifest_stage6_expanded_stroma.csv` para no
perder la clase `estroma`:

```text
camelyon17_manifest_official_plus_stage6_stroma.csv
total: 3550 patches
train: no_metastasico=1437, metastasico=588, estroma=363
val:   no_metastasico=310,  metastasico=294, estroma=50
test:  no_metastasico=262,  metastasico=196, estroma=50
```

Artefactos generados:

```text
artifacts/histopathology/camelyon17_official_patches/
artifacts/histopathology/embeddings-camelyon17-official/
artifacts/histopathology/embeddings-camelyon17-official-plus-stage6-stroma/
artifacts/histopathology/checkpoints/tri_head_camelyon17_official_plus_stage6_stroma.pt
artifacts/histopathology/checkpoints/tri_head_camelyon17_official_plus_stage6_stroma_weight050.pt
artifacts/histopathology/checkpoints/tri_head_camelyon17_official_plus_stage6_stroma_unweighted.pt
```

Comparacion test:

```text
modelo                                acc   macroF1  AUC tumor  recall tumor  precision tumor  stroma->tumor
stage6_actual                         .836  .827     .942       .860          .843             22%
official+stage6 weighted              .801  .736     .945       .724          .916             16%
official+stage6 weight_power=0.5      .789  .716     .939       .730          .877             26%
official+stage6 unweighted            .809  .727     .937       .755          .846             36%
balanced_v1 unweighted                .793  .709     .935       .750          .831             36%
balanced_v1 weighted                  .774  .698     .937       .724          .871             28%
balanced_v2 unweighted                .795  .693     .935       .847          .748             56%
stage6 MLP                            .686  .687     .816       .570          .781             28%
stage6 macro_f1 selected              .732  .728     .829       .710          .755             32%
```

Lectura: el nuevo dataset oficial mejora la trazabilidad y aumenta precision
tumoral en la variante con pesos completos, pero esa tanda no reemplazaba todavia
al checkpoint Stage 6: perdia sensibilidad tumoral y macro F1. La variante con
`class_weight_power=0.5` confirma que suavizar pesos no basta para recuperar el
equilibrio. Tambien se probaron manifiestos balanceados, seleccion de checkpoint
por metrica y una cabeza MLP pequena. Ninguna corrida supero el equilibrio
global de Stage 6 en esa tanda.

Stage 8: datos CAMELYON17 nuevos con `stages.csv` como verdad:

Se agregaron 6 laminas positivas con XML oficial y 6 laminas candidatas para
negativos/hard negatives:

```text
positivas con XML:
patient_010_node_4, patient_012_node_0, patient_044_node_4,
patient_052_node_1, patient_075_node_4, patient_096_node_0

candidatas negativas descargadas:
patient_010_node_0, patient_012_node_1, patient_044_node_0,
patient_052_node_0, patient_075_node_0, patient_096_node_1
```

Correccion importante: una lamina sin XML no equivale automaticamente a una
lamina sana. Se uso `data/camelyon17/stages.csv` como fuente de verdad para no
etiquetar como negativo un slide positivo sin anotacion local. Con esa revision,
`patient_010_node_0` y `patient_052_node_0` fueron excluidas de la mineria
negativa porque figuran como positivas en `stages.csv`.

Artefactos generados:

```text
data/annotations/camelyon17_tumor_rois_stage8.csv
data/annotations/camelyon17_targets_stage8.csv
artifacts/histopathology/manifests/camelyon17_official_manifest_stage8_corrected.csv
artifacts/histopathology/manifests/camelyon17_manifest_stage8_new_hard_negatives.csv
artifacts/histopathology/manifests/camelyon17_manifest_stage8_corrected_balanced_v1.csv
artifacts/histopathology/embeddings-camelyon17-stage8-corrected-balanced-v1/
artifacts/histopathology/checkpoints/tri_head_camelyon17_stage8_corrected_balanced_v1_weighted.pt
artifacts/histopathology/reports/tri_head_camelyon17_stage8_corrected_balanced_v1_weighted_metrics.json
```

Distribucion del manifiesto balanceado:

```text
train: no_metastasico=900, metastasico=924, estroma=374
val:   no_metastasico=310, metastasico=246, estroma=50
test:  no_metastasico=550, metastasico=196, estroma=50
```

Comparacion justa sobre el mismo test Stage 8 corregido:

```text
modelo                         acc   macroF1  AUC tumor  recall tumor  precision tumor  recall stroma  stroma->tumor
stage6_actual                  .854  .743     .967       .791          .847             .780           22%
stage8_corrected_weighted      .852  .744     .973       .806          .859             .820           18%
```

Lectura: Stage 8 corregido no es un salto gigante, pero si es una mejora real
en las senales que importaban para este problema: sube AUC, macro F1, recall
tumoral, precision tumoral, recall de estroma y baja la confusion
`stroma->tumor` de 22% a 18% en el mismo test. Por eso queda como checkpoint
activo recomendado para la siguiente validacion visual, aunque aun no debe
presentarse como modelo robusto final.

Calibracion educativa de baja sospecha:

El umbral principal `HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD=0.90` se mantiene
para llamar una ROI `metastasico` o `no_metastasico` de forma cerrada. Para no
ocultar zonas evaluables con baja probabilidad tumoral, el backend agrega una
salida intermedia:

```text
status: baja_sospecha_no_metastasica
class:  no_metastasico_probable
```

Condicion por defecto:

```text
P(no_metastasico) >= 0.55
P(metastasico) <= 0.25
ROI evaluable por QC
```

Esta salida no reemplaza una etiqueta firme ni es diagnostica; sirve para que
el visor y el heatmap diferencien zonas de baja sospecha de zonas realmente
inciertas o no evaluables.

Evaluacion automatica contra XML CAMELYON17:

Para no depender de criterio visual no experto, se agrego un evaluador offline
que compara predicciones del modelo contra las anotaciones ASAP XML oficiales de
CAMELYON17. El problema se transforma en una validacion geometrica:

```text
patch/ROI: x, y, width, height
XML oficial: poligonos tumorales
verdad automatica: el patch cae o no cae sobre tumor anotado
```

Comando base:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.evaluate_camelyon17_xml_predictions `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_stage8_corrected_balanced_v1.csv `
  --embeddings-dir artifacts\histopathology\embeddings-camelyon17-stage8-corrected-balanced-v1 `
  --checkpoint artifacts\histopathology\checkpoints\tri_head_camelyon17_stage8_corrected_balanced_v1_weighted.pt `
  --annotations-dir data\camelyon17\annotations `
  --targets-csv data\camelyon17\stages.csv `
  --output-dir artifacts\histopathology\evaluation\stage8_xml `
  --splits test `
  --truth-mode center `
  --tumor-threshold 0.90 `
  --device cuda
```

Archivos generados:

```text
all_predictions.csv
true_positive.csv
false_positive.csv
false_negative.csv
true_negative.csv
unknown.csv
summary.json
```

Interpretacion:

```text
XML tumor + modelo tumor            -> true_positive
XML tumor + modelo no tumor         -> false_negative
fuera de XML/slide negativo + tumor -> false_positive candidato
fuera de XML/slide negativo + no tumor -> true_negative
slide positivo sin XML local        -> unknown
```

Esta evaluacion permite minar errores para Stage 9 sin que el desarrollador
tenga que identificar tejido manualmente. Los falsos positivos candidatos se
pueden convertir en hard negatives; los falsos negativos dentro de XML se pueden
usar como positivos dificiles.

Resultado Stage 8 contra XML oficial fijo, usando solo `test`:

```text
checkpoint evaluado: tri_head_camelyon17_stage8_corrected_balanced_v1_weighted.pt
truth-mode: center
threshold: 0.90

true_positive:  78
false_positive: 23
false_negative: 42
true_negative:  653
precision tumor XML: 77.2%
recall tumor XML:    65.0%
```

Stage 9 experimental:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.evaluate_camelyon17_xml_predictions `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_stage8_corrected_balanced_v1.csv `
  --embeddings-dir artifacts\histopathology\embeddings-camelyon17-stage8-corrected-balanced-v1 `
  --checkpoint artifacts\histopathology\checkpoints\tri_head_camelyon17_stage8_corrected_balanced_v1_weighted.pt `
  --annotations-dir data\camelyon17\annotations `
  --targets-csv data\camelyon17\stages.csv `
  --output-dir artifacts\histopathology\evaluation\stage8_xml_train_val_center_t090 `
  --splits train,val `
  --truth-mode center `
  --tumor-threshold 0.90 `
  --device auto

.\.venv\Scripts\python.exe -m histopathology_offline.build_stage9_manifest_from_xml_errors `
  --evaluation-csv artifacts\histopathology\evaluation\stage8_xml_train_val_center_t090\all_predictions.csv `
  --output artifacts\histopathology\manifests\camelyon17_manifest_stage9_xml_error_candidates_trainval.csv `
  --summary artifacts\histopathology\reports\camelyon17_manifest_stage9_xml_error_candidates_trainval_summary.json `
  --include-outcomes false_positive,false_negative

.\.venv\Scripts\python.exe -m histopathology_offline.merge_patch_manifests `
  --base-manifest artifacts\histopathology\manifests\camelyon17_manifest_stage8_corrected_balanced_v1.csv `
  --extra-manifest artifacts\histopathology\manifests\camelyon17_manifest_stage9_xml_error_candidates_trainval.csv `
  --output artifacts\histopathology\manifests\camelyon17_manifest_stage9_xml_errors_merged_raw.csv

.\.venv\Scripts\python.exe -m histopathology_offline.reuse_manifest_embeddings `
  --source-embeddings-dir artifacts\histopathology\embeddings-camelyon17-stage8-corrected-balanced-v1 `
  --target-manifest artifacts\histopathology\manifests\camelyon17_manifest_stage9_xml_errors_merged_raw.csv `
  --output-dir artifacts\histopathology\embeddings-camelyon17-stage9-xml-errors-v1 `
  --source-splits train,val,test `
  --target-splits train,val,test
```

El manifiesto Stage 9 agrego 261 casos dificiles extraidos automaticamente desde
XML oficial, sin tocar el test fijo:

```text
false_positive -> 81 hard negatives
false_negative -> 180 positivos dificiles
train extra -> 223 filas
val extra   -> 38 filas
test extra  -> 0 filas
```

Comparacion XML en el mismo test fijo:

```text
modelo / umbral                  TP  FP  FN  TN  lectura
Stage 8 anterior / 0.90          78  23  42 653  baseline fijo
Stage 8 anterior / 0.80          89  35  31 641  mas sensible, mas FP
Stage 9 weighted / 0.90          56  13  64 663  menos FP, pierde demasiados tumores
Stage 9 unweighted / 0.80        80  26  40 650  cercano, no supera claramente Stage 8
Stage 9 weight050 / 0.80         77  21  43 655  menos FP, pero no mejora sensibilidad
```

Decision: no se reemplazo Stage 8 por Stage 9. La tuberia XML queda
implementada para seguir iterando, pero los resultados indican que repetir
errores del mismo manifest no alcanza para mejorar de forma robusta. La siguiente
mejora real debe incorporar mas laminas/patches nuevos con respaldo oficial y no
solo reponderar ejemplos ya vistos.

Stage 10: datos nuevos CAMELYON17 con XML oficial:

Se amplio el dataset local a 54 laminas `.tif` y 24 anotaciones XML. La mejora
no vino de etiquetar tejido manualmente, sino de agregar slides nuevos con
verdad oficial CAMELYON17 y volver a entrenar contra ese soporte.

```text
nuevas positivas con XML:
patient_015_node_1, patient_015_node_2, patient_017_node_4,
patient_021_node_3, patient_022_node_4, patient_024_node_1,
patient_034_node_3

nuevas negativas oficiales utiles:
patient_021_node_2, patient_022_node_3, patient_023_node_0,
patient_023_node_1, patient_024_node_3
```

Manifiesto oficial Stage 10:

```text
slides: 54
positive_rows: 1152
negative_rows: 2448

label_source:
negative_slide: 1296
annotation_official: 1152
annotation_official_non_tumor: 1152
```

Manifiesto balanceado Stage 10:

```text
train: no_metastasico=1200, metastasico=972, estroma=374
val:   no_metastasico=550,  metastasico=486, estroma=50
test:  no_metastasico=358,  metastasico=244, estroma=50
```

Checkpoint generado:

```text
artifacts/histopathology/checkpoints/tri_head_camelyon17_stage10_balanced_v1_weighted.pt
```

Comparacion honesta contra el mismo test XML fijo usado en Stage 8:

```text
modelo / umbral          TP  FP  FN  TN
Stage 8 / 0.90           78  23  42 653
Stage 10 weighted / 0.90 81  17  39 659
```

Lectura: Stage 10 mejora al checkpoint Stage 8 con el mismo umbral de 0.90:
detecta 3 tumores adicionales, reduce 6 falsos positivos, reduce 3 falsos
negativos y aumenta 6 verdaderos negativos. Por eso queda como checkpoint activo
en Docker/backend para la siguiente validacion visual. Sigue siendo un modulo
educativo no diagnostico.

Stage 11: muestreo oficial mas denso sin datos externos nuevos:

Se genero un manifiesto denso con las mismas 54 laminas y 24 XML locales, pero
duplicando la cantidad de patches oficiales por lamina. El objetivo fue probar
si mas coordenadas oficiales desde CAMELYON17 mejoraban el clasificador sin
depender de etiquetado manual no experto.

```text
Manifest oficial denso:
artifacts/histopathology/manifests/camelyon17_official_manifest_stage11_dense.csv
rows=7200

Manifest balanceado:
artifacts/histopathology/manifests/camelyon17_manifest_stage11_dense_balanced_v1.csv

train: no_metastasico=2400, metastasico=1932, estroma=374
val:   no_metastasico=550,  metastasico=438, estroma=50
test:  no_metastasico=646,  metastasico=484, estroma=50
```

Se extrajeron embeddings CONCH en:

```text
artifacts/histopathology/embeddings-camelyon17-stage11-dense-balanced-v1
```

Se entrenaron cuatro candidatos:

```text
tri_head_camelyon17_stage11_dense_balanced_v1_weighted.pt
tri_head_camelyon17_stage11_dense_balanced_v1_weight050.pt
tri_head_camelyon17_stage11_dense_balanced_v1_metric_selected.pt
tri_mlp_camelyon17_stage11_dense_balanced_v1_weight050.pt
```

Comparacion contra el mismo test XML fijo de Stage 8:

```text
modelo / umbral                    TP  FP  FN  TN
Stage 10 weighted / 0.90           81  17  39  659
Stage 11 weighted / 0.90           76  15  44  661
Stage 11 weight050 / 0.90          76  17  44  659
Stage 11 metric-selected / 0.90    89  35  31  641
Stage 11 MLP weight050 / 0.90      89  28  31  648
```

Decision: Stage 11 no se promueve a produccion. Las variantes mas sensibles
recuperan mas verdaderos positivos, pero tambien suben falsos positivos. La
variante weighted reduce falsos positivos, pero pierde sensibilidad tumoral.
El checkpoint activo sigue siendo Stage 10 porque mantiene mejor equilibrio en
el umbral educativo de 0.90. La lectura metodologica es importante: mas patches
de las mismas laminas ayudan a explorar el espacio, pero para una mejora
robusta hacen falta nuevas laminas, nuevos centros y negativos dificiles
oficiales, no solo mayor densidad de coordenadas ya disponibles.

Stage 12: hard negative mining oficial desde falsos positivos:

Se uso el checkpoint activo Stage 10 para buscar zonas sanas/no tumorales que el
modelo marcaba como metastasicas. La evaluacion se ejecuto solo sobre train/val
de Stage 11, dejando intacto el test fijo usado para comparar modelos.

```text
Evaluacion de minado:
checkpoint=tri_head_camelyon17_stage10_balanced_v1_weighted.pt
manifest=camelyon17_manifest_stage11_dense_balanced_v1.csv
splits=train,val
truth-mode=center
threshold=0.80

Resultados:
true_positive=1612
false_positive=105
false_negative=424
true_negative=3603
```

Los 105 falsos positivos se exportaron como hard negatives:

```text
artifacts/histopathology/manifests/camelyon17_manifest_stage12_stage10_false_positives_trainval.csv

train=93
val=12
outside_xml_tumor_polygon=97
negative_slide=8
```

Luego se fusionaron con Stage 10:

```text
artifacts/histopathology/manifests/camelyon17_manifest_stage12_hardfp_balanced_v1.csv

train: no_metastasico=1293, metastasico=972, estroma=374
val:   no_metastasico=562,  metastasico=486, estroma=50
test:  no_metastasico=358,  metastasico=244, estroma=50
```

Checkpoints candidatos:

```text
tri_head_camelyon17_stage12_hardfp_balanced_v1_weighted.pt
tri_head_camelyon17_stage12_hardfp_balanced_v1_weight050.pt
```

Comparacion contra el mismo test XML fijo:

```text
modelo / umbral                    TP  FP  FN  TN
Stage 10 weighted / 0.90           81  17  39  659
Stage 12 weighted / 0.90           69  14  51  662
Stage 12 weight050 / 0.90          55  12  65  664
Stage 12 weighted / 0.80           75  18  45  658
Stage 12 weight050 / 0.80          76  20  44  656
Stage 10 AND Stage 12 guard        81  17  39  659
```

Decision: Stage 12 no se activa. El minado redujo falsos positivos, pero hizo
el clasificador demasiado conservador y aumento falsos negativos tumorales. La
prueba como filtro secundario tampoco mejoro al checkpoint activo. Este
resultado sirve para justificar metodologicamente que no basta con minar pocos
errores de las mismas laminas; para mejorar sanos sin perder tumor se requiere
mas diversidad: nuevas laminas negativas, mas regiones fuera de tumor y nuevos
pacientes/centros con XML oficial.

Herramientas agregadas para iterar:

```powershell
.\.venv\Scripts\python.exe -m histopathology_offline.balance_patch_manifest `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_official_plus_stage6_stroma.csv `
  --output artifacts\histopathology\manifests\camelyon17_manifest_official_plus_stage6_balanced_v1.csv `
  --cap train:no_metastasico=800 `
  --seed 31

.\.venv\Scripts\python.exe -m histopathology_offline.train_manifest_head_3class `
  --manifest artifacts\histopathology\manifests\camelyon17_manifest_stage6_expanded_stroma.csv `
  --embeddings-dir artifacts\histopathology\embeddings-camelyon17-stage6-expanded-stroma `
  --head-type linear `
  --selection-metric macro_f1
```

El entrenador soporta ahora:

- `--class-weight-power`: suaviza pesos de clase.
- `--head-type mlp`: prueba una cabeza no lineal pequena.
- `--selection-metric`: permite seleccionar el mejor epoch por `val_loss`,
  `macro_f1`, `tumor_f1` o `tumor_recall_minus_stroma_fp`.

Los patches, embeddings, checkpoints y reportes quedan bajo `backend/artifacts`
o `backend/data`, ambos ignorados por Git.

## 10. Integracion WSI local y validacion visual

Para evitar subir laminas CAMELYON17 de varios GB por HTTP, se agrego un flujo
de importacion local. La UI lista las laminas ya descargadas en el servidor y el
backend registra la ruta existente sin copiar el archivo:

```text
backend/data/camelyon17/images/*.tif
-> GET /api/medical-images/local/camelyon17
-> POST /api/medical-images/import-local/camelyon17
-> MedicalImage con file_size BIGINT
-> DZI dinamico con OpenSlide
-> OpenSeadragon
```

Esto resolvio dos problemas practicos:

- no se reenvian archivos de 3 a 4 GB desde el navegador;
- `file_size` ahora usa `BIGINT`, porque PostgreSQL `INTEGER` no alcanza para
  laminas como `patient_017_node_2.tif` (`3.86 GB`).

El backend prepara un manifiesto DZI para WSI grandes y genera tiles dinamicos
cuando el visor los solicita. Por eso la imagen puede verse borrosa al inicio:
OpenSeadragon primero muestra tiles de baja resolucion y luego reemplaza por
tiles mas nitidos segun el zoom y la zona visible.

La lamina `patient_017_node_2.tif` quedo registrada localmente y lista para
validacion en el visor:

```text
image_id: 10
slide: patient_017_node_2.tif
tamano: 3.86 GB
dimensiones DZI: 94968 x 210579
```

Para validar una ROI positiva contra anotacion oficial CAMELYON17 se usaron las
coordenadas extraidas desde `patient_017_node_2.xml`. Una ROI recomendada:

```text
slide: patient_017_node_2.tif
centro tumoral: x=53549, y=151128
ROI sugerida: 512x512 o 1024x1024
```

En la prueba de visor, una ROI dentro de esa zona anotada oficialmente como
tumor fue clasificada como:

```text
clase: metastasico
confianza: 99.8%
P(metastasico): 99.8%
P(no_metastasico): 0.2%
P(estroma): 0.0%
```

Lectura: el modulo funciona para una prueba positiva controlada dentro de una
region tumoral anotada. No debe interpretarse como validacion final del modelo:
faltan pruebas sistematicas en regiones sanas, stroma/fibrosis, laminas
negativas y coordenadas tumorales de otras laminas.

## 11. Primer heatmap sobre ROI

Como paso intermedio antes de analizar una lamina completa, se agrego un escaneo
acotado sobre ROI. El objetivo es dividir una region amplia en tiles, inferir
cada tile y mostrar un mapa visual de sospecha en OpenSeadragon.

Endpoint:

```text
POST /api/histopathology/scan-roi
```

Payload:

```json
{
  "image_id": 10,
  "roi": { "x": 53293, "y": 150872, "width": 512, "height": 512 },
  "tile_size": 512,
  "stride": 512,
  "max_tiles": 64
}
```

Flujo:

```text
ROI amplia
-> grid de tiles
-> extraccion con OpenSlide
-> QC por tile
-> CONCH + cabeza 3-class
-> tumor_score = P(metastasico)
-> resumen con mejor tile
-> persistencia JSON por trace_id e image_id
-> overlay en el visor
```

Prueba controlada sobre `patient_017_node_2.tif`, dentro del XML tumoral oficial:

```text
tile: x=53293, y=150872, width=512, height=512
status: clasificado
class: metastasico
P(metastasico): 99.8%
P(no_metastasico): 0.2%
P(estroma): 0.0%
QC tejido: 96.4%
QC nucleos: 32.3%
```

Persistencia:

```text
artifacts/histopathology/heatmaps/traces/{trace_id}.json
artifacts/histopathology/heatmaps/images/{image_id}/latest.json
artifacts/histopathology/heatmaps/images/{image_id}/history.json
```

Endpoints de consulta:

```text
POST /api/histopathology/heatmaps/jobs
GET /api/histopathology/heatmaps/jobs/{job_id}
GET /api/histopathology/heatmaps/image/{image_id}/latest
GET /api/histopathology/heatmaps/image/{image_id}/history?limit=20
GET /api/histopathology/heatmaps/{trace_id}
PATCH /api/histopathology/heatmaps/{trace_id}/educational
```

El visor intenta recuperar automaticamente el ultimo heatmap guardado al abrir
una imagen y permite ocultarlo sin borrar el artefacto. Para ejecucion normal
desde la UI se usa un job asincronico en memoria: el frontend consulta progreso
hasta recibir `completed`, y luego pinta el resultado persistido.

La pantalla de configuracion incorpora un panel docente/admin para preparar
heatmaps acotados sobre imagenes con DZI. Desde ahi se elige la lamina, se
definen coordenadas ROI, `tile_size`, `max_tiles`, nombre educativo, tipo y nota
docente, se lanza el mismo job asincronico y se revisa el resultado persistido
con trace, cache, tiles positivos y mejor tile. El panel tambien consulta un
historial por imagen para recuperar mapas anteriores mediante `trace_id` y
actualizar su metadata educativa sin recalcular el mapa.

Tipos educativos soportados por UI:

```text
referencia
tumoral
sano
mixto
estroma
falso_positivo
discusion
```

El visor OpenSeadragon muestra una lista de "Mapas preparados" con nombre,
tipo, nota y score maximo. El estudiante puede cargar un mapa docente por
nombre sin conocer coordenadas ni `trace_id`; esto permite preparar varias
regiones docentes, por ejemplo tumor, tejido sano y zona mixta, antes de que
entren estudiantes, sin convertir todavia el flujo en heatmap de lamina
completa.

Control de carga:

```text
HISTO_MAX_CONCURRENT_HEATMAP_JOBS=1
HISTO_STUDENT_MAX_HEATMAP_TILES=16
HISTO_PRIVILEGED_MAX_HEATMAP_TILES=256
HISTO_STUDENT_HEATMAP_JOBS_PER_WINDOW=3
HISTO_PRIVILEGED_HEATMAP_JOBS_PER_WINDOW=20
HISTO_HEATMAP_RATE_LIMIT_WINDOW_SECONDS=60
```

Por defecto solo corre un heatmap pesado a la vez. Los jobs adicionales quedan
en cola en memoria hasta que exista un cupo. Ademas, el frontend envia
`Authorization: Bearer <JWT>` junto con `X-Asofamech-Client-Id`. El backend toma
el rol real desde el token y usa ese rol para aplicar limites:

- estudiante: hasta 16 tiles por heatmap y 3 solicitudes por ventana de 60 s;
- profesor/administrador: hasta 256 tiles por heatmap y 20 solicitudes por
  ventana de 60 s.

Estos controles reducen la probabilidad de saturar GPU/CPU si varios
estudiantes usan el visor al mismo tiempo. El header de rol del prototipo ya no
se considera fuente de verdad cuando hay JWT; los claims del token y el usuario
de base de datos mandan sobre el cliente.

Cache por tile:

```text
artifacts/histopathology/heatmaps/tile_cache/{cache_key}.json
```

La clave usa `image_id`, coordenadas de tile, tamano del tile y firma del modelo
actual. Si el mismo tile ya fue analizado con el mismo checkpoint/umbral, el
backend reutiliza probabilidades, QC y score sin volver a pasar por CONCH.

Limitacion actual: este heatmap sigue acotado a una ROI y los jobs viven en
memoria del proceso backend. Para lamina completa falta persistir jobs en base
de datos/cola real y eventualmente cachear embeddings, no solo scores por tile.

## 12. Mineria automatica de negativos dificiles

Para no depender de etiquetas manuales de un usuario no patologo, se agrego una
etapa offline que usa CAMELYON17 con XML oficial:

```text
histopathology_offline/mine_camelyon17_false_positive_patches.py
```

La herramienta muestrea tejido fuera de los poligonos tumorales oficiales,
aplica QC, ejecuta el checkpoint activo y conserva como hard negatives los
patches que el modelo considera sospechosos o metastasicos. Estos casos
representan ejemplos como tejido linfoide denso o estroma que visualmente no
corresponden a metastasis evidente, pero que el modelo puede confundir.

Primera corrida Stage 13:

```text
laminas XML=6
hard negatives nuevos=36
outside_xml_tumor_polygon=36
lymphoid_or_mixed_negative=35
stroma=1
```

Artefactos principales:

```text
artifacts/histopathology/manifests/camelyon17_manifest_stage13_mined_hard_negatives_v1.csv
artifacts/histopathology/reports/camelyon17_stage13_mined_summary_v1.json
artifacts/histopathology/reports/camelyon17_stage13_mined_candidates_v1.csv
```

Con esos parches se entrenaron candidatos Stage 13, pero no se promovieron: en
el test XML aumentaron la sensibilidad tumoral a costa de mas falsos positivos.
Por tanto, el checkpoint activo sigue siendo Stage 10. La mineria queda como
flujo reproducible para seguir acumulando negativos dificiles sin inventar
verdad clinica manual.

## 13. Limites metodologicos

El clasificador actual cubre una tarea estrecha:

```text
patch compatible con PCam/CAMELYON/SLN-Breast -> metastasico vs no_metastasico
```

No cubre:

- diagnostico clinico;
- clasificacion de cancer de mama primario;
- otros organos;
- subtipos tumorales;
- grado histologico;
- segmentacion exhaustiva de tumor;
- clasificacion completa de una WSI sin muestrear multiples ROI.

La salida debe presentarse siempre como apoyo educativo y exploratorio.
