$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $projectRoot "data\runtime"
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null

$runtimeEnvironmentNames = @(
    "SHUNDE_AI_PROVIDER_MODE",
    "SHUNDE_AI_REMOTE_BASE_URL",
    "SHUNDE_AI_REMOTE_LLM_MODEL_ID",
    "SHUNDE_AI_REMOTE_FLASH_LLM_MODEL_ID",
    "SHUNDE_AI_REMOTE_EMBEDDING_MODEL_ID",
    "SHUNDE_AI_REMOTE_API_KEY",
    "SHUNDE_AI_DEEPSEEK_BASE_URL",
    "SHUNDE_AI_DEEPSEEK_LLM_MODEL_ID",
    "SHUNDE_AI_DEEPSEEK_API_KEY",
    "SHUNDE_AI_LOCAL_EMBEDDING_BASE_URL",
    "SHUNDE_AI_LOCAL_EMBEDDING_MODEL_ID",
    "SHUNDE_AI_LOCAL_EMBEDDING_PROTOCOL",
    "SHUNDE_MODEL_CONCURRENCY",
    "SHUNDE_GAZETTEER_HOME"
)
foreach ($environmentName in $runtimeEnvironmentNames) {
    $processValue = [Environment]::GetEnvironmentVariable($environmentName, "Process")
    if ([string]::IsNullOrWhiteSpace($processValue)) {
        $userValue = [Environment]::GetEnvironmentVariable($environmentName, "User")
        if (-not [string]::IsNullOrWhiteSpace($userValue)) {
            [Environment]::SetEnvironmentVariable($environmentName, $userValue, "Process")
        }
    }
}

docker compose --project-directory $projectRoot up -d postgres
uv run --project $projectRoot alembic upgrade head

$gazetteerHome = $env:SHUNDE_GAZETTEER_HOME
if ([string]::IsNullOrWhiteSpace($gazetteerHome)) {
    $gazetteerHome = [Environment]::GetEnvironmentVariable("SHUNDE_GAZETTEER_HOME", "User")
}
if ([string]::IsNullOrWhiteSpace($gazetteerHome)) {
    throw "SHUNDE_GAZETTEER_HOME is required to start the real gazetteer service"
}
$gazetteerDirectory = Join-Path $gazetteerHome "地名服务"
$gazetteerServer = Join-Path $gazetteerDirectory "server.py"
if (-not (Test-Path -LiteralPath $gazetteerServer)) {
    throw "Gazetteer server not found: $gazetteerServer"
}

$gazetteerLog = Join-Path $runtimePath "gazetteer.log"
$gazetteerErrorLog = Join-Path $runtimePath "gazetteer.error.log"
$backendLog = Join-Path $runtimePath "backend.log"
$backendErrorLog = Join-Path $runtimePath "backend.error.log"
$frontendLog = Join-Path $runtimePath "frontend.log"
$frontendErrorLog = Join-Path $runtimePath "frontend.error.log"
$gazetteerReady = $false
try {
    Invoke-WebRequest "http://127.0.0.1:8000/openapi.json" -UseBasicParsing | Out-Null
    $gazetteerReady = $true
}
catch {
    $gazetteer = Start-Process -FilePath "uv.exe" -ArgumentList @(
        "run", "--project", $projectRoot, "python", "server.py"
    ) -WorkingDirectory $gazetteerDirectory -RedirectStandardOutput $gazetteerLog `
      -RedirectStandardError $gazetteerErrorLog -WindowStyle Hidden -PassThru
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            Invoke-WebRequest "http://127.0.0.1:8000/openapi.json" -UseBasicParsing | Out-Null
            $gazetteerReady = $true
            break
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
}
if (-not $gazetteerReady) {
    if ($null -ne $gazetteer) {
        Stop-Process -Id $gazetteer.Id -Force -ErrorAction SilentlyContinue
    }
    throw "Gazetteer service failed to expose OpenAPI; see $gazetteerErrorLog"
}
$gazetteerPid = (Get-NetTCPConnection -State Listen -LocalPort 8000 |
    Select-Object -First 1 -ExpandProperty OwningProcess)

$backend = Start-Process -FilePath "uv.exe" -ArgumentList @(
    "run", "--project", $projectRoot, "uvicorn", "backend.app.main:app",
    "--host", "127.0.0.1", "--port", "8080"
) -WorkingDirectory $projectRoot -RedirectStandardOutput $backendLog `
  -RedirectStandardError $backendErrorLog -WindowStyle Hidden -PassThru
$frontend = Start-Process -FilePath "pnpm.cmd" -ArgumentList @(
    "--dir", (Join-Path $projectRoot "frontend"), "dev"
) -WorkingDirectory $projectRoot -RedirectStandardOutput $frontendLog `
  -RedirectStandardError $frontendErrorLog -WindowStyle Hidden -PassThru

@{
    backend_pid = $backend.Id
    frontend_pid = $frontend.Id
    gazetteer_pid = $gazetteerPid
} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $runtimePath "dev-processes.json")

Write-Host "Gazetteer: http://127.0.0.1:8000"
Write-Host "Backend: http://127.0.0.1:8080"
Write-Host "Frontend: http://127.0.0.1:5173"
