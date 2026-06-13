param(
    [switch]$NoBuild
)

$ErrorActionPreference = "Continue"
$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script:currentJob = $null
$script:currentJobName = ""
$script:publicUrl = ""
$script:cfProcess = $null
$script:inDoEvents = $false
$script:cfLogFile = "$env:TEMP\cf_tunnel.log"
$script:cfExe = "cloudflared"

foreach ($candidate in @(
    "C:\Program Files\cloudflared\cloudflared.exe",
    "C:\Program Files\cloudflare\cloudflared\cloudflared.exe",
    "C:\Program Files\Cloudflare\cloudflared.exe",
    "C:\Program Files\Cloudflare\cloudflared\cloudflared.exe",
    "C:\Program Files (x86)\cloudflared\cloudflared.exe"
)) {
    if (Test-Path -LiteralPath $candidate) {
        $script:cfExe = $candidate
        break
    }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Append-Log {
    param([string]$Message)
    if ([string]::IsNullOrWhiteSpace($Message)) { return }
    $stamp = Get-Date -Format "HH:mm:ss"
    $logBox.AppendText("[$stamp] $Message`r`n")
    $logBox.SelectionStart = $logBox.Text.Length
    $logBox.ScrollToCaret()
    if (-not $script:inDoEvents) {
        $script:inDoEvents = $true
        try { [System.Windows.Forms.Application]::DoEvents() } finally { $script:inDoEvents = $false }
    }
}

function Set-Status {
    param(
        [string]$Text,
        [System.Drawing.Color]$Color = [System.Drawing.Color]::FromArgb(68, 84, 106)
    )
    $statusLabel.Text = $Text
    $statusLabel.ForeColor = $Color
}

function Invoke-CommandText {
    param(
        [string]$Command,
        [switch]$Quiet
    )
    if (-not $Quiet) { Append-Log "> $Command" }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "cmd.exe"
    $psi.Arguments = "/d /c $Command"
    $psi.WorkingDirectory = $projectDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $process = [System.Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if (-not $Quiet) {
        if ($stdout) { Append-Log ($stdout.TrimEnd()) }
        if ($stderr) { Append-Log ($stderr.TrimEnd()) }
    }
    return @{ ExitCode = $process.ExitCode; StdOut = $stdout; StdErr = $stderr }
}

function Test-CommandAvailable {
    param([string]$Command)
    $result = Invoke-CommandText "where $Command" -Quiet
    return $result.ExitCode -eq 0
}

function Test-CloudflaredAvailable {
    if ($script:cfExe -ne "cloudflared") { return $true }
    return Test-CommandAvailable "cloudflared"
}

function Update-EnvPublicSettings {
    param([string]$TunnelUrl)
    $envPath = Join-Path $projectDir ".env"
    $localOrigins = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
    $settings = [ordered]@{
        CORS_ORIGINS = "$localOrigins,$TunnelUrl"
        ASOFAMECH_PLATFORM_URL = "$TunnelUrl/auth"
        FRONTEND_API_BASE = ""
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    try {
        $lines = if (Test-Path -LiteralPath $envPath) {
            [System.IO.File]::ReadAllLines($envPath)
        } else {
            @()
        }
        $seen = @{}
        $result = [System.Collections.Generic.List[string]]::new()
        foreach ($line in $lines) {
            $matched = $false
            foreach ($key in $settings.Keys) {
                if ($line -match "^$key=") {
                    $result.Add("$key=$($settings[$key])")
                    $seen[$key] = $true
                    $matched = $true
                    break
                }
            }
            if (-not $matched) { $result.Add($line) }
        }
        foreach ($key in $settings.Keys) {
            if (-not $seen.ContainsKey($key)) {
                $result.Add("$key=$($settings[$key])")
            }
        }
        [System.IO.File]::WriteAllLines($envPath, $result, $utf8NoBom)
        Append-Log "Configuracion publica aplicada: API por mismo origen y enlaces en $TunnelUrl"
        return $true
    } catch {
        Append-Log "No se pudo actualizar .env: $($_.Exception.Message)"
        return $false
    }
}

function Get-CloudflaredUrl {
    if ($script:publicUrl) { return $script:publicUrl }
    $files = @($script:cfLogFile, "$env:TEMP\cf_tunnel_out.log") | Where-Object { Test-Path $_ -ErrorAction SilentlyContinue }
    foreach ($f in $files) {
        try {
            $fs = [System.IO.File]::Open($f, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            $reader = New-Object System.IO.StreamReader($fs)
            try {
                $content = $reader.ReadToEnd()
                if ($content -match "https://[a-z0-9\-]+\.trycloudflare\.com") {
                    return $Matches[0]
                }
            } finally {
                $reader.Dispose()
                $fs.Dispose()
            }
        } catch { }
    }
    return ""
}

function Refresh-Status {
    $compose = Invoke-CommandText "docker compose ps --services --filter status=running" -Quiet
    $running = @()
    if ($compose.ExitCode -eq 0 -and $compose.StdOut) {
        $running = @($compose.StdOut -split "`r?`n" | Where-Object { $_.Trim() -ne "" })
    }

    $url = Get-CloudflaredUrl
    if ($url) {
        $script:publicUrl = $url
        $publicText.Text = $url
    } elseif (-not $script:publicUrl) {
        $publicText.Text = "Sin tunel activo"
    }

    $servicesText.Text = if ($running.Count -gt 0) { $running -join ", " } else { "Sin servicios activos detectados" }
    if ($running -contains "backend" -and $running -contains "frontend" -and $url) {
        Set-Status "Plataforma publicada" ([System.Drawing.Color]::FromArgb(16, 137, 91))
    } elseif ($running -contains "backend" -and $running -contains "frontend") {
        Set-Status "Plataforma local activa" ([System.Drawing.Color]::FromArgb(58, 99, 197))
    } else {
        Set-Status "Pendiente de levantar" ([System.Drawing.Color]::FromArgb(166, 109, 21))
    }
}

function Set-ButtonsEnabled {
    param([bool]$Enabled)
    $btnStart.Enabled = $Enabled
    $btnPublish.Enabled = $Enabled
    $btnStopNgrok.Enabled = $Enabled
    $btnRefresh.Enabled = $Enabled
    $btnCopy.Enabled = $Enabled
    $btnOpenLocal.Enabled = $Enabled
    $btnOpenPublic.Enabled = $Enabled
}

function Start-Task {
    param(
        [string]$Name,
        [scriptblock]$ScriptBlock
    )
    if ($script:currentJob -and $script:currentJob.State -eq "Running") {
        Append-Log "Ya hay una tarea en ejecucion: $script:currentJobName"
        return
    }
    Set-ButtonsEnabled $false
    Set-Status "Ejecutando: $Name" ([System.Drawing.Color]::FromArgb(58, 99, 197))
    Append-Log "Iniciando: $Name"
    $script:currentJobName = $Name
    $script:currentJob = Start-Job -ScriptBlock $ScriptBlock -ArgumentList $projectDir, [bool]$NoBuild
    $timer.Start()
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "ASOFAMECH - Publicador de plataforma"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(920, 620)
$form.MinimumSize = New-Object System.Drawing.Size(820, 560)
$form.BackColor = [System.Drawing.Color]::FromArgb(247, 248, 250)

$title = New-Object System.Windows.Forms.Label
$title.Text = "ASOFAMECH Public Server"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 18, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(24, 18)
$title.Size = New-Object System.Drawing.Size(520, 36)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "Levanta Docker Compose y publica el puerto 3000 con Cloudflare."
$subtitle.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(91, 99, 112)
$subtitle.Location = New-Object System.Drawing.Point(27, 56)
$subtitle.Size = New-Object System.Drawing.Size(620, 24)
$form.Controls.Add($subtitle)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "Pendiente de levantar"
$statusLabel.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$statusLabel.Location = New-Object System.Drawing.Point(690, 24)
$statusLabel.Size = New-Object System.Drawing.Size(190, 26)
$statusLabel.TextAlign = "MiddleRight"
$form.Controls.Add($statusLabel)

$panel = New-Object System.Windows.Forms.Panel
$panel.Location = New-Object System.Drawing.Point(24, 96)
$panel.Size = New-Object System.Drawing.Size(856, 142)
$panel.Anchor = "Top,Left,Right"
$panel.BackColor = [System.Drawing.Color]::White
$panel.BorderStyle = "FixedSingle"
$form.Controls.Add($panel)

$localLabel = New-Object System.Windows.Forms.Label
$localLabel.Text = "URL local"
$localLabel.Location = New-Object System.Drawing.Point(18, 18)
$localLabel.Size = New-Object System.Drawing.Size(120, 20)
$localLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$panel.Controls.Add($localLabel)

$localText = New-Object System.Windows.Forms.TextBox
$localText.Text = "http://localhost:3000"
$localText.Location = New-Object System.Drawing.Point(150, 15)
$localText.Size = New-Object System.Drawing.Size(660, 24)
$localText.ReadOnly = $true
$panel.Controls.Add($localText)

$publicLabel = New-Object System.Windows.Forms.Label
$publicLabel.Text = "URL publica"
$publicLabel.Location = New-Object System.Drawing.Point(18, 56)
$publicLabel.Size = New-Object System.Drawing.Size(120, 20)
$publicLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$panel.Controls.Add($publicLabel)

$publicText = New-Object System.Windows.Forms.TextBox
$publicText.Text = "Sin tunel activo"
$publicText.Location = New-Object System.Drawing.Point(150, 53)
$publicText.Size = New-Object System.Drawing.Size(660, 24)
$publicText.ReadOnly = $true
$panel.Controls.Add($publicText)

$servicesLabel = New-Object System.Windows.Forms.Label
$servicesLabel.Text = "Servicios"
$servicesLabel.Location = New-Object System.Drawing.Point(18, 94)
$servicesLabel.Size = New-Object System.Drawing.Size(120, 20)
$servicesLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$panel.Controls.Add($servicesLabel)

$servicesText = New-Object System.Windows.Forms.TextBox
$servicesText.Text = "Sin servicios activos detectados"
$servicesText.Location = New-Object System.Drawing.Point(150, 91)
$servicesText.Size = New-Object System.Drawing.Size(660, 24)
$servicesText.ReadOnly = $true
$panel.Controls.Add($servicesText)

$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = if ($NoBuild) { "Levantar plataforma" } else { "Levantar / reconstruir" }
$btnStart.Location = New-Object System.Drawing.Point(24, 256)
$btnStart.Size = New-Object System.Drawing.Size(150, 34)
$form.Controls.Add($btnStart)

$btnPublish = New-Object System.Windows.Forms.Button
$btnPublish.Text = "Publicar con Cloudflare"
$btnPublish.Location = New-Object System.Drawing.Point(184, 256)
$btnPublish.Size = New-Object System.Drawing.Size(150, 34)
$form.Controls.Add($btnPublish)

$btnCopy = New-Object System.Windows.Forms.Button
$btnCopy.Text = "Copiar URL"
$btnCopy.Location = New-Object System.Drawing.Point(344, 256)
$btnCopy.Size = New-Object System.Drawing.Size(110, 34)
$form.Controls.Add($btnCopy)

$btnOpenLocal = New-Object System.Windows.Forms.Button
$btnOpenLocal.Text = "Abrir local"
$btnOpenLocal.Location = New-Object System.Drawing.Point(464, 256)
$btnOpenLocal.Size = New-Object System.Drawing.Size(100, 34)
$form.Controls.Add($btnOpenLocal)

$btnOpenPublic = New-Object System.Windows.Forms.Button
$btnOpenPublic.Text = "Abrir publica"
$btnOpenPublic.Location = New-Object System.Drawing.Point(574, 256)
$btnOpenPublic.Size = New-Object System.Drawing.Size(110, 34)
$form.Controls.Add($btnOpenPublic)

$btnStopNgrok = New-Object System.Windows.Forms.Button
$btnStopNgrok.Text = "Detener tunel"
$btnStopNgrok.Location = New-Object System.Drawing.Point(694, 256)
$btnStopNgrok.Size = New-Object System.Drawing.Size(120, 34)
$form.Controls.Add($btnStopNgrok)

$btnRefresh = New-Object System.Windows.Forms.Button
$btnRefresh.Text = "Estado"
$btnRefresh.Location = New-Object System.Drawing.Point(824, 256)
$btnRefresh.Size = New-Object System.Drawing.Size(56, 34)
$btnRefresh.Anchor = "Top,Right"
$form.Controls.Add($btnRefresh)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Location = New-Object System.Drawing.Point(24, 308)
$logBox.Size = New-Object System.Drawing.Size(856, 248)
$logBox.Anchor = "Top,Bottom,Left,Right"
$logBox.Multiline = $true
$logBox.ScrollBars = "Vertical"
$logBox.ReadOnly = $true
$logBox.BackColor = [System.Drawing.Color]::FromArgb(15, 23, 42)
$logBox.ForeColor = [System.Drawing.Color]::FromArgb(226, 232, 240)
$logBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$form.Controls.Add($logBox)

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 800
$timer.Add_Tick({
    try {
        if (-not $script:currentJob) { return }
        $output = Receive-Job -Job $script:currentJob 2>&1
        foreach ($line in $output) { Append-Log ([string]$line) }
        if ($script:currentJob.State -in @("Completed", "Failed", "Stopped")) {
            $state = $script:currentJob.State
            $more = Receive-Job -Job $script:currentJob 2>&1
            foreach ($line in $more) { Append-Log ([string]$line) }
            if ($state -eq "Completed") {
                Append-Log "Tarea completada: $script:currentJobName"
            } else {
                Append-Log "Tarea finalizada con estado: $state"
            }
            Remove-Job -Job $script:currentJob -Force -ErrorAction SilentlyContinue
            $script:currentJob = $null
            $script:currentJobName = ""
            $timer.Stop()
            Set-ButtonsEnabled $true
            Refresh-Status
        }
    } catch {
        Append-Log "Error interno en monitor de tarea: $($_.Exception.Message)"
        $timer.Stop()
        $script:currentJob = $null
        Set-ButtonsEnabled $true
    }
})

$btnStart.Add_Click({
    if (-not (Test-CommandAvailable "docker")) {
        Append-Log "Docker CLI no esta disponible en PATH."
        return
    }
    Start-Task "Levantar Docker Compose" {
        param($ProjectDir, $NoBuildFlag)
        Set-Location $ProjectDir
        $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        if (Test-Path -LiteralPath $dockerDesktop) {
            Start-Process -FilePath $dockerDesktop -WindowStyle Hidden | Out-Null
            "Docker Desktop solicitado."
        }
        $deadline = (Get-Date).AddMinutes(3)
        do {
            docker info --format "{{.ServerVersion}}" 2>$null | ForEach-Object { "Docker daemon listo: $_" }
            if ($LASTEXITCODE -eq 0) { break }
            "Esperando Docker daemon..."
            Start-Sleep -Seconds 3
        } while ((Get-Date) -lt $deadline)
        if ($LASTEXITCODE -ne 0) { throw "Docker no quedo disponible dentro del tiempo esperado." }
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
    try {
        if (-not (Test-CloudflaredAvailable)) {
            Append-Log "cloudflared no esta disponible en PATH."
            return
        }
        $existing = Get-CloudflaredUrl
        if ($existing) {
            $script:publicUrl = $existing
            $publicText.Text = $existing
            Append-Log "Ya existe un tunel activo: $existing"
            if (Update-EnvPublicSettings -TunnelUrl $existing) {
                Append-Log "Reiniciando backend y frontend con configuracion publica (esto puede tardar)..."
                Invoke-CommandText "docker compose up -d --no-deps --force-recreate backend frontend" | Out-Null
                Append-Log "Reinicio completado."
            }
            Refresh-Status
            return
        }
        Append-Log "Iniciando cloudflared tunnel hacia http://localhost:3000"
        $cfOutLog = "$env:TEMP\cf_tunnel_out.log"
        Remove-Item $script:cfLogFile -Force -ErrorAction SilentlyContinue
        Remove-Item $cfOutLog          -Force -ErrorAction SilentlyContinue
        try {
            $script:cfProcess = Start-Process `
                -FilePath $script:cfExe `
                -ArgumentList "tunnel --url http://localhost:3000 --no-autoupdate" `
                -RedirectStandardError  $script:cfLogFile `
                -RedirectStandardOutput $cfOutLog `
                -NoNewWindow -PassThru -ErrorAction Stop
        } catch {
            Append-Log "No se pudo iniciar cloudflared: $($_.Exception.Message)"
            return
        }
        $deadline = (Get-Date).AddSeconds(75)
        $url = ""
        $lastPos = 0
        do {
            Start-Sleep -Milliseconds 800
            try {
                $fs = [System.IO.File]::Open($script:cfLogFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
                $reader = New-Object System.IO.StreamReader($fs)
                try { $logContent = $reader.ReadToEnd() } finally { $reader.Dispose(); $fs.Dispose() }
                if ($logContent.Length -gt $lastPos) {
                    ($logContent.Substring($lastPos) -split "`r?`n") | ForEach-Object {
                        $t = $_.Trim(); if ($t) { Append-Log "cf: $t" }
                    }
                    $lastPos = $logContent.Length
                }
            } catch { }
            $url = Get-CloudflaredUrl
            if ($url) { break }
            [System.Windows.Forms.Application]::DoEvents()
        } while ((Get-Date) -lt $deadline)
        if ($url) {
            $script:publicUrl = $url
            $publicText.Text = $url
            Append-Log "Tunel publico activo: $url"
            if (Update-EnvPublicSettings -TunnelUrl $url) {
                Append-Log "Reiniciando backend y frontend con configuracion publica (esto puede tardar)..."
                $restart = Invoke-CommandText "docker compose up -d --no-deps --force-recreate backend frontend"
                if ($restart.ExitCode -eq 0) {
                    Append-Log "Backend y frontend recreados con la configuracion publica."
                } else {
                    Append-Log "ADVERTENCIA: no se pudieron recrear backend/frontend automaticamente."
                }
            }
            try {
                $health = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 10
                Append-Log "Health publico: $($health.status)"
            } catch {
                Append-Log "Tunel creado. Health publico no respondio aun (normal al inicio)."
            }
        } else {
            Append-Log "cloudflared no entrego URL en el tiempo esperado. Revisa que el puerto 3000 este activo."
        }
        Refresh-Status
    } catch {
        Append-Log "Error al publicar: $($_.Exception.Message)"
        Refresh-Status
    }
})

$btnCopy.Add_Click({
    $url = if ($script:publicUrl) { $script:publicUrl } else { Get-CloudflaredUrl }
    if (-not $url) {
        Append-Log "No hay URL publica para copiar."
        return
    }
    [System.Windows.Forms.Clipboard]::SetText($url)
    Append-Log "URL copiada al portapapeles: $url"
})

$btnOpenLocal.Add_Click({
    Start-Process "http://localhost:3000"
})

$btnOpenPublic.Add_Click({
    $url = if ($script:publicUrl) { $script:publicUrl } else { Get-CloudflaredUrl }
    if (-not $url) {
        Append-Log "No hay URL publica activa."
        return
    }
    Start-Process $url
})

$btnStopNgrok.Add_Click({
    Append-Log "Deteniendo tunel cloudflared..."
    if ($script:cfProcess -and -not $script:cfProcess.HasExited) {
        $script:cfProcess.Kill()
        $script:cfProcess = $null
    }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Remove-Item $script:cfLogFile              -Force -ErrorAction SilentlyContinue
    Remove-Item "$env:TEMP\cf_tunnel_out.log"  -Force -ErrorAction SilentlyContinue
    $script:publicUrl = ""
    $publicText.Text = "Sin tunel activo"
    Refresh-Status
})

$btnRefresh.Add_Click({
    Refresh-Status
    Append-Log "Estado actualizado."
})

$form.Add_Shown({
    Append-Log "Directorio del proyecto: $projectDir"
    Append-Log "Orden sugerido: 1) Levantar / reconstruir, 2) Publicar con Cloudflare, 3) Copiar URL."
    Refresh-Status
})

$form.Add_FormClosing({
    if ($script:cfProcess -and -not $script:cfProcess.HasExited) {
        try { $script:cfProcess.Kill() } catch { }
    }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Remove-Item $script:cfLogFile             -Force -ErrorAction SilentlyContinue
    Remove-Item "$env:TEMP\cf_tunnel_out.log" -Force -ErrorAction SilentlyContinue
})

[void]$form.ShowDialog()
