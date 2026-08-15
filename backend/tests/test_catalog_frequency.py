from datetime import date
from uuid import uuid4

import pytest

from backend.app.domain.catalog import (
    is_high_frequency_work_order_count,
    rolling_window_max_distinct_work_orders,
)


def test_three_distinct_work_orders_in_three_calendar_days_is_high_frequency() -> None:
    records = [
        (uuid4(), date(2025, 1, 1)),
        (uuid4(), date(2025, 1, 2)),
        (uuid4(), date(2025, 1, 3)),
    ]

    assert rolling_window_max_distinct_work_orders(records) == 3
    assert is_high_frequency_work_order_count(3)


def test_events_outside_three_day_window_are_not_high_frequency() -> None:
    records = [
        (uuid4(), date(2025, 1, 1)),
        (uuid4(), date(2025, 1, 4)),
        (uuid4(), date(2025, 1, 5)),
    ]

    assert rolling_window_max_distinct_work_orders(records) == 2
    assert not is_high_frequency_work_order_count(2)


def test_same_work_order_is_counted_once_and_undated_records_are_excluded() -> None:
    work_order_id = uuid4()
    records = [
        (work_order_id, date(2025, 1, 1)),
        (work_order_id, date(2025, 1, 2)),
        (uuid4(), date(2025, 1, 3)),
        (uuid4(), None),
    ]

    assert rolling_window_max_distinct_work_orders(records) == 2


def test_window_days_must_be_positive() -> None:
    with pytest.raises(ValueError, match="window_days"):
        rolling_window_max_distinct_work_orders([], window_days=0)
