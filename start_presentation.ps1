# start_presentation.ps1
# Orquestador para levantar Asofamech en el equipo de presentacion.
# Ejecutar desde la raiz del proyecto: .\start_presentation.ps1 -BackupPath "E:\asofamech_migration"

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"
$ProjectName = "asofamech"

function Write-Step($n, $total, $msg) {
    Write-Host "`n[$n/$total] $msg" -ForegroundColor Cyan
}
function Write-OK($msg)    { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  AVISO: $msg" -ForegroundColor Yellow }
function Write-Fail($msg)  { Write-Host "  ERROR: $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  ASOFAMECH - Setup presentacion" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── PASO 1: Verificar prerequisitos ─────────────────────────────────────────
Write-Step 1 7 "Verificando prerequisitos..."

# Docker
try {
    docker info | Out-Null
    Write-OK "Docker en ejecucion"
} catch {
    Write-Fail "Docker no esta corriendo. Abre Docker Desktop y vuelve a ejecutar."
    exit 1
}

# NVIDIA GPU
$gpuOk = $false
try {
    $nvOut = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>$null
    if ($nvOut) {
        Write-OK "GPU detectada: $nvOut"
        $gpuOk = $true
    }
} catch {}
if (-not $gpuOk) {
    Write-Warn "No se detecto GPU NVIDIA. El analisis histopatologico y Ollama correran en CPU (mas lento)."
}

# Node.js
try {
    $nodeVersion = node --version 2>$null
    Write-OK "Node.js $nodeVersion"
} catch {
    Write-Warn "Node.js no encontrado. Instala Node.js 18+ para el frontend."
}

# Backup path
if (-not (Test-Path $BackupPath)) {
    Write-Fail "Ruta de backup no encontrada: $BackupPath"
    exit 1
}
Write-OK "Backup encontrado en $BackupPath"

# ── PASO 2: Importar base de datos ───────────────────────────────────────────
Write-Step 2 7 "Importando base de datos (Postgres)..."
$dbBackup = "$BackupPath\volumes\db_backup.tar.gz"
if (Test-Path $dbBackup) {
    # Crear el volumen si no existe
    docker volume create "${ProjectName}_db_data" | Out-Null
    docker run --rm `
        -v "${ProjectName}_db_data:/data" `
        -v "${BackupPath}\volumes:/backup" `
        alpine sh -c "cd /data && tar xzf /backup/db_backup.tar.gz"
    Write-OK "Base de datos restaurada"
} else {
    Write-Warn "db_backup.tar.gz no encontrado. Se creara una base de datos vacia al iniciar."
}

# ── PASO 3: Importar modelo CONCH (HuggingFace) ──────────────────────────────
Write-Step 3 7 "Importando modelo CONCH..."
$hfBackup = "$BackupPath\volumes\hf_backup.tar.gz"
if (Test-Path $hfBackup) {
    docker volume create "${ProjectName}_huggingface_cache" | Out-Null
    docker run --rm `
        -v "${ProjectName}_huggingface_cache:/data" `
        -v "${BackupPath}\volumes:/backup" `
        alpine sh -c "cd /data && tar xzf /backup/hf_backup.tar.gz"
    Write-OK "Modelo CONCH restaurado"
} else {
    Write-Warn "hf_backup.tar.gz no encontrado. Se descargara al primer uso (requiere HF_TOKEN)."
}

# ── PASO 4: Importar modelos Ollama ──────────────────────────────────────────
Write-Step 4 7 "Importando modelos Ollama (llama3:8b)..."
$ollamaBackup = "$BackupPath\volumes\ollama_backup.tar.gz"
if (Test-Path $ollamaBackup) {
    Write-Host "  Descomprimiendo ~5 GB, puede tardar varios minutos..." -ForegroundColor Yellow
    docker volume create "${ProjectName}_ollama_data" | Out-Null
    docker run --rm `
        -v "${ProjectName}_ollama_data:/data" `
        -v "${BackupPath}\volumes:/backup" `
        alpine sh -c "cd /data && tar xzf /backup/ollama_backup.tar.gz"
    Write-OK "Modelos Ollama restaurados"
} else {
    Write-Warn "ollama_backup.tar.gz no encontrado. Se descargara automaticamente al iniciar (requiere internet)."
}

# ── PASO 5: Restaurar imagenes CAMELYON17 importadas ─────────────────────────
Write-Step 5 7 "Restaurando imagenes CAMELYON17 importadas..."
$camelyon17Src = "$BackupPath\camelyon17_imgs"
$camelyon17Dst = "$projectDir\backend\data\camelyon17\images"
if (Test-Path $camelyon17Src) {
    $tifFiles = Get-ChildItem $camelyon17Src -File
    if ($tifFiles.Count -gt 0) {
        New-Item -ItemType Directory -Force -Path $camelyon17Dst | Out-Null
        Copy-Item -Path "$camelyon17Src\*" -Destination $camelyon17Dst -Force
        Write-OK "$($tifFiles.Count) TIF(s) restaurados en backend\data\camelyon17\images\"
    } else {
        Write-Warn "camelyon17_imgs\ vacio."
    }
} else {
    Write-Warn "No se encontro carpeta camelyon17_imgs\ en el backup."
}

# ── PASO 6: Restaurar artifacts y uploads ─────────────────────────────────────
Write-Step 6 7 "Restaurando artifacts y uploads..."

$artifactsSrc = "$BackupPath\artifacts"
$artifactsDst = "$projectDir\backend\artifacts"
if (Test-Path $artifactsSrc) {
    New-Item -ItemType Directory -Force -Path $artifactsDst | Out-Null
    Copy-Item -Path "$artifactsSrc\*" -Destination $artifactsDst -Recurse -Force
    Write-OK "artifacts\ restaurado (checkpoints del modelo incluidos)"
} else {
    Write-Warn "artifacts\ no encontrado en el backup."
}

$uploadsSrc = "$BackupPath\uploads"
$uploadsDst = "$projectDir\backend\uploads"
if (Test-Path $uploadsSrc) {
    New-Item -ItemType Directory -Force -Path $uploadsDst | Out-Null
    Copy-Item -Path "$uploadsSrc\*" -Destination $uploadsDst -Recurse -Force -ErrorAction SilentlyContinue
    Write-OK "uploads\ restaurado (laminas SVS/PNG incluidas)"
} else {
    New-Item -ItemType Directory -Force -Path $uploadsDst | Out-Null
    Write-Warn "uploads\ no encontrado en el backup. Carpeta creada vacia."
}

# ── PASO 6: Construir/cargar imagen y levantar Docker Compose ─────────────────
Write-Step 6 7 "Levantando backend y base de datos..."

$backendImage = "$BackupPath\volumes\backend_image.tar"
if (Test-Path $backendImage) {
    Write-Host "  Cargando imagen Docker del backend desde archivo..." -ForegroundColor Yellow
    docker load -i $backendImage
    Write-OK "Imagen backend cargada"
} else {
    Write-Host "  Imagen no encontrada en backup. Construyendo desde Dockerfile..." -ForegroundColor Yellow
    Write-Warn "Esto puede tardar 10-30 min la primera vez (descarga dependencias ML)."
    docker compose build
    Write-OK "Backend construido"
}

# Si no hay GPU, comentar temporalmente la seccion de GPU en el compose
if (-not $gpuOk) {
    Write-Warn "Sin GPU: si docker compose falla por 'gpus', edita docker-compose.yml y comenta las lineas 'gpus: all' y el bloque 'deploy'."
}

docker compose up -d db
Write-Host "  Esperando que Postgres este listo..." -ForegroundColor Yellow
Start-Sleep -Seconds 8
docker compose up -d
Write-OK "Todos los servicios levantados"

# ── PASO 7: Levantar frontend ──────────────────────────────────────────────────
Write-Step 7 7 "Levantando frontend..."

$frontendDir = "$projectDir\frontend"
if (Test-Path "$frontendDir\package.json") {
    Set-Location $frontendDir

    if (-not (Test-Path "$frontendDir\node_modules")) {
        Write-Host "  Instalando dependencias Node.js (primera vez)..." -ForegroundColor Yellow
        npm install --silent
    }

    Write-Host "  Iniciando servidor de desarrollo en segundo plano..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendDir'; npm run dev" -WindowStyle Normal
    Write-OK "Frontend iniciando en nueva ventana"
    Set-Location $projectDir
} else {
    Write-Warn "No se encontro frontend\package.json. Levanta el frontend manualmente."
}

# ── Resumen final ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  SISTEMA LISTO PARA LA PRESENTACION" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API   : http://localhost:8001" -ForegroundColor White
Write-Host "  Frontend      : http://localhost:5173  (o el puerto que muestre la ventana de Vite)" -ForegroundColor White
Write-Host "  Ollama        : http://localhost:11434" -ForegroundColor White
Write-Host ""
Write-Host "  Comandos utiles:" -ForegroundColor Yellow
Write-Host "    docker compose logs -f backend     <- ver logs del backend"
Write-Host "    docker compose ps                  <- estado de contenedores"
Write-Host "    docker compose down                <- apagar todo al terminar"
Write-Host ""
Write-Host "  Para abrir el sistema en el navegador:" -ForegroundColor Yellow

# Abrir navegador automaticamente
Start-Sleep -Seconds 5
Start-Process "http://localhost:5173"

Write-Host "  Navegador abierto en http://localhost:5173" -ForegroundColor Green
Write-Host ""
