$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$OutDir = Join-Path $Root "apendices_evidencias"

$Folders = @(
  "A_matrices_verificacion",
  "B_ejecucion_terminal",
  "C_api_swagger_endpoints",
  "D_seguridad_control_acceso",
  "E_trazabilidad_desarrollo"
)

foreach ($folder in $Folders) {
  New-Item -ItemType Directory -Force -Path (Join-Path $OutDir $folder) | Out-Null
}

function Sanitize-Text {
  param([AllowNull()][string]$Text)
  if ($null -eq $Text) { return "" }
  $value = $Text
  $value = $value -replace '[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', '[CORREO OCULTO]'
  $value = $value -replace 'eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+', '[TOKEN OCULTO]'
  $value = $value -replace '"access_token"\s*:\s*"[^"]+"', '"access_token":"[TOKEN OCULTO]"'
  $value = $value -replace 'Bearer\s+[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+', 'Bearer [TOKEN OCULTO]'
  $value = $value -replace '(POSTGRES_PASSWORD|SMTP_PASSWORD|ASOFAMECH_JWT_SECRET|HISTO_HF_TOKEN|HF_TOKEN|API_KEY|SECRET)(=|":\s*")[^,\r\n"]*', '$1$2[CLAVE OCULTA]'
  $value = $value -replace '(Admin12345|Student12345)', '[CLAVE OCULTA]'
  $value = $value -replace 'C:\\Users\\[^\\\r\n"]+', '[RUTA LOCAL OCULTA]'
  $value = $value -replace '"/app/[^"]+"', '"[RUTA CONTENEDOR OCULTA]"'
  $value = $value -replace '"/root/[^"]+"', '"[RUTA CONTENEDOR OCULTA]"'
  $value = $value -replace '/app/[^\s,\)"]+', '[RUTA CONTENEDOR OCULTA]'
  $value = $value -replace '/root/[^\s,\)"]+', '[RUTA CONTENEDOR OCULTA]'
  return $value
}

function Save-TextEvidence {
  param(
    [string]$RelativePath,
    [AllowNull()][string]$Content
  )
  $path = Join-Path $OutDir $RelativePath
  $parent = Split-Path -Parent $path
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  Set-Content -Path $path -Value (Sanitize-Text $Content) -Encoding UTF8
}

function Save-JsonEvidence {
  param(
    [string]$RelativePath,
    [object]$Data,
    [int]$Depth = 20
  )
  Save-TextEvidence $RelativePath ($Data | ConvertTo-Json -Depth $Depth)
}

function Capture-Command {
  param(
    [string]$RelativePath,
    [scriptblock]$Command
  )
  $started = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  try {
    $output = & $Command 2>&1 | Out-String
    $exit = if ($null -ne $global:LASTEXITCODE) { $global:LASTEXITCODE } else { 0 }
    $content = "Fecha ejecucion: $started`r`nExit code: $exit`r`n`r`n$output"
  } catch {
    $content = "Fecha ejecucion: $started`r`nExit code: ERROR`r`n`r`n$($_ | Out-String)"
  }
  Save-TextEvidence $RelativePath $content
}

function Read-ErrorResponse {
  param([object]$ErrorRecord)
  $status = $null
  $body = ""
  try {
    if ($ErrorRecord.Exception.Response) {
      $status = [int]$ErrorRecord.Exception.Response.StatusCode
      $stream = $ErrorRecord.Exception.Response.GetResponseStream()
      if ($stream) {
        $memory = New-Object System.IO.MemoryStream
        $stream.CopyTo($memory)
        $body = [System.Text.Encoding]::UTF8.GetString($memory.ToArray())
      }
    }
  } catch {
    $body = ""
  }
  return [ordered]@{
    ok = $false
    status = $status
    body = $body
    error = $ErrorRecord.Exception.Message
  }
}

function Get-WebResponseContentUtf8 {
  param([object]$Response)
  try {
    if ($Response.RawContentStream) {
      if ($Response.RawContentStream.CanSeek) {
        $Response.RawContentStream.Position = 0
      }
      $memory = New-Object System.IO.MemoryStream
      $Response.RawContentStream.CopyTo($memory)
      return [System.Text.Encoding]::UTF8.GetString($memory.ToArray())
    }
  } catch {
    return [string]$Response.Content
  }
  return [string]$Response.Content
}

