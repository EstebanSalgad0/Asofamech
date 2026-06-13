# run_k6_ai.ps1  — Mide tiempos reales de IA (chat Ollama + histopatología ML)
#
# Uso:
#   .\scripts\run_k6_ai.ps1 -Email "..." -Password "..."
#   .\scripts\run_k6_ai.ps1 -Profile histo_solo    -Email "..." -Password "..."
#   .\scripts\run_k6_ai.ps1 -Profile combined       -Email "..." -Password "..."
#
# Perfiles: chat_solo | chat_concurrent | histo_solo | histo_concurrent | combined

param(
    [string]$BaseUrl  = "http://localhost:8001",
    [string]$Email    = $env:ASO_EMAIL,
    [string]$Password = $env:ASO_PASSWORD,
    [ValidateSet("chat_solo","chat_concurrent","histo_solo","histo_concurrent","combined")]
    [string]$Profile  = "chat_solo",
    [string]$ChatText = "¿Qué es una biopsia? Responde en máximo 2 oraciones.",
    [string]$OutDir   = "backend\artifacts\performance"
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectDir

function Convert-BaseUrlForDocker($Url) {
    $Url -replace "^http://localhost",   "http://host.docker.internal" `
         -replace "^http://127\.0\.0\.1","http://host.docker.internal"
}

if (-not $Email)    { $Email    = Read-Host "Email del usuario" }
if (-not $Password) { $Password = Read-Host "Contrasena" }

$outputDir   = Join-Path $projectDir $OutDir
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
$timestamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryFile = "k6_ai_${Profile}_${timestamp}.json"
$summaryPath = Join-Path $outputDir $summaryFile

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ASOFAMECH - k6 AI test [$Profile]" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  URL     : $BaseUrl"
Write-Host "  Perfil  : $Profile"
Write-Host "  Resultado: $summaryPath"
Write-Host ""

$scriptDir     = Join-Path $projectDir "load_tests\k6"
$dockerBaseUrl = Convert-BaseUrlForDocker $BaseUrl

docker run --rm `
    -v "${scriptDir}:/scripts:ro" `
    -v "${outputDir}:/results" `
    grafana/k6:0.54.0 run `
    -e "ASO_BASE_URL=$dockerBaseUrl" `
    -e "ASO_EMAIL=$Email" `
    -e "ASO_PASSWORD=$Password" `
    -e "ASO_AI_PROFILE=$Profile" `
    -e "ASO_CHAT_TEXT=$ChatText" `
    --summary-export "/results/$summaryFile" `
    /scripts/asofamech_ai.js

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "  OK  Prueba AI completada. JSON: $summaryPath" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  ERROR  k6 termino con codigo $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
