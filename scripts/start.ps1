$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $projectRoot "data\runtime"
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null

docker compose --project-directory $projectRoot up -d postgres
uv run --project $projectRoot alembic upgrade head

$backendLog = Join-Path $runtimePath "backend.log"
$backendErrorLog = Join-Path $runtimePath "backend.error.log"
$frontendLog = Join-Path $runtimePath "frontend.log"
$frontendErrorLog = Join-Path $runtimePath "frontend.error.log"
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
} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $runtimePath "dev-processes.json")

Write-Host "Backend: http://127.0.0.1:8080"
Write-Host "Frontend: http://127.0.0.1:5173"
