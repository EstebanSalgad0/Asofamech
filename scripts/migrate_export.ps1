# migrate_export.ps1
# Exporta lo necesario para migrar ASOFAMECH a otro equipo.
# Uso:
#   .\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration"
#   .\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration" -HistologyImageNames "patient_017_node_2.tif","patient_012_node_1.tif"
#   .\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration" -AllHistologyImages
#   .\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration" -SkipDockerImages
#   .\scripts\migrate_export.ps1 -BackupPath "E:\asofamech_migration" -IncludeRestrictedModelCache

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,

    [string]$ProjectName = "asofamech",

    [switch]$SkipDockerImages,

    [switch]$IncludeRestrictedModelCache,

    [string[]]$HistologyImageNames = @(),

    [switch]$AllHistologyImages,

    [switch]$LeaveStackStopped
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Write-Step($n, $total, $msg) {
    Write-Host "`n[$n/$total] $msg" -ForegroundColor Cyan
}
function Write-OK($msg)   { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  AVISO: $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "  ERROR: $msg" -ForegroundColor Red }

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

function Clear-DirectoryContents($Path, $Root) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null

    $rootFull = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Root).Path).TrimEnd("\")
    $pathFull = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path).TrimEnd("\")
    if (-not $pathFull.StartsWith($rootFull + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Ruta fuera del backup; no se limpia por seguridad: $pathFull"
    }

    Get-ChildItem -LiteralPath $pathFull -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force
}

function Get-ReferencedCamelyonImageNames {
    $query = @"
SELECT DISTINCT filename
FROM medical_images
WHERE is_active = true
  AND (
    lower(coalesce(pathology_type, '')) = 'camelyon17'
    OR replace(lower(file_path), '\', '/') LIKE '%data/camelyon17/images/%'
  )
ORDER BY filename;
"@

    $queryLine = ($query -split "`r?`n") -join " "
    $output = docker exec asofamech_db psql -U app_user -d app_db -t -A -c $queryLine 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "No se pudieron leer las laminas CAMELYON17 registradas en la base de datos."
        return @()
    }

    return @(
        $output |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )
}

function Copy-DirectoryContents {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [string]$Destination,

        [Parameter(Mandatory = $true)]
        [string]$Label,

        [switch]$ShowProgress,

        [AllowEmptyCollection()]
        [string[]]$IncludeFileNames
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    if (-not (Test-Path -LiteralPath $Source)) {
        Write-Warn "$Label no existe en origen: $Source"
        return @{ files = 0; bytes = 0 }
    }

    $items = @(Get-ChildItem -LiteralPath $Source -Force -ErrorAction SilentlyContinue)
    if ($items.Count -eq 0) {
        Write-Warn "$Label esta vacio."
        return @{ files = 0; bytes = 0 }
    }

    if ($ShowProgress) {
        Write-Host "  Calculando tamano de $Label..." -ForegroundColor DarkGray
        $sourceFull = (Resolve-Path -LiteralPath $Source).Path.TrimEnd("\")
        $destinationFull = (Resolve-Path -LiteralPath $Destination).Path.TrimEnd("\")
        $directories = @(Get-ChildItem -LiteralPath $sourceFull -Recurse -Directory -Force -ErrorAction SilentlyContinue)
        $files = @(Get-ChildItem -LiteralPath $sourceFull -Recurse -File -Force -ErrorAction SilentlyContinue)

        if ($PSBoundParameters.ContainsKey("IncludeFileNames")) {
            $wanted = @{}
            foreach ($name in $IncludeFileNames) {
                if ($name) {
                    $wanted[$name.ToLowerInvariant()] = $true
                }
            }

            $files = @(
                $files | Where-Object {
                    $wanted.ContainsKey($_.Name.ToLowerInvariant())
                }
            )

            $found = @{}
            foreach ($file in $files) {
                $found[$file.Name.ToLowerInvariant()] = $true
            }

            foreach ($name in $IncludeFileNames) {
                if ($name -and -not $found.ContainsKey($name.ToLowerInvariant())) {
                    Write-Warn "Lamina solicitada pero no encontrada en carpeta local: $name"
                }
            }
        }

        if ($files.Count -eq 0) {
            Write-Warn "$Label no tiene archivos para copiar con el filtro actual."
            return @{ files = 0; bytes = 0 }
        }

        $totalBytes = ($files | Measure-Object -Property Length -Sum).Sum
        if ($null -eq $totalBytes) { $totalBytes = 0 }

        foreach ($directory in $directories) {
            $relativeDir = $directory.FullName.Substring($sourceFull.Length).TrimStart([char[]]"\/")
            New-Item -ItemType Directory -Force -Path (Join-Path $destinationFull $relativeDir) | Out-Null
        }

        $copiedBytes = [int64]0
        $copiedFiles = 0
        $activity = "Copiando $Label"

        foreach ($file in $files) {
            $relativePath = $file.FullName.Substring($sourceFull.Length).TrimStart([char[]]"\/")
            $targetPath = Join-Path $destinationFull $relativePath
            $targetDir = Split-Path -Parent $targetPath
            New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

            Copy-Item -LiteralPath $file.FullName -Destination $targetPath -Force

            $copiedFiles += 1
            $copiedBytes += [int64]$file.Length
            if ($totalBytes -gt 0) {
                $percent = [math]::Min(100, [math]::Round(($copiedBytes / $totalBytes) * 100, 1))
            } else {
                $percent = 100
            }

            Write-Progress `
                -Activity $activity `
                -Status "$copiedFiles/$($files.Count) archivo(s) - $(Format-Bytes $copiedBytes) de $(Format-Bytes $totalBytes)" `
                -PercentComplete $percent `
                -CurrentOperation $relativePath
        }

        Write-Progress -Activity $activity -Completed
        $stats = Get-DirectoryStats $Destination
        Write-OK "$Label copiado: $($stats.files) archivo(s), $(Format-Bytes $stats.bytes)"
        return $stats
    }

    foreach ($item in $items) {
        Copy-Item -LiteralPath $item.FullName -Destination $Destination -Recurse -Force
    }

    $stats = Get-DirectoryStats $Destination
    Write-OK "$Label copiado: $($stats.files) archivo(s), $(Format-Bytes $stats.bytes)"
    return $stats
}

function Export-DockerVolume($VolumeName, $OutputFileName, $Label) {
    docker volume inspect $VolumeName *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Volumen no encontrado: $VolumeName ($Label)."
        return $false
    }

    docker run --rm `
        -v "${VolumeName}:/data:ro" `
        -v "${volumesDir}:/backup" `
        alpine sh -c "tar czf /backup/$OutputFileName -C /data . && echo DONE"

    Write-OK "$OutputFileName exportado ($Label)"
    return $true
}

function Wait-PostgresReady {
    for ($i = 1; $i -le 30; $i++) {
        docker exec asofamech_db pg_isready -U app_user -d app_db *> $null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function New-Checksums($Root, $OutputFile) {
    $rootFull = (Resolve-Path -LiteralPath $Root).Path.TrimEnd("\")
    $outputFull = [System.IO.Path]::GetFullPath($OutputFile)
    $files = @(
        Get-ChildItem -LiteralPath $rootFull -Recurse -File -Force |
            Where-Object { [System.IO.Path]::GetFullPath($_.FullName) -ne $outputFull }
    )

    $lines = foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($rootFull.Length + 1).Replace("\", "/")
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $relativePath"
    }

    $lines | Set-Content -Path $OutputFile -Encoding ascii
    return $files.Count
}

$backupRoot = (New-Item -ItemType Directory -Force -Path $BackupPath).FullName
$volumesDir = Join-Path $backupRoot "volumes"
$artifactsDir = Join-Path $backupRoot "artifacts"
$uploadsDir = Join-Path $backupRoot "uploads"
$histologyDir = Join-Path $backupRoot "histology_images"
$histologyCamelyonDir = Join-Path $histologyDir "camelyon17\images"

New-Item -ItemType Directory -Force -Path $volumesDir | Out-Null
New-Item -ItemType Directory -Force -Path $artifactsDir | Out-Null
New-Item -ItemType Directory -Force -Path $uploadsDir | Out-Null
New-Item -ItemType Directory -Force -Path $histologyCamelyonDir | Out-Null

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  ASOFAMECH - Exportacion para migracion" -ForegroundColor Cyan
Write-Host "  Destino: $backupRoot" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

try {
    docker info | Out-Null
    Write-OK "Docker en ejecucion"
} catch {
    Write-Fail "Docker no esta corriendo. Abre Docker Desktop y vuelve a ejecutar."
    exit 1
}

if ($AllHistologyImages -and $HistologyImageNames.Count -gt 0) {
    Write-Fail "Usa -AllHistologyImages o -HistologyImageNames, pero no ambos al mismo tiempo."
    exit 1
}

$existingBackupFiles = @(
    Get-ChildItem -LiteralPath $backupRoot -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notlike (Join-Path $backupRoot ".placeholder") }
)
if ($existingBackupFiles.Count -gt 0) {
    Write-Warn "La carpeta de backup ya contiene archivos. Se sobrescribiran coincidencias, pero no se borraran sobrantes."
}

Write-Step 1 6 "Exportando base de datos PostgreSQL"
Write-Warn "Se detendra el stack Docker para crear un respaldo consistente de los volumenes."
docker compose up -d db | Out-Null
if (Wait-PostgresReady) {
    Write-OK "PostgreSQL listo para respaldo"
} else {
    Write-Warn "PostgreSQL no respondio a tiempo; se intentara exportar el volumen igualmente."
}
$referencedCamelyonImages = @()
if (-not $AllHistologyImages) {
    if ($HistologyImageNames.Count -gt 0) {
        $referencedCamelyonImages = @(
            $HistologyImageNames |
                ForEach-Object { [System.IO.Path]::GetFileName($_.Trim()) } |
                Where-Object { $_ } |
                Select-Object -Unique
        )
        Write-OK "Se exportaran $($referencedCamelyonImages.Count) lamina(s) CAMELYON17 seleccionadas explicitamente."
    } else {
        $referencedCamelyonImages = Get-ReferencedCamelyonImageNames
    }

    if ($referencedCamelyonImages.Count -gt 0) {
        if ($HistologyImageNames.Count -eq 0) {
            Write-OK "Se exportaran $($referencedCamelyonImages.Count) lamina(s) CAMELYON17 registradas en la base."
        }
    } else {
        Write-Warn "No hay laminas CAMELYON17 registradas en la base. Usa -AllHistologyImages si quieres mover toda la carpeta local."
    }
} else {
    Write-Warn "Se exportaran todas las laminas locales por -AllHistologyImages."
}
docker compose down | Out-Null
$dbExported = Export-DockerVolume "${ProjectName}_db_data" "db_backup.tar.gz" "PostgreSQL"
if (-not $LeaveStackStopped) {
    Write-Host ""
    Write-Host "Reiniciando stack Docker antes de copiar archivos pesados..." -ForegroundColor Cyan
    docker compose up -d | Out-Null
    Write-OK "Stack Docker reiniciado"
}

Write-Step 2 6 "Copiando laminas histologicas locales"
$sourceCamelyonImages = Join-Path $scriptDir "backend\data\camelyon17\images"
Clear-DirectoryContents $histologyCamelyonDir $backupRoot
if ($AllHistologyImages) {
    $histologyStats = Copy-DirectoryContents $sourceCamelyonImages $histologyCamelyonDir "backend\data\camelyon17\images" -ShowProgress
} else {
    $histologyStats = Copy-DirectoryContents $sourceCamelyonImages $histologyCamelyonDir "backend\data\camelyon17\images" -ShowProgress -IncludeFileNames $referencedCamelyonImages
}

Write-Step 3 6 "Copiando artifacts y uploads"
$artifactsStats = Copy-DirectoryContents (Join-Path $scriptDir "backend\artifacts") $artifactsDir "backend\artifacts"
$uploadsStats = Copy-DirectoryContents (Join-Path $scriptDir "backend\uploads") $uploadsDir "backend\uploads"

Write-Step 4 6 "Exportando volumenes Docker necesarios"
$hfExported = $false
if ($IncludeRestrictedModelCache) {
    Write-Warn "Se exportara el cache HuggingFace/CONCH. Usar solo si tienes autorizacion para mover ese cache."
    $hfExported = Export-DockerVolume "${ProjectName}_huggingface_cache" "hf_backup.tar.gz" "HuggingFace cache / CONCH"
} else {
    Write-Warn "No se exporta HuggingFace/CONCH por defecto. En destino usa prepare_histopathology_model.ps1 con tu token."
}
$ollamaExported = Export-DockerVolume "${ProjectName}_ollama_data" "ollama_backup.tar.gz" "Ollama"

Write-Step 5 6 "Guardando imagenes Docker disponibles"
$dockerImages = @()
if ($SkipDockerImages) {
    Write-Warn "Omitiendo exportacion de imagenes Docker por -SkipDockerImages."
} else {
    $candidateImages = @(
        "${ProjectName}-backend",
        "${ProjectName}-frontend",
        "pgvector/pgvector:pg15",
        "ollama/ollama:latest"
    )
    $availableImages = @()
    foreach ($imageName in $candidateImages) {
        docker image inspect $imageName *> $null
        if ($LASTEXITCODE -eq 0) {
            $availableImages += $imageName
        }
    }

    if ($availableImages.Count -gt 0) {
        $composeImagesTar = Join-Path $volumesDir "compose_images.tar"
        docker save -o $composeImagesTar $availableImages
        $dockerImages += "compose_images.tar"
        Write-OK "compose_images.tar guardado con $($availableImages.Count) imagen(es)"
    } else {
        Write-Warn "No se encontraron imagenes Docker conocidas. En destino se construiran/descargaran si es necesario."
    }
}

Write-Step 6 6 "Generando manifest y checksums"
$volumeFiles = @(Get-ChildItem -LiteralPath $volumesDir -File -Force -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
$manifest = [ordered]@{
    backup_format_version = 4
    exported_at = (Get-Date).ToString("o")
    project_name = $ProjectName
    source_project_dir = $scriptDir
    folders = [ordered]@{
        histology_images = [ordered]@{
            source = "backend/data/camelyon17/images"
            destination = "histology_images/camelyon17/images"
            selection = if ($AllHistologyImages) { "all_local_files" } elseif ($HistologyImageNames.Count -gt 0) { "explicit_file_names" } else { "db_referenced_active_camelyon17" }
            referenced_files = $referencedCamelyonImages
            files = $histologyStats.files
            bytes = $histologyStats.bytes
        }
        artifacts = [ordered]@{
            source = "backend/artifacts"
            destination = "artifacts"
            files = $artifactsStats.files
            bytes = $artifactsStats.bytes
        }
        uploads = [ordered]@{
            source = "backend/uploads"
            destination = "uploads"
            files = $uploadsStats.files
            bytes = $uploadsStats.bytes
        }
    }
    volumes = [ordered]@{
        db = @{ exported = $dbExported; file = "db_backup.tar.gz" }
        huggingface_cache = @{ exported = $hfExported; file = "hf_backup.tar.gz" }
        ollama = @{ exported = $ollamaExported; file = "ollama_backup.tar.gz" }
    }
    restricted_model_policy = [ordered]@{
        conch_cache_exported_by_default = $false
        conch_cache_included = $hfExported
        preparation_script = "prepare_histopathology_model.ps1"
        note = "CONCH/MahmoodLab is gated and should be downloaded in the destination machine with an authorized HuggingFace token unless explicit redistribution permission exists."
    }
    docker_images = $dockerImages
    volume_files = $volumeFiles
    checksums_file = "checksums.sha256"
}

$manifestPath = Join-Path $backupRoot "manifest.json"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath -Encoding utf8

$checksumPath = Join-Path $backupRoot "checksums.sha256"
$checksumCount = New-Checksums $backupRoot $checksumPath
Write-OK "checksums.sha256 generado para $checksumCount archivo(s)"

$totalStats = Get-DirectoryStats $backupRoot

if ($LeaveStackStopped) {
    Write-Warn "El stack Docker quedo detenido por -LeaveStackStopped."
} else {
    Write-Host ""
    Write-Host "Reiniciando stack Docker de ASOFAMECH..." -ForegroundColor Cyan
    docker compose up -d | Out-Null
    Write-OK "Stack Docker reiniciado"
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  EXPORTACION COMPLETADA ($(Format-Bytes $totalStats.bytes) total)" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Contenido exportado:" -ForegroundColor White
Write-Host "  histology_images\camelyon17\images\  <- laminas WSI locales"
Write-Host "  uploads\                             <- imagenes subidas y DZI"
Write-Host "  artifacts\                           <- checkpoints, heatmaps y auditorias"
Write-Host "  volumes\db_backup.tar.gz             <- base de datos"
if ($hfExported) {
    Write-Host "  volumes\hf_backup.tar.gz             <- cache HuggingFace / CONCH"
} else {
    Write-Host "  prepare_histopathology_model.ps1      <- preparar CONCH en destino con token autorizado"
}
Write-Host "  volumes\ollama_backup.tar.gz         <- modelos Ollama"
Write-Host "  manifest.json / checksums.sha256     <- inventario e integridad"
if (-not $SkipDockerImages) {
    Write-Host "  volumes\compose_images.tar           <- imagenes Docker disponibles, si existian"
}
Write-Host ""
Write-Host "En el equipo destino:" -ForegroundColor Yellow
Write-Host "  1. Copia este backup junto al repositorio."
Write-Host "  2. Ejecuta: .\scripts\start_presentation.ps1 -BackupPath '$backupRoot'"
Write-Host ""
