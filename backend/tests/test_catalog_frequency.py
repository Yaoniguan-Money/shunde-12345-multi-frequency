from datetime import date
from uuid import uuid4

import pytest

from backend.app.domain.catalog import (
    is_high_frequency_work_order_count,
    rolling_window_max_distinct_work_orders,
)
from backend.app.domain.work_orders import canonical_root_work_order_number


def test_child_work_orders_share_a_stable_root_identity() -> None:
    assert canonical_root_work_order_number("250113166160109-01") == "250113166160109"
    assert canonical_root_work_order_number("250305018200109-03") == "250305018200109"
    assert canonical_root_work_order_number("ordinary-number-AB") == "ordinary-number-AB"


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


def test_child_work_orders_contribute_one_root_to_frequency() -> None:
    root = canonical_root_work_order_number("250113166160109-01")
    records = [
        (root, date(2025, 3, 31)),
        (canonical_root_work_order_number("250113166160109-02"), date(2025, 3, 31)),
    ]

    assert rolling_window_max_distinct_work_orders(records) == 1
    assert not is_high_frequency_work_order_count(1)


def test_three_independent_roots_reported_on_same_day_are_high_frequency() -> None:
    records = [(root, date(2025, 3, 31)) for root in ("A", "B", "C")]

    assert rolling_window_max_distinct_work_orders(records) == 3
    assert is_high_frequency_work_order_count(3)


def test_long_running_repeat_complaints_are_multi_frequency_but_not_high_frequency() -> None:
    records = [
        ("A", date(2025, 2, 11)),
        ("B", date(2025, 3, 27)),
        ("C", date(2025, 3, 31)),
    ]

    assert rolling_window_max_distinct_work_orders(records) == 1
    assert not is_high_frequency_work_order_count(1)


def test_event_occurrence_dates_cannot_replace_missing_report_dates() -> None:
    # The caller supplies only WorkOrder.reported_at dates.  Historical dates
    # in the event body are deliberately not accepted by this projection.
    records = [("A", date(2025, 3, 31)), ("B", date(2025, 3, 31)), ("C", date(2025, 3, 31))]

    assert rolling_window_max_distinct_work_orders(records) == 3


def test_window_days_must_be_positive() -> None:
    with pytest.raises(ValueError, match="window_days"):
        rolling_window_max_distinct_work_orders([], window_days=0)
