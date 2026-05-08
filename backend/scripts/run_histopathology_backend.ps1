$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $PSScriptRoot
Set-Location $BackendDir

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql://app_user:app_pass@localhost:5432/app_db"
}
$env:HISTO_CLASSIFIER_CHECKPOINT = Join-Path $BackendDir "artifacts\histopathology-pcam-cuda\checkpoints\binary_head_pcam.pt"
$env:HISTO_CONCH_CHECKPOINT_REF = "hf_hub:MahmoodLab/conch"
$env:HISTO_AUDIT_LOG_PATH = "artifacts/histopathology/audit_log.jsonl"
if (-not $env:HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD) {
    $env:HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD = "0.90"
}
if (-not $env:HISTO_SAVE_DEBUG_PATCHES) {
    $env:HISTO_SAVE_DEBUG_PATCHES = "true"
}
if (-not $env:HISTO_DEBUG_PATCH_DIR) {
    $env:HISTO_DEBUG_PATCH_DIR = "artifacts/histopathology/debug_patches"
}
if (-not $env:HISTO_QC_MAX_WHITE_FRACTION) {
    $env:HISTO_QC_MAX_WHITE_FRACTION = "0.45"
}
if (-not $env:HISTO_QC_MIN_TISSUE_FRACTION) {
    $env:HISTO_QC_MIN_TISSUE_FRACTION = "0.40"
}
if (-not $env:HISTO_QC_MIN_NUCLEAR_FRACTION) {
    $env:HISTO_QC_MIN_NUCLEAR_FRACTION = "0.035"
}
if (-not $env:HISTO_QC_MAX_STROMA_FRACTION_WHEN_LOW_NUCLEAR) {
    $env:HISTO_QC_MAX_STROMA_FRACTION_WHEN_LOW_NUCLEAR = "0.65"
}
if (-not $env:HISTO_QC_LOW_NUCLEAR_FOR_STROMA_FRACTION) {
    $env:HISTO_QC_LOW_NUCLEAR_FOR_STROMA_FRACTION = "0.12"
}

$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"
$Port = if ($env:HISTO_BACKEND_PORT) { $env:HISTO_BACKEND_PORT } else { "8001" }
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