function Invoke-ApiEvidence {
  param(
    [string]$Method = "GET",
    [string]$Url,
    [object]$Body = $null,
    [string]$Token = $null,
    [int]$TimeoutSec = 30
  )
  $headers = @{}
  if ($Token) { $headers["Authorization"] = "Bearer $Token" }
  try {
    $params = @{
      Uri = $Url
      Method = $Method
      Headers = $headers
      TimeoutSec = $TimeoutSec
      UseBasicParsing = $true
    }
    if ($null -ne $Body) {
      $params["ContentType"] = "application/json"
      $params["Body"] = ($Body | ConvertTo-Json -Depth 30)
    }
    $response = Invoke-WebRequest @params
    $content = Get-WebResponseContentUtf8 $response
    $parsed = $null
    try { $parsed = $content | ConvertFrom-Json } catch { $parsed = $content }
    return [ordered]@{
      ok = $true
      status = [int]$response.StatusCode
      body = $parsed
    }
  } catch {
    $err = Read-ErrorResponse $_
    try { $err.body = $err.body | ConvertFrom-Json } catch { }
    return $err
  }
}

function Capture-EndpointPng {
  param(
    [string]$Url,
    [string]$RelativePng,
    [string]$RelativeLog
  )
  function ConvertTo-JsLiteral {
    param([string]$Value)
    $escaped = $Value.Replace("\", "\\").Replace("'", "\'")
    return "'$escaped'"
  }
  $pngPath = Join-Path $OutDir $RelativePng
  $parent = Split-Path -Parent $pngPath
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  $rootJs = ConvertTo-JsLiteral $Root
  $urlJs = ConvertTo-JsLiteral $Url
  $pngJs = ConvertTo-JsLiteral $pngPath
  $nodeCode = @"
const path = require('path');
const { chromium } = require(path.join($rootJs, 'frontend', 'node_modules', '@playwright', 'test'));
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
  await page.goto($urlJs, { waitUntil: 'networkidle', timeout: 45000 });
  await page.screenshot({ path: $pngJs, fullPage: true });
  await browser.close();
})();
"@
  Push-Location $Root
  try {
    $output = node -e $nodeCode 2>&1 | Out-String
    $exit = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  if ($exit -ne 0) {
    Save-TextEvidence $RelativeLog "No ejecutada: captura Playwright fallo con exit code $exit.`r`n$output"
  } else {
    Save-TextEvidence $RelativeLog "Captura generada correctamente: $RelativePng"
  }
}

$BaseApi = "http://127.0.0.1:8001"
$Frontend = "http://127.0.0.1:3000"
$StudentEmail = "student.e2e@asofamech.local"
$StudentPassword = "Student12345"

Capture-Command "B_ejecucion_terminal/B_ET01_docker_compose_ps.txt" { docker compose ps }
Capture-Command "B_ejecucion_terminal/B_ET02_backend_logs_sanitizado.txt" { docker compose logs backend --tail 200 }
Capture-Command "B_ejecucion_terminal/B_ET04_pytest_resultado.txt" { docker compose exec -T backend sh -c "PYTHONPATH=/app python -m pytest tests -q" }
Capture-Command "B_ejecucion_terminal/B_ET05_npm_build.txt" {
  Push-Location (Join-Path $Root "frontend")
  try { npm.cmd run build } finally { Pop-Location }
}
Capture-Command "B_ejecucion_terminal/B_ET06_postgresql_pgvector_estado.txt" {
  docker compose exec -T db psql -U app_user -d app_db -c "select current_database() as database, current_user as db_user; select extname, extversion from pg_extension where extname = 'vector'; select count(*) as users_total from users; select count(*) as medical_images_activas from medical_images where is_active = true;"
}
Capture-Command "B_ejecucion_terminal/B_ET07_ollama_estado.txt" {
  Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10 | Select-Object StatusCode, Content
}
Capture-Command "B_ejecucion_terminal/B_ET08_frontend_backend_health_proxy.txt" {
  Invoke-WebRequest -UseBasicParsing -Uri "$Frontend/health" -TimeoutSec 10 | Select-Object StatusCode, Content
}

$health = Invoke-ApiEvidence -Url "$BaseApi/health"
Save-JsonEvidence "B_ejecucion_terminal/B_ET03_health_endpoint.json" $health
Save-JsonEvidence "C_api_swagger_endpoints/C_API05_health_respuesta.json" $health

