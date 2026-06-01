# scripts/register_startup_task.ps1
# Registra startup_auto.ps1 como tarea programada que se ejecuta al iniciar sesion.
# EJECUTAR COMO ADMINISTRADOR.
#
# Uso:
#   .\scripts\register_startup_task.ps1           <- registrar
#   .\scripts\register_startup_task.ps1 -Remove   <- eliminar la tarea

param(
    [switch]$Remove
)

$taskName   = "ASOFAMECH_Startup"
$scriptPath = Join-Path $PSScriptRoot "startup_auto.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarea '$taskName' eliminada." -ForegroundColor Yellow
    exit 0
}

# Verificar que el script existe
if (-not (Test-Path -LiteralPath $scriptPath)) {
    Write-Host "ERROR: No se encontro startup_auto.ps1 en $scriptPath" -ForegroundColor Red
    exit 1
}

# Verificar que se ejecuta como administrador
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Host "ERROR: Este script debe ejecutarse como Administrador." -ForegroundColor Red
    Write-Host "Haz clic derecho en PowerShell y elige 'Ejecutar como administrador'." -ForegroundColor Yellow
    exit 1
}

# Accion: ejecutar PowerShell con el script de inicio
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""

# Disparador: al iniciar sesion el usuario actual
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Configuracion: hasta 30 min de ejecucion, reintentar 2 veces si falla
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit  (New-TimeSpan -Minutes 30) `
    -RestartCount        2 `
    -RestartInterval     (New-TimeSpan -Minutes 3) `
    -StartWhenAvailable  $true

# Principal: usuario actual con privilegios elevados
$principal = New-ScheduledTaskPrincipal `
    -UserId   $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

# Registrar (o actualizar si ya existe)
Register-ScheduledTask `
    -TaskName  $taskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "  Tarea programada registrada con exito" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Nombre  : $taskName" -ForegroundColor White
Write-Host "  Trigger : Al iniciar sesion ($env:USERNAME)" -ForegroundColor White
Write-Host "  Script  : $scriptPath" -ForegroundColor White
Write-Host ""
Write-Host "  Logs del inicio automatico:" -ForegroundColor Cyan
Write-Host "  $(Split-Path $scriptPath)\..\..\logs\startup_auto.log" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Para eliminar la tarea:" -ForegroundColor Yellow
Write-Host "  .\scripts\register_startup_task.ps1 -Remove" -ForegroundColor Yellow
Write-Host ""
