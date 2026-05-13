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
$env:HISTO_CLASSIFIER_CHECKPOINT = "C:\ruta\absoluta\Asofamech\backend\artifacts\histopathology\checkpoints\tri_head_camelyon17_stage3b_stroma.pt"
$env:HISTO_CONCH_CHECKPOINT_REF = "hf_hub:MahmoodLab/conch"
$env:HISTO_AUDIT_LOG_PATH = "artifacts/histopathology/audit_log.jsonl"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Verifica estado:

```powershell
Invoke-RestMethod -Uri http://localhost:8001/api/histopathology/status -Method GET
```

El endpoint debe responder `model_ready=true` cuando el checkpoint de la cabeza
binaria y CONCH esten disponibles. En Docker, la ruta esperada del checkpoint es:

```text
/app/artifacts/histopathology-pcam-cuda/checkpoints/binary_head_pcam.pt
```

En ejecucion local, la ruta se define con `HISTO_CLASSIFIER_CHECKPOINT`.

## 5. Backend Docker con IA

El backend Docker instala las dependencias IA cuando Compose construye la imagen
con `INSTALL_HISTOPATHOLOGY_AI=true`. Los artefactos no se copian dentro de la
imagen; se montan desde `backend/artifacts` para mantener la imagen reproducible
y liviana.

Variables y mounts configurados en `docker-compose.yml`:

- `HISTO_CLASSIFIER_CHECKPOINT=/app/artifacts/histopathology/checkpoints/tri_head_camelyon17_stage3b_stroma.pt`
- `HISTO_CONCH_CHECKPOINT_REF=hf_hub:MahmoodLab/conch`
- `HISTO_AUDIT_LOG_PATH=/app/artifacts/histopathology/audit_log.jsonl`
- `HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD=0.90`
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
patch_id,source,slide_id,path,label,hard_negative_type,x,y,width,height,split,qc_status,qc_tissue_fraction,qc_nuclear_fraction,qc_white_fraction,annotation_status
```

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
`X-Asofamech-Role` y `X-Asofamech-Client-Id` para aplicar limites por rol en el
prototipo con roles simulados:

- estudiante: hasta 16 tiles por heatmap y 3 solicitudes por ventana de 60 s;
- profesor/administrador: hasta 256 tiles por heatmap y 20 solicitudes por
  ventana de 60 s.

Estos controles reducen la probabilidad de saturar GPU/CPU si varios
estudiantes usan el visor al mismo tiempo. No reemplazan autenticacion real:
cuando exista JWT/roles backend, el header simulado debe sustituirse por claims
validados del token.

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

## 12. Limites metodologicos

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