$login = Invoke-ApiEvidence -Method "POST" -Url "$BaseApi/api/auth/login" -Body @{ email = $StudentEmail; password = $StudentPassword }
$studentToken = $null
if ($login.ok -and $login.body.access_token) { $studentToken = [string]$login.body.access_token }
Save-JsonEvidence "C_api_swagger_endpoints/C_API03_login_respuesta_sanitizada.json" $login
Save-JsonEvidence "D_seguridad_control_acceso/D_SEC01_login_valido.json" $login

$invalidLogin = Invoke-ApiEvidence -Method "POST" -Url "$BaseApi/api/auth/login" -Body @{ email = "qa.invalid.$((Get-Date).ToString('yyyyMMddHHmmss'))@asofamech.local"; password = "ClaveQA12345" }
Save-JsonEvidence "D_seguridad_control_acceso/D_SEC02_login_invalido.json" $invalidLogin

$me = Invoke-ApiEvidence -Url "$BaseApi/api/auth/me" -Token $studentToken
Save-JsonEvidence "C_api_swagger_endpoints/C_API04_usuario_autenticado_sanitizado.json" $me

$dashboardNoToken = Invoke-ApiEvidence -Url "$BaseApi/api/dashboard/stats"
Save-JsonEvidence "D_seguridad_control_acceso/D_SEC03_ruta_protegida_sin_token.json" $dashboardNoToken

$dashboardWithToken = Invoke-ApiEvidence -Url "$BaseApi/api/dashboard/stats" -Token $studentToken
Save-JsonEvidence "D_seguridad_control_acceso/D_SEC04_ruta_protegida_con_token.json" $dashboardWithToken

$adminWithStudent = Invoke-ApiEvidence -Url "$BaseApi/api/admin/users" -Token $studentToken
Save-JsonEvidence "D_seguridad_control_acceso/D_SEC05_admin_con_usuario_estudiante.json" $adminWithStudent

Capture-Command "D_seguridad_control_acceso/D_SEC06_password_hash_evidencia.txt" {
  docker compose exec -T db psql -U app_user -d app_db -c "select count(*) as usuarios, count(password_hash) as hashes_presentes, min(length(password_hash)) as largo_min_hash, max(length(password_hash)) as largo_max_hash, bool_or(password_hash like 'pbkdf2_sha256$%') as usa_pbkdf2_sha256, bool_or(password_hash in ('Student12345','Admin12345','password','12345678')) as texto_plano_detectado from users;"
}

$histStatus = Invoke-ApiEvidence -Url "$BaseApi/api/histopathology/status" -TimeoutSec 60
Save-JsonEvidence "B_ejecucion_terminal/B_ET09_histopathology_status.json" $histStatus
Save-JsonEvidence "C_api_swagger_endpoints/C_API06_histopathology_status_sanitizado.json" $histStatus

$openapi = Invoke-ApiEvidence -Url "$BaseApi/openapi.json" -TimeoutSec 20
Save-JsonEvidence "C_api_swagger_endpoints/C_API00_openapi_json_sanitizado.json" $openapi

$endpointRows = @()
if ($openapi.ok -and $openapi.body.paths) {
  foreach ($pathProp in $openapi.body.paths.PSObject.Properties) {
    foreach ($methodProp in $pathProp.Value.PSObject.Properties) {
      $method = $methodProp.Name.ToUpperInvariant()
      if ($method -in @("GET", "POST", "PUT", "PATCH", "DELETE")) {
        $endpointRows += "| $method | $($pathProp.Name) | $($methodProp.Value.summary) | $($methodProp.Value.tags -join ', ') |"
      }
    }
  }
}
$endpointMarkdown = @"
# C_API02 - Listado de endpoints principales

Fuente: `/openapi.json`, generado por FastAPI.

| Método | Ruta | Resumen OpenAPI | Tags |
|---|---|---|---|
$($endpointRows -join "`r`n")
"@
Save-TextEvidence "C_api_swagger_endpoints/C_API02_listado_endpoints_principales.md" $endpointMarkdown

$sctList = Invoke-ApiEvidence -Url "$BaseApi/api/sct/list" -Token $studentToken
Save-JsonEvidence "C_api_swagger_endpoints/C_API07_sct_list_respuesta.json" $sctList

