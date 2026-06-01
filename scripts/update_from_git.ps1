# update_from_git.ps1
# Aplica una actualizacion normal de ASOFAMECH desde GitHub.
# Uso:
#   .\scripts\update_from_git.ps1
#   .\scripts\update_from_git.ps1 -Branch main
#   .\scripts\update_from_git.ps1 -SkipGitPull
#   .\scripts\update_from_git.ps1 -BackendOnly
#   .\scripts\update_from_git.ps1 -FrontendOnly

param(
    [switch]$SkipGitPull,

    [switch]$SkipBuild,

    [switch]$BackendOnly,

    [switch]$FrontendOnly,

    [switch]$NoBrowser,

    [string]$Remote = "origin",

    [string]$Branch = "",

    [int]$HealthRetries = 45
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

if ($BackendOnly -and $FrontendOnly) {
    Write-Fail "Usa -BackendOnly o -FrontendOnly, pero no ambos al mismo tiempo."
    exit 1
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  ASOFAMECH - Actualizacion normal desde GitHub" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

Write-Step 1 4 "Verificando prerequisitos"
try {
    git --version | Out-Null
    Write-OK "Git disponible"
} catch {
    Write-Fail "Git no esta disponible en PATH."
    exit 1
}

try {
    docker info | Out-Null
    Write-OK "Docker en ejecucion"
} catch {
    Write-Fail "Docker no esta corriendo. Abre Docker Desktop y vuelve a ejecutar."
    exit 1
}

Write-Step 2 4 "Actualizando codigo y migraciones desde Git"
if ($SkipGitPull) {
    Write-Warn "Se omitio git pull por -SkipGitPull."
} else {
    $dirty = @(git status --porcelain)
    if ($dirty.Count -gt 0) {
        Write-Warn "Hay cambios locales sin commitear. git pull puede fallar si hay conflictos."
        Write-Host "  Revisa con: git status" -ForegroundColor Yellow
    }

    $pullArgs = @("pull", "--ff-only")
    if ($Remote -and $Branch) {
        $pullArgs += @($Remote, $Branch)
    }

    & git @pullArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "git pull fallo. Resuelve el conflicto o actualiza manualmente antes de continuar."
        exit 1
    }
    Write-OK "Repositorio actualizado"
}

Write-Step 3 4 "Reconstruyendo servicios necesarios"
if ($SkipBuild) {
    Write-Warn "Se omitio docker compose up --build por -SkipBuild."
} else {
    if ($BackendOnly) {
        $services = @("backend")
    } elseif ($FrontendOnly) {
        $services = @("frontend")
    } else {
        $services = @("backend", "frontend")
    }

    $composeArgs = @("compose", "up", "-d", "--build") + $services
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "No se pudieron reconstruir los servicios Docker."
        exit 1
    }
    Write-OK "Servicios reconstruidos: $($services -join ', ')"
}

Write-Step 4 4 "Verificando servicios"
docker compose ps

if (-not $FrontendOnly) {
    Wait-Url "http://localhost:8001/health" "Backend" $HealthRetries | Out-Null
}
if (-not $BackendOnly) {
    Wait-Url "http://localhost:3000" "Frontend" $HealthRetries | Out-Null
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  ACTUALIZACION NORMAL COMPLETADA" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Git actualizo codigo y migraciones. El backend aplica Alembic al iniciar." -ForegroundColor White
Write-Host "Los datos reales no viajan por Git; para eso usa migrate_export.ps1 y start_presentation.ps1." -ForegroundColor Yellow
Write-Host ""

if (-not $NoBrowser -and -not $BackendOnly) {
    Start-Process "http://localhost:3000"
}
