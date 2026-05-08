$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $PSScriptRoot
Set-Location $BackendDir

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql://app_user:app_pass@localhost:5432/app_db"
}
$env:HISTO_CLASSIFIER_CHECKPOINT = Join-Path $BackendDir "artifacts\histopathology-pcam-cuda\checkpoints\binary_head_pcam.pt"
$env:HISTO_CONCH_CHECKPOINT_REF = "hf_hub:MahmoodLab/conch"
$env:HISTO_AUDIT_LOG_PATH = "artifacts/histopathology/audit_log.jsonl"

$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"
$Port = if ($env:HISTO_BACKEND_PORT) { $env:HISTO_BACKEND_PORT } else { "8001" }
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