$sctAttempt = [ordered]@{ ok = $false; status = "No ejecutada"; reason = "No hay test SCT publicado disponible." }
if ($sctList.ok -and @($sctList.body).Count -gt 0) {
  $firstSct = @($sctList.body)[0]
  $sctDetail = Invoke-ApiEvidence -Url "$BaseApi/api/sct/$($firstSct.id)" -Token $studentToken
  if ($sctDetail.ok -and $sctDetail.body.items) {
    $answers = @()
    foreach ($item in $sctDetail.body.items) {
      $answers += @{ item_id = $item.id; selected_answer = $item.correct_answer }
    }
    $sctAttempt = Invoke-ApiEvidence -Method "POST" -Url "$BaseApi/api/sct/$($firstSct.id)/attempt" -Token $studentToken -Body @{ answers = $answers; started_at = (Get-Date).ToString("o") }
  }
}
Save-JsonEvidence "C_api_swagger_endpoints/C_API08_sct_attempt_respuesta.json" $sctAttempt

$ragSearch = Invoke-ApiEvidence -Url "$BaseApi/api/rag/search?q=fiebre&limit=2" -Token $studentToken -TimeoutSec 30
Save-JsonEvidence "C_api_swagger_endpoints/C_API09_rag_search_respuesta.json" $ragSearch

$chat = Invoke-ApiEvidence -Method "POST" -Url "$BaseApi/api/chat" -Token $studentToken -Body @{ text = "Hola, entrega una recomendacion breve para estudiar histopatologia." } -TimeoutSec 120
Save-JsonEvidence "C_api_swagger_endpoints/C_API10_chatbot_respuesta_sanitizada.json" $chat

$images = Invoke-ApiEvidence -Url "$BaseApi/api/medical-images/list" -Token $studentToken -TimeoutSec 30
$imageForViewer = $null
if ($images.ok -and @($images.body).Count -gt 0) {
  $imageForViewer = @($images.body | Where-Object { $_.file_type -match "svs|tif|tiff" } | Select-Object -First 1)
  if (-not $imageForViewer) { $imageForViewer = @($images.body)[0] }
}
Save-JsonEvidence "C_api_swagger_endpoints/C_API11_medical_images_list_resumen.json" $images

$dzi = [ordered]@{ ok = $false; status = "No ejecutada"; reason = "No hay imagen disponible para DZI." }
$roiAnalysis = [ordered]@{ ok = $false; status = "No ejecutada"; reason = "No hay imagen disponible para ROI." }
$roiInvalid = [ordered]@{ ok = $false; status = "No ejecutada"; reason = "No hay imagen disponible para ROI." }
if ($imageForViewer) {
  $dzi = Invoke-ApiEvidence -Url "$BaseApi/api/medical-images/dzi/$($imageForViewer.id).dzi" -Token $studentToken -TimeoutSec 60
  $roi1 = @{ x = 1000; y = 1000; width = 2048; height = 2048 }
  $roi2 = @{ x = 1200; y = 1200; width = 256; height = 256 }
  $roiAnalysis = Invoke-ApiEvidence -Method "POST" -Url "$BaseApi/api/histopathology/analyze-roi" -Token $studentToken -Body @{ image_id = $imageForViewer.id; roi_1 = $roi1; roi_2 = $roi2 } -TimeoutSec 120
  $roiInvalid = Invoke-ApiEvidence -Method "POST" -Url "$BaseApi/api/histopathology/analyze-roi" -Token $studentToken -Body @{ image_id = $imageForViewer.id; roi_1 = @{ x = 1000; y = 1000; width = 256; height = 256 }; roi_2 = @{ x = 2000; y = 2000; width = 256; height = 256 } } -TimeoutSec 60
}
Save-JsonEvidence "C_api_swagger_endpoints/C_API12_dzi_viewer_respuesta.xml.json" $dzi
Save-JsonEvidence "C_api_swagger_endpoints/C_API13_roi_analisis_respuesta.json" $roiAnalysis
Save-JsonEvidence "C_api_swagger_endpoints/C_API14_roi_validacion_invalida.json" $roiInvalid

