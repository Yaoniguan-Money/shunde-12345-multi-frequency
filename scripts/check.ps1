$ErrorActionPreference = "Stop"

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

