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
$env:HISTO_CLASSIFIER_CHECKPOINT = "C:\ruta\absoluta\Asofamech\backend\artifacts\histopathology\checkpoints\binary_head_pcam.pt"
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

- `HISTO_CLASSIFIER_CHECKPOINT=/app/artifacts/histopathology-pcam-cuda/checkpoints/binary_head_pcam.pt`
- `HISTO_CONCH_CHECKPOINT_REF=hf_hub:MahmoodLab/conch`
- `HISTO_AUDIT_LOG_PATH=/app/artifacts/histopathology/audit_log.jsonl`
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
- ROI 1 y ROI 2 usadas
- prediccion y probabilidades
- metadata del patch extraido
- dimensiones de la lamina
- advertencia educativa

Ademas, el backend escribe eventos JSONL en `HISTO_AUDIT_LOG_PATH`.

## 7. Pruebas con SLN-Breast

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
tamaño y condiciones de distribucion.

## 8. Limites metodologicos

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
