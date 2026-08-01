# start_presentation.ps1
# Restaura un backup de ASOFAMECH y levanta el sistema con Docker Compose.
# Uso:
#   .\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration"
#   .\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration" -SkipChecksum
#   .\scripts\start_presentation.ps1 -BackupPath "E:\asofamech_migration_lite" -PullOllamaModel

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,

    [string]$ProjectName = "asofamech",

    [switch]$SkipChecksum,

    [switch]$PullOllamaModel,

    [string]$OllamaModel = "llama3.1:8b"
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Write-Step($n, $total, $msg) {
    Write-Host "`n[$n/$total] $msg" -ForegroundColor Cyan
}
function Write-OK($msg)    { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  AVISO: $msg" -ForegroundColor Yellow }
function Write-Fail($msg)  { Write-Host "  ERROR: $msg" -ForegroundColor Red }

function New-SecureHexSecret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return -join ($bytes | ForEach-Object { $_.ToString("x2") })
}

function Set-EnvSetting {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Key,
        [string]$Value
    )
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match "^$([regex]::Escape($Key))=") {
            $Lines[$i] = "$Key=$Value"
            return
        }
    }
    $Lines.Add("$Key=$Value")
}

function Initialize-PresentationEnvironment {
    $envPath = Join-Path $projectDir ".env"
    $examplePath = Join-Path $projectDir ".env.example"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false

    if (Test-Path -LiteralPath $envPath) {
        $lines = [System.Collections.Generic.List[string]]::new()
        [System.IO.File]::ReadAllLines($envPath) | ForEach-Object { $lines.Add($_) }
    } elseif (Test-Path -LiteralPath $examplePath) {
        $lines = [System.Collections.Generic.List[string]]::new()
        [System.IO.File]::ReadAllLines($examplePath) | ForEach-Object { $lines.Add($_) }
        Write-Warn ".env no existia; se creo desde .env.example."
    } else {
        $lines = [System.Collections.Generic.List[string]]::new()
        Write-Warn ".env y .env.example no existen; se creara configuracion minima."
    }

    $currentSecret = ""
    foreach ($line in $lines) {
        if ($line -match "^ASOFAMECH_JWT_SECRET=(.*)$") {
            $currentSecret = $Matches[1].Trim()
        }
    }
    if ($currentSecret.Length -lt 32 -or $currentSecret -match "cambia|change|secret") {
        Set-EnvSetting $lines "ASOFAMECH_JWT_SECRET" (New-SecureHexSecret)
        Write-OK "Se genero un secreto JWT local seguro."
    }

    Set-EnvSetting $lines "APP_ENV" "production"
    Set-EnvSetting $lines "ASOFAMECH_ACCESS_TOKEN_EXPIRE_MINUTES" "720"
    Set-EnvSetting $lines "FRONTEND_API_BASE" ""
    Set-EnvSetting $lines "ASOFAMECH_PLATFORM_URL" "http://localhost:3000/auth"

    [System.IO.File]::WriteAllLines($envPath, $lines, $utf8NoBom)
    Write-OK "Entorno local de presentacion preparado."
}

function Format-Bytes($bytes) {
    if ($null -eq $bytes) { return "0 B" }
    if ($bytes -ge 1GB) { return "$([math]::Round($bytes / 1GB, 2)) GB" }
    if ($bytes -ge 1MB) { return "$([math]::Round($bytes / 1MB, 1)) MB" }
    if ($bytes -ge 1KB) { return "$([math]::Round($bytes / 1KB, 1)) KB" }
    return "$bytes B"
}

function Get-DirectoryStats($Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return @{ files = 0; bytes = 0 }
    }

    $files = @(Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue)
    $bytes = ($files | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $bytes) { $bytes = 0 }
    return @{ files = $files.Count; bytes = [int64]$bytes }
}

