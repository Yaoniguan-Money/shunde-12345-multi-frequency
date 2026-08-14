"""Run the real government workbook through the resumable import handler.

The source path is supplied explicitly so the original workbook is never copied
into the repository or silently replaced by a fixture.
"""

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path

from backend.app.application.handlers.imports import ImportHandler
from backend.app.config import get_settings
from backend.app.infrastructure.db.imports import SQLAlchemyImportRepository
from backend.app.infrastructure.db.session import create_engine, create_session_factory
from backend.app.infrastructure.imports import PolarsTabularReader, SourceStager


async def main() -> None:
    source_path = Path(os.environ["SHUNDE_GOVERNMENT_XLSX"])
    settings = get_settings()
    engine = create_engine(settings)
    try:
        handler = ImportHandler(
            PolarsTabularReader(),
            SQLAlchemyImportRepository(create_session_factory(engine)),
            chunk_size=1000,
        )
        source = SourceStager(settings.runtime_dir).stage_path(source_path, source_path.name)
        summary = await handler.execute(source, sheet_name="Sheet1")
        print(json.dumps(asdict(summary), ensure_ascii=False, default=str))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
