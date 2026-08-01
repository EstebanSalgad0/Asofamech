# Verifica que una instalacion de ASOFAMECH este lista para una presentacion.
# Uso:
#   .\scripts\check_presentation_readiness.ps1
#   .\scripts\check_presentation_readiness.ps1 -ExpectedBranch main
#   .\scripts\check_presentation_readiness.ps1 -PublicUrl "https://xxxx.trycloudflare.com"
#   .\scripts\check_presentation_readiness.ps1 -CheckLlmGeneration

param(
    [string]$ExpectedBranch = "",
    [string]$PublicUrl = "",
    [switch]$CheckLlmGeneration
)

$ErrorActionPreference = "Continue"
$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectDir

$script:failures = 0
$script:warnings = 0

function Write-Pass([string]$Message) {
    Write-Host "  OK    $Message" -ForegroundColor Green
}

function Write-WarningResult([string]$Message) {
    $script:warnings++
    Write-Host "  AVISO $Message" -ForegroundColor Yellow
}

function Write-Failure([string]$Message) {
    $script:failures++
    Write-Host "  FALLO $Message" -ForegroundColor Red
}

function Get-EnvValue([string]$Key) {
    $envPath = Join-Path $projectDir ".env"
    if (-not (Test-Path -LiteralPath $envPath)) { return $null }
    $line = @(
        Get-Content -LiteralPath $envPath -Encoding utf8 |
            Where-Object { $_ -match "^$([regex]::Escape($Key))=" }
    ) | Select-Object -Last 1
    if ($null -eq $line) { return $null }
    return $line.Substring($Key.Length + 1).Trim()
}

function Test-LocalUrl([string]$Url, [string]$Label) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 12
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
            Write-Pass "$Label responde HTTP $($response.StatusCode)"
            return $true
        }
        Write-Failure "$Label respondio HTTP $($response.StatusCode)"
    } catch {
        Write-Failure "$Label no responde: $($_.Exception.Message)"
    }
    return $false
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  ASOFAMECH - Verificacion para presentacion" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

Write-Host "`n[1/6] Git y version desplegable" -ForegroundColor Cyan
try {
    $branch = (git branch --show-current 2>$null).Trim()
    $commit = (git rev-parse --short HEAD 2>$null).Trim()
    if ($branch -and $commit) {
        Write-Pass "Rama $branch, commit $commit"
    } else {
        Write-Failure "No se pudo determinar rama y commit"
    }

    if ($ExpectedBranch -and $branch -ne $ExpectedBranch) {
        Write-Failure "Se esperaba la rama $ExpectedBranch, pero esta activo $branch"
    } elseif (-not $ExpectedBranch -and $branch -ne "main") {
        Write-WarningResult "La rama activa no es main; confirma que el otro equipo use exactamente $branch"
    }

    $dirty = @(git status --porcelain 2>$null)
    if ($dirty.Count -eq 0) {
        Write-Pass "No hay cambios locales sin commit"
    } else {
        Write-WarningResult "Hay $($dirty.Count) cambio(s) local(es) que no viajaran con git pull"
        $dirty | ForEach-Object { Write-Host "        $_" -ForegroundColor DarkYellow }
    }

    $upstream = (git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null).Trim()
    if ($upstream) {
        $counts = (git rev-list --left-right --count "$upstream...HEAD" 2>$null).Trim() -split "\s+"
        if ($counts.Count -eq 2) {
            $behind = [int]$counts[0]
            $ahead = [int]$counts[1]
            if ($behind -eq 0 -and $ahead -eq 0) {
                Write-Pass "La rama coincide con $upstream"
            } else {
                Write-WarningResult "Respecto de ${upstream}: atras $behind, adelante $ahead"
            }
        }
    } else {
        Write-WarningResult "La rama no tiene upstream remoto configurado"
    }
} catch {
    Write-Failure "Git no esta disponible: $($_.Exception.Message)"
}

Write-Host "`n[2/6] Configuracion local no versionada" -ForegroundColor Cyan
$envPath = Join-Path $projectDir ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    Write-Failure "Falta .env; Git no lo descarga"
} else {
    Write-Pass ".env presente"
    $jwtSecret = Get-EnvValue "ASOFAMECH_JWT_SECRET"
    if ($jwtSecret -and $jwtSecret.Length -ge 32 -and $jwtSecret -notmatch "cambia|change|secret") {
        Write-Pass "Secreto JWT configurado"
    } else {
        Write-Failure "ASOFAMECH_JWT_SECRET falta o parece inseguro"
    }

    $appEnv = Get-EnvValue "APP_ENV"
    if ($appEnv -eq "production") {
        Write-Pass "APP_ENV=production"
    } else {
        Write-WarningResult "APP_ENV no esta en production"
    }

    $frontendApi = Get-EnvValue "FRONTEND_API_BASE"
    if ([string]::IsNullOrWhiteSpace($frontendApi)) {
        Write-Pass "Frontend usa API por mismo origen, compatible con Cloudflare"
    } elseif ($frontendApi -match "localhost|127\.0\.0\.1") {
        Write-Failure "FRONTEND_API_BASE=$frontendApi rompe el acceso desde equipos externos"
    } else {
        Write-WarningResult "FRONTEND_API_BASE esta fijado en $frontendApi"
    }
}