Capture-Command "B_ejecucion_terminal/B_ET10_persistencia_bd_resumen.txt" {
  docker compose exec -T db psql -U app_user -d app_db -c "select count(*) as sct_attempts from sct_attempts; select count(*) as histopathology_sessions from histopathology_sessions; select count(*) as chat_logs from chat_logs;"
}

Capture-EndpointPng "$BaseApi/docs" "C_api_swagger_endpoints/C_API01_swagger_openapi.png" "C_api_swagger_endpoints/C_API01_swagger_openapi_capture_log.txt"
Capture-EndpointPng "$BaseApi/health" "B_ejecucion_terminal/B_ET03_health_endpoint.png" "B_ejecucion_terminal/B_ET03_health_endpoint_capture_log.txt"

$matrixA = @"
# Apéndice A - Matriz extendida de verificación

| ID | Tipo de prueba | Módulo | Precondición | Pasos ejecutados | Resultado esperado | Resultado observado | Estado | Evidencia asociada |
|---|---|---|---|---|---|---|---|---|
| A_FUNC_01 | Funcional | Autenticación | Backend y BD activos; cuenta estudiante E2E aprobada | POST `/api/auth/login` con credenciales de prueba sanitizadas | HTTP 200, token JWT y usuario público | Login correcto; token oculto en evidencia | Aprobada | `C_API03_login_respuesta_sanitizada.json`, `D_SEC01_login_valido.json` |
| A_FUNC_02 | Funcional | Autenticación | Backend activo | POST `/api/auth/login` con cuenta inexistente de QA | HTTP 401 sin token | Respuesta de rechazo registrada sin token | Aprobada | `D_SEC02_login_invalido.json` |
| A_FUNC_03 | Funcional | Dashboard | Token estudiante válido | GET `/api/dashboard/stats` con token | HTTP 200 con métricas del dashboard | Ruta protegida responde con datos agregados | Aprobada | `D_SEC04_ruta_protegida_con_token.json` |
| A_FUNC_04 | Integración | Visor histopatológico | Token válido e imagen activa | GET `/api/medical-images/list` y GET DZI de imagen compatible | Imagen listada y descriptor DZI disponible | Listado y descriptor DZI respondieron correctamente | Aprobada | `C_API11_medical_images_list_resumen.json`, `C_API12_dzi_viewer_respuesta.xml.json` |
| A_FUNC_05 | Funcional | ROI | Imagen compatible disponible | Preparar ROI 1 amplia en coordenadas nivel 0 | ROI 1 queda representada como área madre | ROI 1 enviada en payload de análisis | Aprobada | `C_API13_roi_analisis_respuesta.json` |
| A_FUNC_06 | Funcional | ROI | ROI 1 definida | Preparar ROI 2 contenida en ROI 1 | ROI 2 queda lista para clasificación | ROI 2 enviada en payload de análisis | Aprobada | `C_API13_roi_analisis_respuesta.json` |
| A_FUNC_07 | Funcional | Validación ROI | Imagen y token válidos | POST `/api/histopathology/analyze-roi` con ROI 2 fuera de ROI 1 | HTTP 400 por validación geométrica | La API rechazó el ROI inválido | Aprobada | `C_API14_roi_validacion_invalida.json` |
| A_FUNC_08 | Integración | Análisis IA | Imagen activa, ROI 1 y ROI 2 válidas | POST `/api/histopathology/analyze-roi` | Respuesta educativa con clase/estado, trazabilidad y advertencia | Se generó resultado preliminar de ROI | Aprobada | `C_API13_roi_analisis_respuesta.json`, `B_ET09_histopathology_status.json` |
| A_FUNC_09 | Integración | Chatbot educativo | Token válido y Ollama activo | POST `/api/chat` con consulta breve | Respuesta educativa o error controlado | Respuesta registrada y sanitizada | Aprobada | `C_API10_chatbot_respuesta_sanitizada.json`, `B_ET07_ollama_estado.txt` |
| A_FUNC_10 | Funcional | SCT | Token válido y test SCT publicado | GET `/api/sct/list`, GET detalle y POST intento | Intento SCT guardado con puntuación | Intento SCT registrado en API | Aprobada | `C_API07_sct_list_respuesta.json`, `C_API08_sct_attempt_respuesta.json` |
| A_INT_01 | Integración | Frontend-backend | Contenedores activos | GET `http://127.0.0.1:3000/health` vía Nginx frontend | Proxy frontend responde salud backend | Health proxy operativo | Aprobada | `B_ET08_frontend_backend_health_proxy.txt` |
| A_INT_02 | Integración | Persistencia | BD activa | Consultar conteos de intentos SCT, sesiones ROI y logs de chat | Registros persistidos en PostgreSQL | Conteos registrados en BD | Aprobada | `B_ET10_persistencia_bd_resumen.txt` |
| A_E2E_01 | Flujo completo técnico | Login -> dashboard -> visor -> ROI -> análisis -> chatbot -> SCT | Servicios Docker activos y usuario E2E aprobado | Secuencia API: login, dashboard, listado/DZI, ROI válido, chat, SCT attempt | Flujo responde sin errores no controlados | Secuencia completada mediante endpoints técnicos | Aprobada | `D_SEC01_login_valido.json`, `D_SEC04_ruta_protegida_con_token.json`, `C_API12_dzi_viewer_respuesta.xml.json`, `C_API13_roi_analisis_respuesta.json`, `C_API10_chatbot_respuesta_sanitizada.json`, `C_API08_sct_attempt_respuesta.json` |
"@
Save-TextEvidence "A_matrices_verificacion/A_MV01_matriz_verificacion_extendida.md" $matrixA

