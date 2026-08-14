#!/usr/bin/env bash
set -euo pipefail

if git check-ignore --quiet backend/app/infrastructure/db/models/base.py; then
  echo "Database model sources are ignored by Git. Check .gitignore." >&2
  exit 1
fi

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
