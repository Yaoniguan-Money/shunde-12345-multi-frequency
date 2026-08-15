from datetime import date

from backend.app.domain.time_normalization import occurrence_date_from_signals
from backend.app.domain.title_tags import parse_title_tags


def test_title_tags_are_explicit_facts_not_department_inference() -> None:
    assert parse_title_tags("（急）【公众号自助】道路积水") == ("急", "公众号自助")
    assert parse_title_tags("（某某部门）道路积水") == ()


def test_occurrence_date_requires_one_explicit_valid_full_date() -> None:
    assert occurrence_date_from_signals(("2025年1月3日夜间",)) == date(2025, 1, 3)
    assert occurrence_date_from_signals(("2025年1月3日22:23:00",)) == date(2025, 1, 3)
    assert occurrence_date_from_signals(("1月3日", "今日", "夜间")) is None
    assert occurrence_date_from_signals(("2025-02-30",)) is None
    assert occurrence_date_from_signals(("2025-01-03", "2025-01-04")) is None
