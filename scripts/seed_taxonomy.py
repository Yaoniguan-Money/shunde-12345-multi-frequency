"""Seed the DB44/T 2479—2024 appendix A taxonomy from the reference CSV.

Usage:
    uv run python scripts/seed_taxonomy.py [--csv-path PATH] [--no-activate]

Default CSV path is docs/presentation-alignment-plan/reference/db44t2479-2024-appendix-a.csv.
The script creates a draft taxonomy version, runs integrity validation, and activates it.
Any validation failure is reported and the version stays in draft status.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from backend.app.application.services.taxonomy import TaxonomyService
from backend.app.config import get_settings
from backend.app.infrastructure.db.session import create_engine, create_session_factory
from backend.app.infrastructure.db.taxonomy import SQLAlchemyTaxonomyRepository

DEFAULT_CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "presentation-alignment-plan"
    / "reference"
    / "db44t2479-2024-appendix-a.csv"
)


async def main(csv_path: Path, activate: bool) -> int:
    if not csv_path.is_file():  # noqa: ASYNC240
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        return 1

    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    repository = SQLAlchemyTaxonomyRepository(session_factory)
    service = TaxonomyService(repository)

    version, activated, errors = await service.seed_from_csv(str(csv_path), activate=activate)

    result = {
        "version_id": str(version.version_id),
        "standard_name": version.standard_name,
        "status": version.status.value,
        "level_1_count": version.level_1_count,
        "level_2_count": version.level_2_count,
        "level_3_count": version.level_3_count,
        "distinct_level_3_code_count": version.distinct_level_3_code_count,
        "duplicate_printed_codes": list(version.duplicate_printed_codes),
        "empty_level_3_name_count": version.empty_level_3_name_count,
        "activated": activated,
        "validation_errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    await engine.dispose()

    if activate and not activated:
        return 2
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed DB44/T 2479-2024 appendix A taxonomy")
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="Path to db44t2479-2024-appendix-a.csv",
    )
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Create draft only, do not activate",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main(args.csv_path, activate=not args.no_activate))
    sys.exit(exit_code)