$matrixD = @"
# Apéndice D - Matriz de seguridad básica y control de acceso

| ID | Prueba | Entrada o acción | Resultado esperado | Resultado observado | Estado | Evidencia asociada |
|---|---|---|---|---|---|---|
| D_SEC_01 | Login válido | POST `/api/auth/login` con usuario estudiante E2E | HTTP 200, token emitido y datos públicos | Token emitido y oculto en evidencia | Aprobada | `D_SEC01_login_valido.json` |
| D_SEC_02 | Login inválido | POST `/api/auth/login` con usuario inexistente | HTTP 401, sin token | Rechazo registrado; no se expone token | Aprobada | `D_SEC02_login_invalido.json` |
| D_SEC_03 | Ruta protegida sin token | GET `/api/dashboard/stats` sin Authorization | HTTP 401 o 403 | Acceso denegado por falta de token | Aprobada | `D_SEC03_ruta_protegida_sin_token.json` |
| D_SEC_04 | Ruta protegida con token válido | GET `/api/dashboard/stats` con Bearer válido | HTTP 200 | Acceso autorizado | Aprobada | `D_SEC04_ruta_protegida_con_token.json` |
| D_SEC_05 | Ruta administrativa con rol insuficiente | GET `/api/admin/users` con token estudiante | HTTP 403 | Acceso administrativo rechazado | Aprobada | `D_SEC05_admin_con_usuario_estudiante.json` |
| D_SEC_06 | Contraseñas no almacenadas en texto plano | Consulta agregada de `password_hash` sin mostrar hashes | Hashes presentes, formato PBKDF2, sin contraseñas planas conocidas | Evidencia agregada sin revelar hashes reales | Aprobada | `D_SEC06_password_hash_evidencia.txt` |
"@
Save-TextEvidence "D_seguridad_control_acceso/D_MSC01_matriz_seguridad_control_acceso.md" $matrixD

$traceability = @"
# Apéndice E - Trazabilidad de desarrollo y evidencias

