# prepare_histopathology_model.ps1
# Descarga/cachea CONCH en el volumen Docker HuggingFace usando un token temporal.
# Uso:
#   .\scripts\prepare_histopathology_model.ps1
#   .\scripts\prepare_histopathology_model.ps1 -Token "hf_..."

param(
    [string]$Token,

    [string]$StatusUrl = "http://localhost:8001/api/histopathology/status",

    [switch]$SkipBackendRecreate
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectDir

function Write-Step($n, $total, $msg) {
    Write-Host "`n[$n/$total] $msg" -ForegroundColor Cyan
}
function Write-OK($msg)    { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  AVISO: $msg" -ForegroundColor Yellow }
function Write-Fail($msg)  { Write-Host "  ERROR: $msg" -ForegroundColor Red }

function Convert-SecureStringToPlainText($SecureString) {
    if ($null -eq $SecureString) { return "" }
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Wait-Url($Url, $Label, $Retries = 45) {
    for ($i = 1; $i -le $Retries; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-OK "$Label disponible en $Url"
                return $true
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }

    Write-Warn "$Label aun no responde en $Url."
    return $false
}

function Test-HistopathologyStatus($Url) {
    try {
        return Invoke-RestMethod -Uri $Url -TimeoutSec 900
    } catch {
        throw "No se pudo consultar $Url. Detalle: $($_.Exception.Message)"
    }
}

$preparePython = @'
import os
import shutil
from pathlib import Path

target = Path("/root/.cache/huggingface/conch/pytorch_model.bin")
snapshots = Path("/root/.cache/huggingface/hub/models--MahmoodLab--conch/snapshots")
source = None

if snapshots.exists():
    candidates = sorted(
        snapshots.glob("*/pytorch_model.bin"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        source = candidates[0]

if source is None:
    from huggingface_hub import hf_hub_download

    token = os.getenv("HISTO_HF_TOKEN") or None
    source = Path(hf_hub_download("MahmoodLab/conch", "pytorch_model.bin", token=token))

target.parent.mkdir(parents=True, exist_ok=True)
if target.exists() or target.is_symlink():
    target.unlink()

try:
    target.symlink_to(source)
except Exception:
    shutil.copy2(source, target)

os.environ["HISTO_CONCH_CHECKPOINT_REF"] = str(target)

from app.histopathology.ml.inference_service import get_inference_service

svc = get_inference_service()
print(
    "CONCH cache OK | "
    f"checkpoint={target} | "
    f"feature_dim={svc.feature_dim} | "
    f"device={svc.device} | "
    f"classes={svc.num_classes}"
)
'@

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  ASOFAMECH - Preparacion modelo histopatologico" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

Write-Step 1 5 "Verificando Docker y checkpoint local"
try {
    docker info | Out-Null
    Write-OK "Docker en ejecucion"
} catch {
    Write-Fail "Docker no esta corriendo. Abre Docker Desktop y vuelve a ejecutar."
    exit 1
}

$checkpointPath = Join-Path $projectDir "backend\artifacts\histopathology\checkpoints\tri_head_camelyon17_stage15_heavy_neg_v1.pt"
if (Test-Path -LiteralPath $checkpointPath) {
    Write-OK "Cabeza clasificadora encontrada: $checkpointPath"
} else {
    Write-Warn "No se encontro la cabeza clasificadora esperada: $checkpointPath"
    Write-Warn "Restaura primero el backup o revisa HISTO_CLASSIFIER_CHECKPOINT en docker-compose.yml."
}

Write-Step 2 5 "Leyendo token HuggingFace temporal"
if (-not $Token -and $env:HISTO_HF_TOKEN) {
    $Token = $env:HISTO_HF_TOKEN
    Write-OK "Usando HISTO_HF_TOKEN de la sesion actual"
}

if (-not $Token) {
    Write-Host "  Pega tu token HuggingFace con acceso a MahmoodLab/conch." -ForegroundColor Yellow
    Write-Host "  El token no se guardara en archivos del proyecto." -ForegroundColor Yellow
    Write-Host "  Si el modelo ya esta cacheado, puedes presionar Enter e intentar sin token." -ForegroundColor Yellow
    $secureToken = Read-Host "  Token HF" -AsSecureString
    $Token = Convert-SecureStringToPlainText $secureToken
}

if ($Token) {
    $env:HISTO_HF_TOKEN = $Token
    Write-OK "Token cargado solo para esta ejecucion"
} else {
    Write-Warn "Continuando sin token. Esto solo funcionara si CONCH ya esta cacheado."
}

try {
    Write-Step 3 5 "Descargando/cacheando CONCH con contenedor temporal"
    if ($SkipBackendRecreate) {
        Write-Warn "No se recreara backend por -SkipBackendRecreate; se usara el backend actualmente activo."
    } else {
        Write-Host "  Se usara un contenedor temporal. El token no queda guardado en el repositorio." -ForegroundColor Yellow
        docker compose run --rm --no-deps --entrypoint python -e HISTO_HF_TOKEN backend -c $preparePython | Out-Host
    }

    Write-Step 4 5 "Levantando backend sin token y validando estado"
    if (-not $SkipBackendRecreate) {
        if (Test-Path Env:\HISTO_HF_TOKEN) {
            Remove-Item Env:\HISTO_HF_TOKEN -ErrorAction SilentlyContinue
        }
        docker compose up -d db | Out-Null
        docker compose up -d --force-recreate backend | Out-Null
    }
    Wait-Url "http://localhost:8001/health" "Backend" 60 | Out-Null
    $status = Test-HistopathologyStatus $StatusUrl

    if ($status.model_ready -ne $true) {
        Write-Fail "El modelo histopatologico no quedo listo."
        if ($status.reason) {
            Write-Host "  Motivo: $($status.reason)" -ForegroundColor Red
        }
        Write-Warn "Si el cache quedo descargado pero CONCH exige token al iniciar, ejecuta Docker Compose desde una sesion con HISTO_HF_TOKEN y limita el acceso al equipo."
        exit 1
    }

    Write-OK "Modelo listo"
    Write-Host "  Backbone  : $($status.backbone)" -ForegroundColor White
    Write-Host "  Checkpoint: $($status.classifier_checkpoint)" -ForegroundColor White
    Write-Host "  Version   : $($status.model_version)" -ForegroundColor White
    Write-Host "  Clases    : $($status.num_classes)" -ForegroundColor White
    Write-Host "  Dispositivo: $($status.device)" -ForegroundColor White

    Write-Step 5 5 "Quitando token temporal de la sesion"
    if (Test-Path Env:\HISTO_HF_TOKEN) {
        Remove-Item Env:\HISTO_HF_TOKEN -ErrorAction SilentlyContinue
    }
    Write-OK "Token eliminado de la sesion PowerShell actual"

    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "  MODELO HISTOPATOLOGICO PREPARADO" -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Los estudiantes pueden usar la plataforma sin recibir el token." -ForegroundColor White
    Write-Host "Si Docker se apaga, inicia normalmente con:" -ForegroundColor Yellow
    Write-Host "  docker compose up -d"
    Write-Host ""
} finally {
    if (Test-Path Env:\HISTO_HF_TOKEN) {
        Remove-Item Env:\HISTO_HF_TOKEN -ErrorAction SilentlyContinue
    }
}
