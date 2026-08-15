import re
from datetime import datetime

from backend.app.domain.reported_at import WorkOrderNumberDateParser

_WRO_PATTERN = re.compile(r"^(\d{2})(\d{2})(\d{2})")


class ShundeWroNumberDateParser(WorkOrderNumberDateParser):
    def parse(self, work_order_number: str | None) -> datetime | None:
        if not work_order_number:
            return None
        match = _WRO_PATTERN.match(work_order_number)
        if match is None:
            return None
        yy, mm, dd = (int(g) for g in match.groups())
        year = 2000 + yy
        if not (1 <= mm <= 12 and 1 <= dd <= 31):
            return None
        try:
            return datetime(year, mm, dd)
        except ValueError:
            return None
