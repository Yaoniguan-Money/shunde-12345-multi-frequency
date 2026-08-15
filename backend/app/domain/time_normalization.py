"""Conservative normalization of explicit event business dates."""

import re
from datetime import date

_FULL_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(\d{4})年(\d{1,2})月(\d{1,2})日"),
    re.compile(r"(?<!\d)(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?!\d)"),
)


def occurrence_date_from_signals(signals: tuple[str, ...]) -> date | None:
    """Return only a valid full date; never infer a year or use import time."""
    resolved: set[date] = set()
    for signal in signals:
        for pattern in _FULL_DATE_PATTERNS:
            match = pattern.search(signal)
            if match is None:
                continue
            try:
                resolved.add(date(*(int(value) for value in match.groups())))
            except ValueError:
                continue
    return next(iter(resolved)) if len(resolved) == 1 else None
