#!/usr/bin/env bash
set -euo pipefail

uv sync --locked
pnpm install --frozen-lockfile
docker compose up -d postgres
uv run alembic upgrade head