Write-Host "`n[3/6] Docker y servicios" -ForegroundColor Cyan
$dockerReady = $false
try {
    docker info --format "{{.ServerVersion}}" *> $null
    if ($LASTEXITCODE -eq 0) {
        $dockerReady = $true
        Write-Pass "Docker daemon disponible"
    } else {
        Write-Failure "Docker daemon no esta disponible"
    }
} catch {
    Write-Failure "Docker no esta disponible: $($_.Exception.Message)"
}

if ($dockerReady) {
    foreach ($container in @("asofamech_db", "asofamech_backend", "asofamech_frontend", "asofamech_ollama")) {
        $state = docker inspect $container --format "{{.State.Running}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Failure "No existe el contenedor $container"
            continue
        }
        $parts = ([string]$state).Trim() -split "\|", 2
        if ($parts[0] -ne "true") {
            Write-Failure "$container no esta ejecutandose"
        } elseif ($parts.Count -gt 1 -and $parts[1] -and $parts[1] -ne "healthy") {
            Write-Failure "$container esta activo pero su salud es $($parts[1])"
        } else {
            $healthSuffix = ""
            if ($parts.Count -gt 1 -and $parts[1]) {
                $healthSuffix = " ($($parts[1]))"
            }
            Write-Pass "$container activo$healthSuffix"
        }
    }
}

Write-Host "`n[4/6] Modulos locales" -ForegroundColor Cyan
$backendOk = Test-LocalUrl "http://localhost:8001/health" "Backend"
$frontendOk = Test-LocalUrl "http://localhost:3000" "Frontend"

if ($backendOk) {
    try {
        $histo = Invoke-RestMethod -Uri "http://localhost:8001/api/histopathology/status" -TimeoutSec 120
        if ($histo.model_ready) {
            Write-Pass "Histopatologia lista: $($histo.model_version) en $($histo.device)"
        } else {
            Write-Failure "Histopatologia no esta lista"
        }
    } catch {
        Write-Failure "No se pudo consultar histopatologia: $($_.Exception.Message)"
    }
}

if ($dockerReady) {
    $ollamaModels = docker exec asofamech_ollama ollama list 2>$null | Out-String
    if ($ollamaModels -match "llama3.1:8b") {
        Write-Pass "Ollama tiene llama3.1:8b"
    } else {
        Write-Failure "Ollama no tiene llama3.1:8b"
    }
}

if ($CheckLlmGeneration -and $backendOk) {
    try {
        $body = @{ model = "llama3.1:8b"; prompt = "Responde exactamente: OK"; stream = $false } | ConvertTo-Json
        $watch = [System.Diagnostics.Stopwatch]::StartNew()
        $result = Invoke-RestMethod -Method Post -Uri "http://localhost:11434/api/generate" -ContentType "application/json" -Body $body -TimeoutSec 180
        $watch.Stop()
        if ($result.done) {
            $seconds = [math]::Round($watch.Elapsed.TotalSeconds, 1)
            if ($seconds -gt 30) {
                Write-WarningResult "Generacion Ollama correcta pero lenta en frio: $seconds s; calienta el modelo antes de presentar"
            } else {
                Write-Pass "Generacion Ollama correcta en $seconds s"
            }
        } else {
            Write-Failure "Ollama respondio sin completar la generacion"
        }
    } catch {
        Write-Failure "Fallo la generacion Ollama: $($_.Exception.Message)"
    }
}

Write-Host "`n[5/6] Datos locales" -ForegroundColor Cyan
if ($dockerReady) {
    try {
        $counts = docker exec asofamech_db psql -U app_user -d app_db -At -c "SELECT 'usuarios=' || count(*) FROM users; SELECT 'imagenes=' || count(*) FROM medical_images; SELECT 'sct=' || count(*) FROM sct_tests;" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Pass "Base restaurada: $(([string[]]$counts) -join ', ')"
        } else {
            Write-WarningResult "No se pudieron obtener conteos de la base"
        }
    } catch {
        Write-WarningResult "No se pudieron verificar datos locales"
    }
}

Write-Host "`n[6/6] Acceso publico" -ForegroundColor Cyan
if ($PublicUrl) {
    $publicBase = $PublicUrl.TrimEnd("/")
    $platformUrl = Get-EnvValue "ASOFAMECH_PLATFORM_URL"
    if ($platformUrl -eq "$publicBase/auth") {
        Write-Pass "Enlaces de correo apuntan a la URL publica"
    } else {
        Write-WarningResult "ASOFAMECH_PLATFORM_URL no coincide con $publicBase/auth"
    }
    Test-LocalUrl "$publicBase/health" "Health publico" | Out-Null
    Test-LocalUrl $publicBase "Frontend publico" | Out-Null
} else {
    Write-WarningResult "No se proporciono -PublicUrl; falta probar desde otra red o datos moviles"
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
if ($script:failures -eq 0) {
    Write-Host "  LISTA PARA PRESENTACION" -ForegroundColor Green
} else {
    Write-Host "  NO LISTA: $script:failures fallo(s)" -ForegroundColor Red
}
Write-Host "  Avisos: $script:warnings" -ForegroundColor Yellow
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

if ($script:failures -gt 0) { exit 1 }