function Copy-DirectoryContents($Source, $Destination, $Label) {
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    if (-not (Test-Path -LiteralPath $Source)) {
        Write-Warn "$Label no existe en backup: $Source"
        return @{ files = 0; bytes = 0 }
    }

    $items = @(Get-ChildItem -LiteralPath $Source -Force -ErrorAction SilentlyContinue)
    if ($items.Count -eq 0) {
        Write-Warn "$Label esta vacio."
        return @{ files = 0; bytes = 0 }
    }

    $projectRoot = [System.IO.Path]::GetFullPath($projectDir).TrimEnd("\")
    $destinationFull = [System.IO.Path]::GetFullPath($Destination).TrimEnd("\")
    if (-not $destinationFull.StartsWith("$projectRoot\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Destino fuera del proyecto; no se reemplaza por seguridad: $destinationFull"
    }
    Get-ChildItem -LiteralPath $destinationFull -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force

    foreach ($item in $items) {
        Copy-Item -LiteralPath $item.FullName -Destination $Destination -Recurse -Force
    }

    $stats = Get-DirectoryStats $Destination
    Write-OK "$Label restaurado: $($stats.files) archivo(s), $(Format-Bytes $stats.bytes)"
    return $stats
}

function Restore-DockerVolume($VolumeName, $BackupFileName, $Label) {
    $archive = Join-Path $volumesDir $BackupFileName
    if (-not (Test-Path -LiteralPath $archive)) {
        Write-Warn "$BackupFileName no encontrado. Se omitira $Label."
        return $false
    }

    docker volume inspect $VolumeName *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Warn "El volumen $VolumeName ya existe y sera reemplazado por el snapshot."
    }

    docker volume create $VolumeName | Out-Null
    docker run --rm `
        -v "${VolumeName}:/data" `
        -v "${volumesDir}:/backup:ro" `
        alpine sh -c "find /data -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar xzf /backup/$BackupFileName -C /data"

    Write-OK "$Label restaurado desde $BackupFileName"
    return $true
}

function Test-Checksums($Root, $ChecksumFile) {
    if (-not (Test-Path -LiteralPath $ChecksumFile)) {
        Write-Warn "checksums.sha256 no encontrado. No se verificara integridad."
        return
    }

    $rootFull = (Resolve-Path -LiteralPath $Root).Path.TrimEnd("\")
    $lines = @(Get-Content -LiteralPath $ChecksumFile | Where-Object { $_.Trim() -ne "" })
    $checked = 0

    foreach ($line in $lines) {
        $parts = $line -split "\s+", 2
        if ($parts.Count -lt 2) { continue }

        $expected = $parts[0].Trim().ToLowerInvariant()
        $relative = $parts[1].Trim()
        $path = Join-Path $rootFull ($relative -replace "/", "\")

        if (-not (Test-Path -LiteralPath $path)) {
            throw "Falta archivo del backup: $relative"
        }

        $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) {
            throw "Checksum invalido para $relative"
        }
        $checked++
    }

    Write-OK "$checked archivo(s) verificados por SHA256"
}

function Wait-Url($Url, $Label, $Retries = 30) {
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

function Wait-PostgresReady {
    for ($i = 1; $i -le 30; $i++) {
        docker exec asofamech_db pg_isready -U app_user -d app_db *> $null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Sync-ExplicitHistologySelection($Manifest) {
    if ($null -eq $Manifest) { return }
    if ($null -eq $Manifest.folders -or $null -eq $Manifest.folders.histology_images) { return }
    if ($Manifest.folders.histology_images.selection -ne "explicit_file_names") { return }

    $selectedNames = @(
        $Manifest.folders.histology_images.referenced_files |
            ForEach-Object { [string]$_ } |
            Where-Object { $_.Trim() -ne "" }
    )

    if ($selectedNames.Count -eq 0) {
        Write-Warn "Backup con seleccion explicita de laminas, pero la lista esta vacia."
        return
    }

    $quotedNames = @(
        $selectedNames |
            ForEach-Object { "'" + ($_.Replace("'", "''")) + "'" }
    ) -join ", "

    $query = @"
UPDATE medical_images
SET is_active = false
WHERE is_active = true
  AND (
    lower(coalesce(pathology_type, '')) = 'camelyon17'
    OR replace(lower(file_path), '\', '/') LIKE '%data/camelyon17/images/%'
  )
  AND filename NOT IN ($quotedNames);
"@

    $queryLine = ($query -split "`r?`n") -join " "
    docker exec asofamech_db psql -U app_user -d app_db -c $queryLine | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Biblioteca sincronizada con seleccion de laminas: $($selectedNames.Count) archivo(s)"
    } else {
        Write-Warn "No se pudo sincronizar la biblioteca con la seleccion de laminas."
    }
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  ASOFAMECH - Setup presentacion" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

Write-Step 1 8 "Verificando prerequisitos y backup"
Initialize-PresentationEnvironment
try {
    docker info | Out-Null
    Write-OK "Docker en ejecucion"
} catch {
    Write-Fail "Docker no esta corriendo. Abre Docker Desktop y vuelve a ejecutar."
    exit 1
}

$gpuOk = $false
try {
    $nvOut = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>$null
    if ($nvOut) {
        Write-OK "GPU detectada: $nvOut"
        $gpuOk = $true
    }
} catch {}
if (-not $gpuOk) {
    Write-Warn "No se detecto GPU NVIDIA. Si Docker falla por GPU, usa un compose/override CPU."
}

if (-not (Test-Path -LiteralPath $BackupPath)) {
    Write-Fail "Ruta de backup no encontrada: $BackupPath"
    exit 1
}

$backupRoot = (Resolve-Path -LiteralPath $BackupPath).Path
$volumesDir = Join-Path $backupRoot "volumes"
Write-OK "Backup encontrado en $backupRoot"

$manifestPath = Join-Path $backupRoot "manifest.json"
if (Test-Path -LiteralPath $manifestPath) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    Write-OK "Manifest encontrado: formato $($manifest.backup_format_version), exportado $($manifest.exported_at)"
} else {
    Write-Warn "manifest.json no encontrado. Se intentara restaurar con estructura compatible."
}

Write-Step 2 8 "Verificando integridad del backup"
if ($SkipChecksum) {
    Write-Warn "Verificacion SHA256 omitida por -SkipChecksum."
} else {
    Test-Checksums $backupRoot (Join-Path $backupRoot "checksums.sha256")
}

Write-Step 3 8 "Restaurando base de datos PostgreSQL"
Write-Warn "Se detendra cualquier stack ASOFAMECH activo antes de restaurar volumenes."
docker compose down | Out-Null
Restore-DockerVolume "${ProjectName}_db_data" "db_backup.tar.gz" "Base de datos"

Write-Step 4 8 "Restaurando laminas histologicas locales"
$newHistologySrc = Join-Path $backupRoot "histology_images\camelyon17\images"
$legacyHistologySrc = Join-Path $backupRoot "camelyon17_imgs"
$histologySrc = if (Test-Path -LiteralPath $newHistologySrc) { $newHistologySrc } else { $legacyHistologySrc }
$histologyDst = Join-Path $projectDir "backend\data\camelyon17\images"
Copy-DirectoryContents $histologySrc $histologyDst "Laminas histologicas"

Write-Step 5 8 "Restaurando artifacts y uploads"
Copy-DirectoryContents (Join-Path $backupRoot "artifacts") (Join-Path $projectDir "backend\artifacts") "artifacts"
Copy-DirectoryContents (Join-Path $backupRoot "uploads") (Join-Path $projectDir "backend\uploads") "uploads"

Write-Step 6 8 "Restaurando volumenes de modelos"
$hfRestored = Restore-DockerVolume "${ProjectName}_huggingface_cache" "hf_backup.tar.gz" "HuggingFace cache / CONCH"
$ollamaRestored = Restore-DockerVolume "${ProjectName}_ollama_data" "ollama_backup.tar.gz" "Ollama"
if (-not $hfRestored) {
    Write-Warn "CONCH no viene incluido en este backup. Luego ejecuta .\scripts\prepare_histopathology_model.ps1 para descargarlo con tu token HuggingFace."
}
if (-not $ollamaRestored) {
    if ($PullOllamaModel) {
        Write-Warn "Ollama no viene incluido. Se descargara $OllamaModel despues de levantar el servicio."
    } else {
        Write-Warn "Ollama no viene incluido. Si necesitas chatbot local, ejecuta luego: docker exec asofamech_ollama ollama pull $OllamaModel"
    }
}

Write-Step 7 8 "Cargando imagenes Docker y levantando servicios"
$composeImagesTar = Join-Path $volumesDir "compose_images.tar"
$legacyBackendImageTar = Join-Path $volumesDir "backend_image.tar"

if (Test-Path -LiteralPath $composeImagesTar) {
    Write-Host "  Cargando imagenes Docker desde compose_images.tar..." -ForegroundColor Yellow
    docker load -i $composeImagesTar
    Write-OK "Imagenes Docker cargadas"
} elseif (Test-Path -LiteralPath $legacyBackendImageTar) {
    Write-Host "  Cargando imagen Docker legacy del backend..." -ForegroundColor Yellow
    docker load -i $legacyBackendImageTar
    Write-OK "Imagen backend cargada"
} else {
    Write-Host "  Imagenes Docker no incluidas. Construyendo desde Dockerfile..." -ForegroundColor Yellow
    Write-Warn "Esto puede tardar y puede requerir internet si no estan las dependencias en cache."
    docker compose build
    Write-OK "Imagenes Docker construidas"
}

docker compose up -d db
Write-Host "  Esperando que PostgreSQL este listo..." -ForegroundColor Yellow
if (Wait-PostgresReady) {
    Write-OK "PostgreSQL listo"
    Sync-ExplicitHistologySelection $manifest
} else {
    Write-Warn "PostgreSQL no respondio a tiempo; se levantaran servicios igualmente."
}
docker compose up -d
Write-OK "Servicios Docker solicitados"

if (-not $ollamaRestored -and $PullOllamaModel) {
    Write-Host "  Descargando modelo Ollama $OllamaModel..." -ForegroundColor Yellow
    docker exec asofamech_ollama ollama pull $OllamaModel
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Modelo Ollama disponible: $OllamaModel"
    } else {
        Write-Warn "No se pudo descargar $OllamaModel automaticamente. Puedes repetir: docker exec asofamech_ollama ollama pull $OllamaModel"
    }
}

Write-Step 8 8 "Verificando servicios y abriendo frontend"
$backendUrl = "http://localhost:8001/health"
$frontendUrl = "http://localhost:3000"
Wait-Url $backendUrl "Backend" 45 | Out-Null
Wait-Url $frontendUrl "Frontend Docker" 45 | Out-Null

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  SISTEMA LISTO PARA LA PRESENTACION" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API   : http://localhost:8001" -ForegroundColor White
Write-Host "  Frontend      : $frontendUrl" -ForegroundColor White
Write-Host "  Ollama        : http://localhost:11434" -ForegroundColor White
Write-Host ""
Write-Host "  Comandos utiles:" -ForegroundColor Yellow
Write-Host "    docker compose logs -f backend     <- ver logs del backend"
Write-Host "    docker compose logs -f frontend    <- ver logs del frontend"
Write-Host "    docker compose ps                  <- estado de contenedores"
Write-Host "    docker compose down                <- apagar todo al terminar"
if (-not $hfRestored) {
    Write-Host "    .\scripts\prepare_histopathology_model.ps1 <- preparar CONCH con token HuggingFace" -ForegroundColor Yellow
}
if (-not $ollamaRestored) {
    Write-Host "    docker exec asofamech_ollama ollama pull $OllamaModel <- descargar LLM local" -ForegroundColor Yellow
}
Write-Host ""

Start-Sleep -Seconds 3
Start-Process $frontendUrl
Write-Host "  Navegador abierto en $frontendUrl" -ForegroundColor Green
Write-Host ""
