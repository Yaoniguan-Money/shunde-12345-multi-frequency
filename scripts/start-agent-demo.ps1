$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$expectedDatabase = "shunde_agent_demo_v2"

# This is deliberately separate from the general development launcher.  The
# demo must never silently migrate the primary `shunde` database.
$env:SHUNDE_DATABASE_URL = "postgresql+asyncpg://shunde:shunde@127.0.0.1:5432/$expectedDatabase"

$preflight = @'
import asyncio
from sqlalchemy import text
from backend.app.config import get_settings
from backend.app.infrastructure.db.session import create_engine

async def main():
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as connection:
            database = await connection.scalar(text("select current_database()"))
            if database != "shunde_agent_demo_v2":
                raise RuntimeError(f"refusing to start demo against {database}")
            work_orders = await connection.scalar(text("select count(*) from work_orders"))
            events = await connection.scalar(text("select count(*) from event_instances where pipeline_version = 'understanding.v2'"))
            embeddings = await connection.scalar(text("select count(*) from work_order_embeddings"))
            print(f"Agent demo database: {database}")
            print(f"work_orders={work_orders}; understanding_v2_events={events}; embeddings={embeddings}")
    finally:
        await engine.dispose()

asyncio.run(main())
'@

$preflight | uv run --project $projectRoot python -
& (Join-Path $PSScriptRoot "start.ps1")
