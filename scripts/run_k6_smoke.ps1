# run_k6_smoke.ps1
# Ejecuta prueba k6 liviana contra endpoints principales de ASOFAMECH.
# Uso:
#   .\scripts\run_k6_smoke.ps1 -Email "admin@correo.cl" -Password "clave123"
#   .\scripts\run_k6_smoke.ps1 -Vus 10 -Duration "2m" -IncludeAdmin
#   .\scripts\run_k6_smoke.ps1 -IncludeChat

param(
    [string]$BaseUrl = "http://localhost:8001",

    [string]$Email = $env:ASO_EMAIL,

    [string]$Password = $env:ASO_PASSWORD,

    [int]$Vus = 5,

    [string]$Duration = "1m",

    [int]$Iterations = 0,

    [string]$MaxDuration = "10m",

    [switch]$IncludeAdmin,

    [switch]$IncludeChat,

    [int]$ChatP95Ms = 0,

    [switch]$UseDocker,

    [switch]$NoDocker,

    [string]$OutDir = "backend\artifacts\performance"
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectDir

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

function Convert-BaseUrlForDocker($Url) {
    return $Url `
        -replace "^http://localhost", "http://host.docker.internal" `
        -replace "^http://127\.0\.0\.1", "http://host.docker.internal"
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  ASOFAMECH - k6 smoke/load test" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

$testScript = Join-Path $projectDir "load_tests\k6\asofamech_smoke.js"
if (-not (Test-Path -LiteralPath $testScript)) {
    Write-Fail "No existe el escenario k6: $testScript"
    exit 1
}

if (-not $Email) {
    $Email = $env:ASO_EMAIL
}
if (-not $Email) {
    $Email = $env:K6_EMAIL
}
if (-not $Password) {
    $Password = $env:ASO_PASSWORD
}
if (-not $Password) {
    $Password = $env:K6_PASSWORD
}
if (-not $Email) {
    $Email = Read-Host "Correo de usuario aprobado"
}
if (-not $Password) {
    $securePassword = Read-Host "Contrasena" -AsSecureString
    $Password = Convert-SecureStringToPlainText $securePassword
}
if (-not $Email -or -not $Password) {
    Write-Fail "Email y password son obligatorios para probar endpoints protegidos."
    exit 1
}
if ($UseDocker -and $NoDocker) {
    Write-Fail "Usa -UseDocker o -NoDocker, pero no ambos al mismo tiempo."
    exit 1
}

$outputDir = Join-Path $projectDir $OutDir
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryFile = "k6_summary_$timestamp.json"
$summaryPath = Join-Path $outputDir $summaryFile

$localK6 = Get-Command k6 -ErrorAction SilentlyContinue
if ($NoDocker -and -not $localK6) {
    Write-Fail "No se encontro k6 local y -NoDocker esta activo. Instala k6 o quita -NoDocker para usar Docker."
    exit 1
}
$runWithDocker = $UseDocker -or (-not $localK6 -and -not $NoDocker)

Write-Host ""
Write-Host "Configuracion:" -ForegroundColor White
Write-Host "  BaseUrl      : $BaseUrl"
Write-Host "  Usuario      : $Email"
Write-Host "  VUs          : $Vus"
if ($Iterations -gt 0) {
    Write-Host "  Iteraciones  : $Iterations"
    Write-Host "  MaxDuration  : $MaxDuration"
} else {
    Write-Host "  Duracion     : $Duration"
}
Write-Host "  IncludeAdmin : $([bool]$IncludeAdmin)"
Write-Host "  IncludeChat  : $([bool]$IncludeChat)"
if ($IncludeChat) {
    if ($ChatP95Ms -gt 0) {
        Write-Host "  Chat p95 max : $ChatP95Ms ms"
    } else {
        Write-Host "  Chat p95 max : sin umbral estricto"
    }
}
Write-Host "  Resultado    : $summaryPath"

if ($runWithDocker) {
    Write-Warn "k6 local no detectado o -UseDocker activo. Se usara Docker con grafana/k6."
    try {
        docker info | Out-Null
    } catch {
        Write-Fail "Docker no esta corriendo. Instala k6 local o abre Docker Desktop."
        exit 1
    }

    $scriptDir = Split-Path -Parent $testScript
    $dockerBaseUrl = Convert-BaseUrlForDocker $BaseUrl
    docker run --rm `
        -v "${scriptDir}:/scripts:ro" `
        -v "${outputDir}:/results" `
        grafana/k6:0.54.0 run `
        -e "ASO_BASE_URL=$dockerBaseUrl" `
        -e "ASO_EMAIL=$Email" `
        -e "ASO_PASSWORD=$Password" `
        -e "ASO_VUS=$Vus" `
        -e "ASO_DURATION=$Duration" `
        -e "ASO_ITERATIONS=$Iterations" `
        -e "ASO_MAX_DURATION=$MaxDuration" `
        -e "ASO_INCLUDE_ADMIN=$([bool]$IncludeAdmin)" `
        -e "ASO_INCLUDE_CHAT=$([bool]$IncludeChat)" `
        -e "ASO_CHAT_P95_MS=$ChatP95Ms" `
        --summary-export "/results/$summaryFile" `
        /scripts/asofamech_smoke.js
} else {
    Write-OK "Usando k6 local: $($localK6.Source)"
    k6 run `
        -e "ASO_BASE_URL=$BaseUrl" `
        -e "ASO_EMAIL=$Email" `
        -e "ASO_PASSWORD=$Password" `
        -e "ASO_VUS=$Vus" `
        -e "ASO_DURATION=$Duration" `
        -e "ASO_ITERATIONS=$Iterations" `
        -e "ASO_MAX_DURATION=$MaxDuration" `
        -e "ASO_INCLUDE_ADMIN=$([bool]$IncludeAdmin)" `
        -e "ASO_INCLUDE_CHAT=$([bool]$IncludeChat)" `
        -e "ASO_CHAT_P95_MS=$ChatP95Ms" `
        --summary-export $summaryPath `
        $testScript
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-OK "Prueba k6 completada. Resumen guardado en: $summaryPath"
} else {
    Write-Host ""
    Write-Fail "k6 termino con errores. Revisa umbrales, credenciales o disponibilidad del backend."
    exit $LASTEXITCODE
}
