# scripts/startup_auto.ps1
# Se ejecuta automaticamente al iniciar sesion via Tarea Programada de Windows.
# Levanta Docker Compose, inicia cloudflared quick tunnel y configura CORS sin intervencion.
#
# Registrar con: .\scripts\register_startup_task.ps1  (como Administrador)
# Ver logs en:   .\logs\startup_auto.log

param()

$ErrorActionPreference = "SilentlyContinue"
$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$logDir     = Join-Path $projectDir "logs"
$logFile    = Join-Path $logDir "startup_auto.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log {
    param([string]$Msg)
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Msg"
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
}

function Update-EnvPublicSettings {
    param([string]$TunnelUrl)
    $envPath      = Join-Path $projectDir ".env"
    $localOrigins = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
    $corsValue    = "$localOrigins,$TunnelUrl"
    $platformUrl  = "$TunnelUrl/auth"
    $utf8NoBom    = New-Object System.Text.UTF8Encoding $false
    try {
        if (Test-Path -LiteralPath $envPath) {
            $lines  = [System.IO.File]::ReadAllLines($envPath)
            $foundCors = $false
            $foundPlatform = $false
            $foundFrontend = $false
            $result = [System.Collections.Generic.List[string]]::new()
            foreach ($line in $lines) {
                if ($line -match '^CORS_ORIGINS=') {
                    $result.Add("CORS_ORIGINS=$corsValue")
                    $foundCors = $true
                } elseif ($line -match '^ASOFAMECH_PLATFORM_URL=') {
                    $result.Add("ASOFAMECH_PLATFORM_URL=$platformUrl")
                    $foundPlatform = $true
                } elseif ($line -match '^FRONTEND_API_BASE=') {
                    $result.Add("FRONTEND_API_BASE=")
                    $foundFrontend = $true
                } else {
                    $result.Add($line)
                }
            }
            if (-not $foundCors) { $result.Add("CORS_ORIGINS=$corsValue") }
            if (-not $foundPlatform) { $result.Add("ASOFAMECH_PLATFORM_URL=$platformUrl") }
            if (-not $foundFrontend) { $result.Add("FRONTEND_API_BASE=") }
            [System.IO.File]::WriteAllLines($envPath, $result, $utf8NoBom)
        } else {
            $content = @(
                "CORS_ORIGINS=$corsValue"
                "ASOFAMECH_PLATFORM_URL=$platformUrl"
                "FRONTEND_API_BASE="
            ) -join "`n"
            [System.IO.File]::WriteAllText($envPath, "$content`n", $utf8NoBom)
        }
        Write-Log "Configuracion publica actualizada: CORS=$corsValue; plataforma=$platformUrl; API frontend=mismo origen"
        return $true
    } catch {
        Write-Log "ERROR actualizando .env: $($_.Exception.Message)"
        return $false
    }
}

# ── Buscar cloudflared ──────────────────────────────────────────────────────

$cfExe = "cloudflared"
foreach ($candidate in @(
    "C:\Program Files\cloudflared\cloudflared.exe",
    "C:\Program Files\cloudflare\cloudflared\cloudflared.exe",
    "C:\Program Files\Cloudflare\cloudflared\cloudflared.exe"
)) {
    if (Test-Path -LiteralPath $candidate) { $cfExe = $candidate; break }
}

# ── Inicio ──────────────────────────────────────────────────────────────────

Write-Log "=========================================="
Write-Log "ASOFAMECH - Inicio automatico"
Write-Log "Directorio: $projectDir"
Write-Log "cloudflared: $cfExe"
Write-Log "=========================================="

Set-Location $projectDir

# Esperar 30s para que Windows y Docker Desktop terminen de cargar
Write-Log "Esperando 30s para que el sistema termine de cargar..."
Start-Sleep -Seconds 30

# ── Paso 1: Iniciar Docker Desktop si no esta corriendo ────────────────────

$ddExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path -LiteralPath $ddExe) {
    $ddRunning = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
    if (-not $ddRunning) {
        Write-Log "Iniciando Docker Desktop..."
        Start-Process -FilePath $ddExe -WindowStyle Hidden
    }
}

# ── Paso 2: Esperar Docker daemon (hasta 5 minutos) ────────────────────────

