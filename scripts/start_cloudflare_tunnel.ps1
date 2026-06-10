# scripts/start_cloudflare_tunnel.ps1
# Publica ASOFAMECH usando Cloudflare Tunnel (cloudflared).
# Detecta la URL del tunel, actualiza la configuracion publica en .env y
# recrea backend/frontend para que los usuarios externos puedan usar la API.
#
# Prerequisito: instalar cloudflared
#   winget install Cloudflare.cloudflared
#
# Uso:
#   .\scripts\start_cloudflare_tunnel.ps1
#   .\scripts\start_cloudflare_tunnel.ps1 -NoBuild   (no reconstruye imagenes)

param(
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Archivo temporal donde cloudflared escribe sus logs
$cfLogFile = [System.IO.Path]::Combine(
    [System.IO.Path]::GetTempPath(),
    "asofamech_cf_$([System.Diagnostics.Process]::GetCurrentProcess().Id).log"
)

$script:publicUrl      = ""
$script:cfProcess      = $null
$script:cfJob          = $null
$script:cfOutput       = ""
$script:currentJob     = $null
$script:currentJobName = ""

# Buscar cloudflared en rutas comunes si no esta en PATH
$script:cfExe = "cloudflared"
$cfSearchPaths = @(
    "C:\Program Files\cloudflared\cloudflared.exe",
    "C:\Program Files\cloudflare\cloudflared\cloudflared.exe",
    "C:\Program Files\Cloudflare\cloudflared\cloudflared.exe",
    "C:\Program Files (x86)\cloudflared\cloudflared.exe",
    "C:\Program Files (x86)\Cloudflare\cloudflared\cloudflared.exe",
    "C:\ProgramData\cloudflare\cloudflared\cloudflared.exe",
    "C:\ProgramData\Cloudflare\cloudflared.exe"
)
foreach ($candidate in $cfSearchPaths) {
    if (Test-Path -LiteralPath $candidate) {
        $script:cfExe = $candidate
        # Agregar su directorio al PATH de este proceso para que cmd.exe tambien lo encuentre
        $cfDir = Split-Path $candidate
        if ($env:PATH -notlike "*$cfDir*") {
            $env:PATH = "$cfDir;$env:PATH"
        }
        break
    }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# ── Helpers ─────────────────────────────────────────────────────────────────

function Append-Log {
    param([string]$Message)
    if ([string]::IsNullOrWhiteSpace($Message)) { return }
    $stamp = Get-Date -Format "HH:mm:ss"
    $logBox.AppendText("[$stamp] $Message`r`n")
    $logBox.SelectionStart = $logBox.Text.Length
    $logBox.ScrollToCaret()
    [System.Windows.Forms.Application]::DoEvents()
}

function Set-Status {
    param(
        [string]$Text,
        [System.Drawing.Color]$Color = [System.Drawing.Color]::FromArgb(68, 84, 106)
    )
    $statusLabel.Text      = $Text
    $statusLabel.ForeColor = $Color
}

function Invoke-CommandText {
    param([string]$Command, [switch]$Quiet)
    if (-not $Quiet) { Append-Log "> $Command" }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName             = "cmd.exe"
    $psi.Arguments            = "/d /c $Command"
    $psi.WorkingDirectory     = $projectDir
    $psi.UseShellExecute      = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.CreateNoWindow       = $true
    $p   = [System.Diagnostics.Process]::Start($psi)
    $out = $p.StandardOutput.ReadToEnd()
    $err = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    if (-not $Quiet) {
        if ($out) { Append-Log $out.TrimEnd() }
        if ($err) { Append-Log $err.TrimEnd() }
    }
    return @{ ExitCode = $p.ExitCode; StdOut = $out; StdErr = $err }
}

function Test-CommandAvailable {
    param([string]$Cmd)
    return (Invoke-CommandText "where $Cmd" -Quiet).ExitCode -eq 0
}

function Test-CloudflaredAvailable {
    # Devuelve true si cloudflared esta en PATH o en alguna ruta conocida
    if ($script:cfExe -ne "cloudflared") { return $true }
    return (Invoke-CommandText "where cloudflared" -Quiet).ExitCode -eq 0
}

function Get-TunnelUrl {
    foreach ($file in @($cfLogFile, "$cfLogFile.out", "$cfLogFile.err")) {
        if (-not (Test-Path -LiteralPath $file)) { continue }
        try {
            $content = [System.IO.File]::ReadAllText($file)
            if ($content -match 'https://[a-zA-Z0-9\-]+\.(trycloudflare|cfargotunnel)\.com') {
                return $Matches[0].Trim()
            }
        } catch { }
    }
    return ""
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
        Append-Log "Configuracion publica actualizada en .env"
        Append-Log "  CORS -> $corsValue"
        Append-Log "  Plataforma -> $platformUrl"
        Append-Log "  API frontend -> mismo origen (/api)"
        return $true
    } catch {
        Append-Log "ERROR actualizando .env: $($_.Exception.Message)"
        return $false
    }
}

function Restart-ServicesWithPublicSettings {
    Append-Log "Recreando backend y frontend con la URL publica (puede tardar ~20s)..."
    $r = Invoke-CommandText "docker compose up -d --no-deps --force-recreate backend frontend"
    if ($r.ExitCode -eq 0) {
        Append-Log "Backend y frontend recreados para el tunel."
    } else {
        Append-Log "ADVERTENCIA: No se pudieron recrear los servicios automaticamente."
        Append-Log "  Ejecuta: docker compose up -d --no-deps --force-recreate backend frontend"
    }
}

function Refresh-Status {
    $compose = Invoke-CommandText "docker compose ps --services --filter status=running" -Quiet
    $running = @()
    if ($compose.ExitCode -eq 0 -and $compose.StdOut) {
        $running = @($compose.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" })
    }
    $url = if ($script:publicUrl) { $script:publicUrl } else { Get-TunnelUrl }
    if ($url) {
        $script:publicUrl = $url
        $publicText.Text  = $url
    } elseif (-not $script:publicUrl) {
        $publicText.Text = "Sin tunel activo"
    }
    $servicesText.Text = if ($running.Count -gt 0) { $running -join ", " } else { "Sin servicios activos" }

    if (($running -contains "backend") -and ($running -contains "frontend") -and $url) {
        Set-Status "Publicada con Cloudflare" ([System.Drawing.Color]::FromArgb(16, 137, 91))
    } elseif (($running -contains "backend") -and ($running -contains "frontend")) {
        Set-Status "Plataforma local activa" ([System.Drawing.Color]::FromArgb(58, 99, 197))
    } else {
        Set-Status "Pendiente de levantar" ([System.Drawing.Color]::FromArgb(166, 109, 21))
    }
}

function Set-ButtonsEnabled {
    param([bool]$Enabled)
    $btnStart.Enabled      = $Enabled
    $btnPublish.Enabled    = $Enabled
    $btnStop.Enabled       = $Enabled
    $btnRefresh.Enabled    = $Enabled
    $btnCopy.Enabled       = $Enabled
    $btnOpenLocal.Enabled  = $Enabled
    $btnOpenPublic.Enabled = $Enabled
}

function Start-Task {
    param([string]$Name, [scriptblock]$Block)
    if ($script:currentJob -and $script:currentJob.State -eq "Running") {
        Append-Log "Ya hay una tarea en curso: $script:currentJobName"
        return
    }
    Set-ButtonsEnabled $false
    Set-Status "Ejecutando: $Name" ([System.Drawing.Color]::FromArgb(58, 99, 197))
    Append-Log "Iniciando: $Name"
    $script:currentJobName = $Name
    $script:currentJob     = Start-Job -ScriptBlock $Block -ArgumentList $projectDir, [bool]$NoBuild
    $jobTimer.Start()
}

# ── GUI ──────────────────────────────────────────────────────────────────────

$form = New-Object System.Windows.Forms.Form
$form.Text          = "ASOFAMECH - Cloudflare Tunnel"
$form.StartPosition = "CenterScreen"
$form.Size          = New-Object System.Drawing.Size(940, 650)
$form.MinimumSize   = New-Object System.Drawing.Size(820, 580)
$form.BackColor     = [System.Drawing.Color]::FromArgb(247, 248, 250)

$lbTitle = New-Object System.Windows.Forms.Label
$lbTitle.Text     = "ASOFAMECH - Cloudflare Tunnel"
$lbTitle.Font     = New-Object System.Drawing.Font("Segoe UI", 17, [System.Drawing.FontStyle]::Bold)
$lbTitle.Location = New-Object System.Drawing.Point(24, 16)
$lbTitle.Size     = New-Object System.Drawing.Size(580, 34)
$form.Controls.Add($lbTitle)

$lbSub = New-Object System.Windows.Forms.Label
$lbSub.Text      = "Levanta Docker Compose y publica el puerto 3000 con cloudflared. CORS se configura automaticamente."
$lbSub.Font      = New-Object System.Drawing.Font("Segoe UI", 9)
$lbSub.ForeColor = [System.Drawing.Color]::FromArgb(91, 99, 112)
$lbSub.Location  = New-Object System.Drawing.Point(27, 54)
$lbSub.Size      = New-Object System.Drawing.Size(800, 20)
$form.Controls.Add($lbSub)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text      = "Pendiente de levantar"
$statusLabel.Font      = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$statusLabel.Location  = New-Object System.Drawing.Point(670, 22)
$statusLabel.Size      = New-Object System.Drawing.Size(244, 26)
$statusLabel.TextAlign = "MiddleRight"
$form.Controls.Add($statusLabel)

# Panel de informacion
$panel = New-Object System.Windows.Forms.Panel
$panel.Location    = New-Object System.Drawing.Point(24, 82)
$panel.Size        = New-Object System.Drawing.Size(876, 142)
$panel.Anchor      = "Top,Left,Right"
$panel.BackColor   = [System.Drawing.Color]::White
$panel.BorderStyle = "FixedSingle"
$form.Controls.Add($panel)

$lbLocal = New-Object System.Windows.Forms.Label
$lbLocal.Text     = "URL local"
$lbLocal.Location = New-Object System.Drawing.Point(18, 18)
$lbLocal.Size     = New-Object System.Drawing.Size(120, 20)
$lbLocal.Font     = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$panel.Controls.Add($lbLocal)

$localText = New-Object System.Windows.Forms.TextBox
$localText.Text     = "http://localhost:3000"
$localText.Location = New-Object System.Drawing.Point(150, 15)
$localText.Size     = New-Object System.Drawing.Size(706, 24)
$localText.ReadOnly = $true
$panel.Controls.Add($localText)

$lbPublic = New-Object System.Windows.Forms.Label
$lbPublic.Text     = "URL publica"
$lbPublic.Location = New-Object System.Drawing.Point(18, 56)
$lbPublic.Size     = New-Object System.Drawing.Size(120, 20)
$lbPublic.Font     = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$panel.Controls.Add($lbPublic)

$publicText = New-Object System.Windows.Forms.TextBox
$publicText.Text     = "Sin tunel activo"
$publicText.Location = New-Object System.Drawing.Point(150, 53)
$publicText.Size     = New-Object System.Drawing.Size(706, 24)
$publicText.ReadOnly = $true
$panel.Controls.Add($publicText)

$lbSvc = New-Object System.Windows.Forms.Label
$lbSvc.Text     = "Servicios"
$lbSvc.Location = New-Object System.Drawing.Point(18, 94)
$lbSvc.Size     = New-Object System.Drawing.Size(120, 20)
$lbSvc.Font     = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$panel.Controls.Add($lbSvc)

$servicesText = New-Object System.Windows.Forms.TextBox
$servicesText.Text     = "Sin servicios activos"
$servicesText.Location = New-Object System.Drawing.Point(150, 91)
$servicesText.Size     = New-Object System.Drawing.Size(706, 24)
$servicesText.ReadOnly = $true
$panel.Controls.Add($servicesText)

# Botones
$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text     = if ($NoBuild) { "Levantar plataforma" } else { "Levantar / reconstruir" }
$btnStart.Location = New-Object System.Drawing.Point(24, 242)
$btnStart.Size     = New-Object System.Drawing.Size(162, 34)
$form.Controls.Add($btnStart)

$btnPublish = New-Object System.Windows.Forms.Button
$btnPublish.Text     = "Publicar con Cloudflare"
$btnPublish.Location = New-Object System.Drawing.Point(196, 242)
$btnPublish.Size     = New-Object System.Drawing.Size(170, 34)
$form.Controls.Add($btnPublish)

$btnCopy = New-Object System.Windows.Forms.Button
$btnCopy.Text     = "Copiar URL"
$btnCopy.Location = New-Object System.Drawing.Point(376, 242)
$btnCopy.Size     = New-Object System.Drawing.Size(100, 34)
$form.Controls.Add($btnCopy)

$btnOpenLocal = New-Object System.Windows.Forms.Button
$btnOpenLocal.Text     = "Abrir local"
$btnOpenLocal.Location = New-Object System.Drawing.Point(486, 242)
$btnOpenLocal.Size     = New-Object System.Drawing.Size(100, 34)
$form.Controls.Add($btnOpenLocal)

$btnOpenPublic = New-Object System.Windows.Forms.Button
$btnOpenPublic.Text     = "Abrir publica"
$btnOpenPublic.Location = New-Object System.Drawing.Point(596, 242)
$btnOpenPublic.Size     = New-Object System.Drawing.Size(110, 34)
$form.Controls.Add($btnOpenPublic)

$btnStop = New-Object System.Windows.Forms.Button
$btnStop.Text     = "Detener tunel"
$btnStop.Location = New-Object System.Drawing.Point(716, 242)
$btnStop.Size     = New-Object System.Drawing.Size(110, 34)
$form.Controls.Add($btnStop)

$btnRefresh = New-Object System.Windows.Forms.Button
$btnRefresh.Text     = "Estado"
$btnRefresh.Location = New-Object System.Drawing.Point(836, 242)
$btnRefresh.Size     = New-Object System.Drawing.Size(64, 34)
$btnRefresh.Anchor   = "Top,Right"
$form.Controls.Add($btnRefresh)

# Log
$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Location   = New-Object System.Drawing.Point(24, 294)
$logBox.Size       = New-Object System.Drawing.Size(876, 308)
$logBox.Anchor     = "Top,Bottom,Left,Right"
$logBox.Multiline  = $true
$logBox.ScrollBars = "Vertical"
$logBox.ReadOnly   = $true
$logBox.BackColor  = [System.Drawing.Color]::FromArgb(15, 23, 42)
$logBox.ForeColor  = [System.Drawing.Color]::FromArgb(226, 232, 240)
$logBox.Font       = New-Object System.Drawing.Font("Consolas", 9)
$form.Controls.Add($logBox)

# ── Timers ───────────────────────────────────────────────────────────────────

# Vigila jobs de PowerShell en segundo plano (docker compose up, etc.)
$jobTimer = New-Object System.Windows.Forms.Timer
$jobTimer.Interval = 800
$jobTimer.Add_Tick({
    if (-not $script:currentJob) { return }
    $out = Receive-Job -Job $script:currentJob 2>&1
    foreach ($line in $out) { Append-Log ([string]$line) }
    if ($script:currentJob.State -in @("Completed", "Failed", "Stopped")) {
        $state = $script:currentJob.State
        $more  = Receive-Job -Job $script:currentJob 2>&1
        foreach ($line in $more) { Append-Log ([string]$line) }
        if ($state -eq "Completed") {
            Append-Log "Tarea completada: $script:currentJobName"
        } else {
            Append-Log "Tarea finalizada ($state): $script:currentJobName"
        }
        Remove-Job -Job $script:currentJob -Force -ErrorAction SilentlyContinue
        $script:currentJob     = $null
        $script:currentJobName = ""
        $jobTimer.Stop()
        Set-ButtonsEnabled $true
        Refresh-Status
    }
})

# Vigila el PS job de cloudflared leyendo su salida en tiempo real
$cfTimer = New-Object System.Windows.Forms.Timer
$cfTimer.Interval = 1500
$cfTimer.Add_Tick({
    if (-not $script:cfJob) { return }

    # Drenar nueva salida del job y acumularla
    $newLines = @(Receive-Job -Job $script:cfJob 2>&1)
    foreach ($line in $newLines) {
        $str = [string]$line
        if ($str.Trim()) {
            Append-Log "  cf> $str"
            $script:cfOutput += "$str`n"
        }
    }

    # Buscar URL en toda la salida acumulada
    if ($script:cfOutput -match 'https://[a-zA-Z0-9\-]+\.(trycloudflare|cfargotunnel)\.com') {
        $url = $Matches[0].Trim()
        if ($url -ne $script:publicUrl) {
            $cfTimer.Stop()
            $script:publicUrl = $url
            $publicText.Text  = $url
            Append-Log "Tunel Cloudflare activo: $url"

            $ok = Update-EnvPublicSettings -TunnelUrl $url
            if ($ok) { Restart-ServicesWithPublicSettings }
            Refresh-Status

            try {
                $h = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 8
                Append-Log "Health check publico: OK ($($h.status))"
                Append-Log "Plataforma disponible para usuarios externos."
            } catch {
                Append-Log "Health check publico pendiente (~30s para propagar)."
                Append-Log "Espera y haz clic en 'Abrir publica' para verificar."
            }
        }
        return
    }

    # Si el job murio sin entregar URL
    if ($script:cfJob.State -in @("Failed","Completed","Stopped")) {
        Append-Log "cloudflared termino sin entregar URL. Revisa la salida arriba."
        $cfTimer.Stop()
        Remove-Job -Job $script:cfJob -Force -ErrorAction SilentlyContinue
        $script:cfJob = $null
        Refresh-Status
    }
})

# ── Handlers de botones ───────────────────────────────────────────────────────

$btnStart.Add_Click({
    if (-not (Test-CommandAvailable "docker")) {
        Append-Log "docker CLI no esta en PATH. Instala Docker Desktop."
        return
    }
    Start-Task "Levantar Docker Compose" {
        param($ProjectDir, $NoBuildFlag)
        Set-Location $ProjectDir
        $ddExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        if (Test-Path -LiteralPath $ddExe) {
            Start-Process -FilePath $ddExe -WindowStyle Hidden
            "Docker Desktop solicitado."
        }
        $deadline = (Get-Date).AddMinutes(3)
        do {
            docker info --format "{{.ServerVersion}}" 2>$null | ForEach-Object { "Docker daemon listo: $_" }
            if ($LASTEXITCODE -eq 0) { break }
            "Esperando Docker daemon..."
            Start-Sleep -Seconds 3
        } while ((Get-Date) -lt $deadline)
        if ($LASTEXITCODE -ne 0) { throw "Docker daemon no disponible." }
        if ($NoBuildFlag) {
            docker compose up -d 2>&1 | ForEach-Object { $_.ToString() }
        } else {
            docker compose up -d --build 2>&1 | ForEach-Object { $_.ToString() }
        }
        if ($LASTEXITCODE -ne 0) { throw "docker compose up fallo." }
        docker compose ps 2>&1 | ForEach-Object { $_.ToString() }
    }
})

$btnPublish.Add_Click({
    if (-not (Test-CloudflaredAvailable)) {
        $msg = @"
cloudflared no esta en PATH ni en rutas conocidas.

Instala con winget (recomendado):
  winget install Cloudflare.cloudflared

O descarga el instalador .msi desde:
  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

Despues de instalar, reinicia esta ventana.
"@
        [System.Windows.Forms.MessageBox]::Show(
            $msg, "cloudflared no encontrado",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Warning
        ) | Out-Null
        return
    }
    Append-Log "Usando cloudflared: $($script:cfExe)"

    # Si ya hay un tunel activo, mostrar URL y salir
    if ($script:cfProcess -and -not $script:cfProcess.HasExited) {
        $url = Get-TunnelUrl
        if ($url) {
            Append-Log "cloudflared ya esta activo: $url"
        } else {
            Append-Log "cloudflared ya corre, esperando URL del tunel..."
        }
        return
    }

    $script:publicUrl = ""
    $publicText.Text  = "Iniciando tunel Cloudflare..."

    Append-Log "Iniciando cloudflared -> http://localhost:3000"
    Append-Log "La URL del tunel puede tardar hasta 30 segundos en aparecer..."
    try {
        # Detener servicio cloudflared si esta corriendo (instalado por el wizard de Cloudflare)
        $svc = Get-Service cloudflared -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -eq "Running") {
            Append-Log "Deteniendo servicio cloudflared en segundo plano..."
            Stop-Service cloudflared -ErrorAction SilentlyContinue
        }
        # Matar procesos cloudflared existentes
        Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 800

        $script:cfOutput = ""
        $cfExePath = $script:cfExe
        $script:cfJob = Start-Job -ScriptBlock {
            param($exe)
            & $exe tunnel --url http://localhost:3000 --no-autoupdate --loglevel info 2>&1
        } -ArgumentList $cfExePath

        Append-Log "cloudflared iniciado. La salida aparecera a continuacion:"
        $cfTimer.Start()
    } catch {
        Append-Log "Error al iniciar cloudflared: $($_.Exception.Message)"
        $publicText.Text = "Sin tunel activo"
    }
})

$btnStop.Add_Click({
    Append-Log "Deteniendo tunel Cloudflare..."
    $cfTimer.Stop()
    if ($script:cfJob) {
        Stop-Job  -Job $script:cfJob -ErrorAction SilentlyContinue
        Remove-Job -Job $script:cfJob -Force -ErrorAction SilentlyContinue
        $script:cfJob = $null
    }
    if ($script:cfProcess -and -not $script:cfProcess.HasExited) {
        try { $script:cfProcess.Kill() } catch { }
    }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    $script:cfProcess = $null
    $script:cfOutput  = ""
    $script:publicUrl = ""
    $publicText.Text  = "Sin tunel activo"
    Append-Log "Tunel detenido."
    Refresh-Status
})

$btnCopy.Add_Click({
    $url = if ($script:publicUrl) { $script:publicUrl } else { Get-TunnelUrl }
    if (-not $url) { Append-Log "No hay URL publica disponible."; return }
    [System.Windows.Forms.Clipboard]::SetText($url)
    Append-Log "URL copiada al portapapeles: $url"
})

$btnOpenLocal.Add_Click({
    Start-Process "http://localhost:3000"
})

$btnOpenPublic.Add_Click({
    $url = if ($script:publicUrl) { $script:publicUrl } else { Get-TunnelUrl }
    if (-not $url) { Append-Log "No hay URL publica activa."; return }
    Start-Process $url
})

$btnRefresh.Add_Click({
    Refresh-Status
    Append-Log "Estado actualizado."
})

$form.Add_Shown({
    Append-Log "Directorio del proyecto: $projectDir"
    Append-Log ""
    Append-Log "Orden recomendado:"
    Append-Log "  1. Levantar / reconstruir   <- inicia Docker Compose"
    Append-Log "  2. Publicar con Cloudflare  <- crea tunel y configura CORS automaticamente"
    Append-Log "  3. Copiar URL y compartir con los usuarios"
    Append-Log ""
    Append-Log "NOTA: cada sesion genera una URL aleatoria *.trycloudflare.com."
    Append-Log "Para URL fija permanente, crea un Named Tunnel en:"
    Append-Log "  https://one.dash.cloudflare.com -> Zero Trust -> Networks -> Tunnels"
    Append-Log ""
    Refresh-Status
})

$form.Add_FormClosing({
    $cfTimer.Stop()
    $jobTimer.Stop()
    if ($script:cfJob) {
        Stop-Job  -Job $script:cfJob -ErrorAction SilentlyContinue
        Remove-Job -Job $script:cfJob -Force -ErrorAction SilentlyContinue
    }
    if ($script:cfProcess -and -not $script:cfProcess.HasExited) {
        try { $script:cfProcess.Kill() } catch { }
    }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    foreach ($f in @($cfLogFile, "$cfLogFile.out", "$cfLogFile.err")) {
        if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue }
    }
})

[void]$form.ShowDialog()
