# migrate_export.ps1
# Exporta todo lo necesario para migrar Asofamech a otro equipo.
# Ejecutar desde la raiz del proyecto: .\migrate_export.ps1 -BackupPath "E:\asofamech_migration"

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"
$ProjectName = "asofamech"
$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step($n, $total, $msg) {
    Write-Host "`n[$n/$total] $msg" -ForegroundColor Cyan
}
function Write-OK($msg)   { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  AVISO: $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  ASOFAMECH - Exportacion para migracion" -ForegroundColor Cyan
Write-Host "  Destino: $BackupPath" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

# ── Crear estructura de destino ──────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path "$BackupPath\volumes"          | Out-Null
New-Item -ItemType Directory -Force -Path "$BackupPath\artifacts"        | Out-Null
New-Item -ItemType Directory -Force -Path "$BackupPath\uploads"          | Out-Null
New-Item -ItemType Directory -Force -Path "$BackupPath\camelyon17_imgs"  | Out-Null

# ── Levantar solo la DB para consultar imagenes importadas ───────────────────
Write-Step 1 6 "Consultando imagenes CAMELYON17 registradas en la base de datos..."
docker compose up -d db | Out-Null
Start-Sleep -Seconds 6

$query = "SELECT file_path FROM medical_images WHERE file_path LIKE '%camelyon17%' OR file_path LIKE '%data/%';"
$rawPaths = docker exec asofamech_db psql -U app_user -d app_db -t -c $query 2>$null

$camelyon17Files = @()
if ($rawPaths) {
    $camelyon17Files = $rawPaths -split "`n" |
        ForEach-Object { $_.Trim() } |
        Where-Object   { $_ -ne "" -and $_ -match "\.(tif|tiff|svs)$" }
    Write-OK "Encontradas $($camelyon17Files.Count) imagenes importadas desde CAMELYON17."
} else {
    Write-Warn "No se pudieron consultar imagenes desde la DB. Continuando sin ellas."
}

docker compose down | Out-Null

# ── Copiar TIF/TIFF importados desde data/camelyon17 ────────────────────────
if ($camelyon17Files.Count -gt 0) {
    Write-Step 2 6 "Copiando imagenes CAMELYON17 importadas (~varios GB)..."
    Write-Warn "Esta es la parte mas pesada. Puede tardar bastante segun el tamano de los TIF."

    foreach ($containerPath in $camelyon17Files) {
        # El contenedor ve /app/data/... => el host tiene backend\data\...
        $relativePath = $containerPath -replace "^/app/", "backend\"
        $relativePath = $relativePath -replace "/", "\"
        $hostPath = Join-Path $scriptDir $relativePath

        if (Test-Path $hostPath) {
            $fileName = Split-Path $hostPath -Leaf
            $sizeMB   = [math]::Round((Get-Item $hostPath).Length / 1MB, 1)
            Write-Host "  Copiando $fileName ($sizeMB MB)..." -ForegroundColor Yellow
            Copy-Item -Path $hostPath -Destination "$BackupPath\camelyon17_imgs\" -Force
            Write-OK "$fileName"
        } else {
            Write-Warn "Archivo no encontrado en host: $hostPath"
        }
    }
} else {
    Write-Step 2 6 "Sin imagenes CAMELYON17 importadas, omitiendo..."
}

# ── Exportar volumen: base de datos ─────────────────────────────────────────
Write-Step 3 6 "Exportando base de datos (Postgres)..."
docker run --rm `
    -v "${ProjectName}_db_data:/data" `
    -v "${BackupPath}\volumes:/backup" `
    alpine sh -c "tar czf /backup/db_backup.tar.gz -C /data . && echo DONE"
Write-OK "db_backup.tar.gz"

# ── Exportar volumen: HuggingFace cache (modelo CONCH) ──────────────────────
Write-Step 4 6 "Exportando modelo CONCH (HuggingFace cache)..."
Write-Warn "Puede tardar 2-5 min (~1-2 GB)..."
docker run --rm `
    -v "${ProjectName}_huggingface_cache:/data" `
    -v "${BackupPath}\volumes:/backup" `
    alpine sh -c "tar czf /backup/hf_backup.tar.gz -C /data . && echo DONE"
Write-OK "hf_backup.tar.gz"

# ── Exportar volumen: Ollama (llama3:8b) ─────────────────────────────────────
Write-Step 5 6 "Exportando modelos Ollama (llama3:8b)..."
Write-Warn "Puede tardar 10-20 min (~5 GB)..."
docker run --rm `
    -v "${ProjectName}_ollama_data:/data" `
    -v "${BackupPath}\volumes:/backup" `
    alpine sh -c "tar czf /backup/ollama_backup.tar.gz -C /data . && echo DONE"
Write-OK "ollama_backup.tar.gz"

# ── Copiar artifacts y uploads ───────────────────────────────────────────────
Write-Step 6 6 "Copiando artifacts y uploads..."

Copy-Item -Path "$scriptDir\backend\artifacts\*" -Destination "$BackupPath\artifacts\" -Recurse -Force
Write-OK "artifacts\ copiado"

if (Test-Path "$scriptDir\backend\uploads") {
    Copy-Item -Path "$scriptDir\backend\uploads\*" -Destination "$BackupPath\uploads\" -Recurse -Force -ErrorAction SilentlyContinue
    Write-OK "uploads\ copiado"
}

# ── Guardar imagen Docker del backend ────────────────────────────────────────
Write-Host "`n[Extra] Guardando imagen Docker del backend..." -ForegroundColor Cyan
Write-Warn "Opcional pero evita recompilar en destino (~8-10 GB, puede tardar 10-15 min)."
$imageExists = (docker images -q "${ProjectName}-backend" 2>$null) -or (docker images -q "asofamech-backend" 2>$null)
if ($imageExists) {
    $imageName = docker images --format "{{.Repository}}" | Where-Object { $_ -match "backend" } | Select-Object -First 1
    docker save $imageName -o "$BackupPath\volumes\backend_image.tar"
    Write-OK "backend_image.tar"
} else {
    Write-Warn "Imagen backend no construida. Recuerda hacer 'docker compose build' antes si quieres incluirla."
}

# ── Manifest ─────────────────────────────────────────────────────────────────
@{
    exported_at      = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    project_name     = $ProjectName
    camelyon17_files = $camelyon17Files
    volumes          = @("db_backup.tar.gz", "hf_backup.tar.gz", "ollama_backup.tar.gz")
} | ConvertTo-Json | Out-File -Encoding utf8 "$BackupPath\manifest.json"

# ── Resumen ───────────────────────────────────────────────────────────────────
$totalGB = [math]::Round(
    (Get-ChildItem $BackupPath -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1GB, 2)

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  EXPORTACION COMPLETADA  ($totalGB GB total)" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Contenido exportado:" -ForegroundColor White
Write-Host "  camelyon17_imgs\    <- TIF importados desde CAMELYON17 ($($camelyon17Files.Count) archivos)"
Write-Host "  volumes\db_backup.tar.gz       <- base de datos"
Write-Host "  volumes\hf_backup.tar.gz       <- modelo CONCH"
Write-Host "  volumes\ollama_backup.tar.gz   <- llama3:8b"
Write-Host "  artifacts\                     <- checkpoints del modelo"
Write-Host "  uploads\                       <- imagenes subidas por usuarios"
Write-Host ""
Write-Host "En el equipo destino:" -ForegroundColor Yellow
Write-Host "  1. Clona el repositorio"
Write-Host "  2. Ejecuta: .\start_presentation.ps1 -BackupPath '<ruta_backup>'"
Write-Host ""