Write-Log "Esperando Docker daemon..."
$deadline    = (Get-Date).AddMinutes(5)
$dockerReady = $false
while ((Get-Date) -lt $deadline) {
    $ver = & docker info --format "{{.ServerVersion}}" 2>$null
    if ($LASTEXITCODE -eq 0 -and $ver) {
        Write-Log "Docker daemon listo: v$ver"
        $dockerReady = $true
        break
    }
    Start-Sleep -Seconds 8
}

if (-not $dockerReady) {
    Write-Log "ERROR: Docker daemon no estuvo disponible en 5 minutos. Abortando."
    exit 1
}

# ── Paso 3: Levantar Docker Compose ────────────────────────────────────────

Write-Log "Levantando Docker Compose..."
$out = & docker compose up -d 2>&1 | Out-String
Write-Log $out.Trim()
if ($LASTEXITCODE -ne 0) {
    Write-Log "ERROR: docker compose up fallo. Abortando."
    exit 1
}
Write-Log "Docker Compose levantado correctamente."

# ── Paso 4: Esperar que el backend este saludable ──────────────────────────

Write-Log "Esperando backend (hasta 3 minutos)..."
$deadline2 = (Get-Date).AddMinutes(3)
$backendOk = $false
while ((Get-Date) -lt $deadline2) {
    try {
        $h = Invoke-RestMethod -Uri "http://localhost:8001/health" -TimeoutSec 4
        if ($h.status -eq "ok") { $backendOk = $true; break }
    } catch { }
    Start-Sleep -Seconds 6
}
if ($backendOk) {
    Write-Log "Backend saludable."
} else {
    Write-Log "ADVERTENCIA: Backend no respondio en 3 minutos. Continuando de todas formas..."
}

# ── Paso 5: Iniciar cloudflared quick tunnel ───────────────────────────────

# No iniciar si ya hay uno corriendo
$existing = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($existing) {
    Write-Log "cloudflared ya esta corriendo (PID $($existing.Id)). Salteando."
} else {
    Write-Log "Iniciando cloudflared quick tunnel..."
    $cfStdout = Join-Path $logDir "cloudflared.stdout.log"
    $cfStderr = Join-Path $logDir "cloudflared.stderr.log"
    Remove-Item -LiteralPath $cfStdout, $cfStderr -Force -ErrorAction SilentlyContinue
    $cfProcess = Start-Process `
        -FilePath $cfExe `
        -ArgumentList @("tunnel", "--url", "http://localhost:3000", "--no-autoupdate", "--loglevel", "info") `
        -WindowStyle Hidden `
        -RedirectStandardOutput $cfStdout `
        -RedirectStandardError $cfStderr `
        -PassThru
    Write-Log "cloudflared iniciado como proceso persistente (PID $($cfProcess.Id))."

    # ── Paso 6: Esperar URL del tunel (hasta 90 segundos) ──────────────────

    $tunnelUrl = ""
    $cfOutput  = ""
    $deadline3 = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline3) {
        Start-Sleep -Seconds 3
        $cfOutput = ""
        foreach ($path in @($cfStdout, $cfStderr)) {
            if (Test-Path -LiteralPath $path) {
                $cfOutput += [System.IO.File]::ReadAllText($path)
            }
        }
        if ($cfOutput -match 'https://[a-zA-Z0-9\-]+\.(trycloudflare|cfargotunnel)\.com') {
            $tunnelUrl = $Matches[0].Trim()
            Write-Log "URL del tunel obtenida: $tunnelUrl"
            break
        }
        if ($cfProcess.HasExited) {
            Write-Log "ERROR: cloudflared termino sin entregar URL."
            break
        }
    }

    if (-not $tunnelUrl) {
        Write-Log "ADVERTENCIA: No se obtuvo URL del tunel. El sistema queda disponible solo localmente."
        exit 0
    }

    # ── Paso 7: Actualizar CORS y reiniciar backend ────────────────────────

    $ok = Update-EnvPublicSettings -TunnelUrl $tunnelUrl
    if ($ok) {
        Write-Log "Recreando backend y frontend para aplicar la configuracion publica..."
        $r = & docker compose up -d --no-deps --force-recreate backend frontend 2>&1 | Out-String
        Write-Log $r.Trim()
        Write-Log "Backend y frontend recreados con configuracion publica."
    }

    Write-Log "=========================================="
    Write-Log "Sistema listo."
    Write-Log "URL local  : http://localhost:3000"
    Write-Log "URL publica: $tunnelUrl"
    Write-Log "=========================================="
}