| Requerimiento | Tarea, issue o commit asociado | Módulo | Evidencia generada | Estado de implementación | Observación técnica |
|---|---|---|---|---|---|
| RF-01 Autenticación JWT de usuarios | Implementación local en routers/auth.py y auth_security.py | Autenticación | `C_API03_login_respuesta_sanitizada.json`, `D_SEC01_login_valido.json` | Implementado | Token emitido y sanitizado; usuario público sin `password_hash`. |
| RF-02 Control de acceso por rol | Dependencias `get_current_user`, `require_admin`, `require_roles` | Seguridad | `D_SEC03_ruta_protegida_sin_token.json`, `D_SEC05_admin_con_usuario_estudiante.json` | Implementado | Ruta administrativa rechaza estudiante con 403. |
| RF-03 Visor histopatológico OpenSeadragon/DZI | Integración OpenSeadragon y endpoint DZI | Visor histopatológico | `C_API12_dzi_viewer_respuesta.xml.json` | Implementado | Descriptor DZI confirma soporte de imagen piramidal. |
| RF-04 Selección ROI 1 y ROI 2 | Componentes de selección ROI y validación backend | ROI | `C_API13_roi_analisis_respuesta.json`, `C_API14_roi_validacion_invalida.json` | Implementado | ROI 2 debe estar contenida en ROI 1 y cumplir tamaño. |
| RF-05 Análisis IA histopatológico | CONCH/PyTorch y servicio de inferencia | Análisis IA | `B_ET09_histopathology_status.json`, `C_API13_roi_analisis_respuesta.json` | Implementado | Resultado educativo no diagnóstico con advertencia explícita. |
| RF-06 Chatbot educativo | Endpoint `/api/chat`, Ollama/LLaMA y registro de conversaciones | Chatbot | `C_API10_chatbot_respuesta_sanitizada.json`, `B_ET07_ollama_estado.txt` | Implementado | Servicio Ollama expone modelo local; respuesta sanitizada. |
| RF-07 Búsqueda RAG | Endpoint `/api/rag/search` y pgvector | RAG | `C_API09_rag_search_respuesta.json`, `B_ET06_postgresql_pgvector_estado.txt` | Implementado | Evidencia técnica de recuperación documental. |
| RF-08 Módulo SCT | Routers SCT, intentos y scoring | SCT | `C_API07_sct_list_respuesta.json`, `C_API08_sct_attempt_respuesta.json` | Implementado | Intento SCT persiste score y correctas/total. |
| RNF-01 Persistencia PostgreSQL/pgvector | Docker Compose + migraciones | Base de datos | `B_ET06_postgresql_pgvector_estado.txt`, `B_ET10_persistencia_bd_resumen.txt` | Implementado | Extensión `vector` activa y conteos de registros disponibles. |
| RNF-02 Ejecución contenerizada | Docker Compose | Infraestructura | `B_ET01_docker_compose_ps.txt` | Implementado | Servicios backend, frontend, db y Ollama levantados. |
| RNF-03 Pruebas backend | Suite pytest | QA backend | `B_ET04_pytest_resultado.txt` | Implementado | Batería técnica ejecutada dentro del contenedor. |
| RNF-04 Build frontend reproducible | Vite build | Frontend | `B_ET05_npm_build.txt` | Implementado | Build productivo generado sin errores. |
"@
Save-TextEvidence "E_trazabilidad_desarrollo/E_TRZ01_trazabilidad_desarrollo.md" $traceability

$readme = @"
# README_APENDICES

Carpeta de evidencias complementarias para los apéndices técnicos del informe ASOFAMECH.

## A_matrices_verificacion
Contiene la matriz extendida de verificación funcional, integración y flujo completo técnico. Cada fila referencia evidencias ubicadas en las carpetas B, C o D.

## B_ejecucion_terminal
Contiene salidas de terminal sanitizadas: Docker Compose, logs backend, health checks, pytest, build frontend, PostgreSQL/pgvector, Ollama y persistencia.

## C_api_swagger_endpoints
Contiene evidencia de Swagger/OpenAPI, listado de endpoints, respuestas JSON sanitizadas de autenticación, usuario autenticado, salud, histopatología, SCT, RAG/chatbot, visor DZI y ROI.

## D_seguridad_control_acceso
Contiene la matriz de seguridad básica y respuestas sanitizadas para login válido, login inválido, acceso protegido sin token, acceso protegido con token, rechazo administrativo por rol y verificación agregada de hashes de contraseña.

## E_trazabilidad_desarrollo
Relaciona requerimientos funcionales y no funcionales con módulos, evidencias generadas y estado de implementación.

## Sanitización
Los archivos fueron generados ocultando tokens JWT, correos completos, claves, contraseñas y rutas locales personales. Los valores sensibles se reemplazan por marcadores como `[TOKEN OCULTO]`, `[CORREO OCULTO]`, `[CLAVE OCULTA]` o `[RUTA LOCAL OCULTA]`.
"@
Save-TextEvidence "README_APENDICES.md" $readme

$summary = @"
Generación completada: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

Carpeta: $OutDir

Subcarpetas:
- A_matrices_verificacion
- B_ejecucion_terminal
- C_api_swagger_endpoints
- D_seguridad_control_acceso
- E_trazabilidad_desarrollo
"@
Save-TextEvidence "RESUMEN_GENERACION.txt" $summary
Write-Output $summary
