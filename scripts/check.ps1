$ErrorActionPreference = "Stop"

git check-ignore --quiet backend/app/infrastructure/db/models/base.py
if ($LASTEXITCODE -eq 0) {
  throw "Database model sources are ignored by Git. Check .gitignore."
}

uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright backend
uv run pytest -q
pnpm install --frozen-lockfile
pnpm lint
pnpm test --run
pnpm build
docker compose config --quiet
