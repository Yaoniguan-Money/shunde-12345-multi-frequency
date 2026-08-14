$ErrorActionPreference = "Stop"

uv sync --locked
pnpm install --frozen-lockfile
docker compose up -d postgres
uv run alembic upgrade head

Write-Host "Bootstrap complete. Run scripts/start.ps1 to start backend and frontend."

