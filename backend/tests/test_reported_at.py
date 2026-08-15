from datetime import datetime

from backend.app.domain.imports import ImportRow
from backend.app.domain.reported_at import (
    PARSER_VERSION,
    ReportedAtResolver,
    ReportedAtSource,
)
from backend.app.domain.wro_number_parser import ShundeWroNumberDateParser


def _make_row(
    *,
    external_work_order_number: str | None = None,
    raw_fields: dict[str, object] | None = None,
) -> ImportRow:
    return ImportRow(
        source_row_number=1,
        external_work_order_number=external_work_order_number,
        title=None,
        content="test content",
        raw_fields=raw_fields or {},
        raw_sha256="a" * 64,
    )


class TestReportedAtResolver:
    def setup_method(self) -> None:
        self.resolver = ReportedAtResolver(ShundeWroNumberDateParser())

    def test_field_mapping_takes_priority(self) -> None:
        row = _make_row(
            external_work_order_number="250331170700109-01",
            raw_fields={"reported_at": "2025-03-31 10:00:00"},
        )
        result = self.resolver.resolve(row)
        assert result.reported_at == datetime(2025, 3, 31, 10, 0, 0)
        assert result.source == ReportedAtSource.FIELD_MAPPING
        assert result.parser_version == PARSER_VERSION
        assert result.is_resolved

    def test_field_mapping_iso_date(self) -> None:
        row = _make_row(
            raw_fields={"reported_at": "2025-03-31"},
        )
        result = self.resolver.resolve(row)
        assert result.reported_at == datetime(2025, 3, 31)
        assert result.source == ReportedAtSource.FIELD_MAPPING

    def test_field_mapping_datetime_object(self) -> None:
        row = _make_row(
            raw_fields={"reported_at": "2025-03-31 14:30"},
        )
        result = self.resolver.resolve(row)
        assert result.reported_at == datetime(2025, 3, 31, 14, 30)
        assert result.source == ReportedAtSource.FIELD_MAPPING

    def test_wro_number_fallback(self) -> None:
        row = _make_row(
            external_work_order_number="250331170700109-01",
        )
        result = self.resolver.resolve(row)
        assert result.reported_at == datetime(2025, 3, 31)
        assert result.source == ReportedAtSource.WORK_ORDER_NUMBER

    def test_unknown_when_no_date_available(self) -> None:
        row = _make_row()
        result = self.resolver.resolve(row)
        assert result.reported_at is None
        assert result.source == ReportedAtSource.UNKNOWN
        assert not result.is_resolved

    def test_invalid_field_value_falls_back_to_wro(self) -> None:
        row = _make_row(
            external_work_order_number="250331170700109-01",
            raw_fields={"reported_at": "not a date"},
        )
        result = self.resolver.resolve(row)
        assert result.reported_at == datetime(2025, 3, 31)
        assert result.source == ReportedAtSource.WORK_ORDER_NUMBER

    def test_empty_wro_number_returns_unknown(self) -> None:
        row = _make_row(external_work_order_number="")
        result = self.resolver.resolve(row)
        assert result.reported_at is None
        assert result.source == ReportedAtSource.UNKNOWN

    def test_none_wro_number_returns_unknown(self) -> None:
        row = _make_row(external_work_order_number=None)
        result = self.resolver.resolve(row)
        assert result.reported_at is None
        assert result.source == ReportedAtSource.UNKNOWN

    def test_malformed_wro_number_returns_unknown(self) -> None:
        row = _make_row(external_work_order_number="ABCDEF")
        result = self.resolver.resolve(row)
        assert result.reported_at is None
        assert result.source == ReportedAtSource.UNKNOWN

    def test_cross_year_boundary(self) -> None:
        row = _make_row(external_work_order_number="991231170700109-01")
        result = self.resolver.resolve(row)
        assert result.reported_at == datetime(2099, 12, 31)

    def test_short_wro_number_returns_unknown(self) -> None:
        row = _make_row(external_work_order_number="2503")
        result = self.resolver.resolve(row)
        assert result.reported_at is None
        assert result.source == ReportedAtSource.UNKNOWN

    def test_invalid_month_in_wro_returns_unknown(self) -> None:
        row = _make_row(external_work_order_number="251331170700109-01")
        result = self.resolver.resolve(row)
        assert result.reported_at is None
        assert result.source == ReportedAtSource.UNKNOWN

    def test_invalid_day_in_wro_returns_unknown(self) -> None:
        row = _make_row(external_work_order_number="250232170700109-01")
        result = self.resolver.resolve(row)
        assert result.reported_at is None
        assert result.source == ReportedAtSource.UNKNOWN


class TestShundeWroNumberDateParser:
    def test_valid_number(self) -> None:
        parser = ShundeWroNumberDateParser()
        assert parser.parse("250331170700109-01") == datetime(2025, 3, 31)

    def test_valid_number_no_suffix(self) -> None:
        parser = ShundeWroNumberDateParser()
        assert parser.parse("250331") == datetime(2025, 3, 31)

    def test_none_input(self) -> None:
        parser = ShundeWroNumberDateParser()
        assert parser.parse(None) is None

    def test_empty_input(self) -> None:
        parser = ShundeWroNumberDateParser()
        assert parser.parse("") is None

    def test_malformed_input(self) -> None:
        parser = ShundeWroNumberDateParser()
        assert parser.parse("invalid") is None

    def test_year_2000(self) -> None:
        parser = ShundeWroNumberDateParser()
        assert parser.parse("000101") == datetime(2000, 1, 1)

    def test_year_2099(self) -> None:
        parser = ShundeWroNumberDateParser()
        assert parser.parse("991231") == datetime(2099, 12, 31)
