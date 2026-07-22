from datetime import date
from decimal import Decimal

import pytest
from app.services.csv_column_mappings import get_column_mapping
from app.services.csv_parser import StatementParseError, parse_csv

MAPPING = get_column_mapping()


def test_parse_csv_valid_rows():
    content = (
        b"date,amount,description,payee\n"
        b"2026-01-01,10.00,Coffee,Starbucks\n"
        b"2026-01-02,-5.50,,\n"
    )

    result = parse_csv(content, MAPPING)

    assert len(result) == 2
    assert result[0].transaction_date == date(2026, 1, 1)
    assert result[0].amount == Decimal("10.00")
    assert result[0].description == "Coffee"
    assert result[0].payee == "Starbucks"
    assert result[1].amount == Decimal("-5.50")
    assert result[1].description is None
    assert result[1].payee is None


def test_parse_csv_headers_are_case_and_whitespace_insensitive():
    content = b" Date , Amount \n2026-01-01,10.00\n"

    result = parse_csv(content, MAPPING)

    assert len(result) == 1
    assert result[0].amount == Decimal("10.00")


def test_parse_csv_missing_required_column_raises():
    content = b"date,description\n2026-01-01,Coffee\n"

    with pytest.raises(StatementParseError):
        parse_csv(content, MAPPING)


def test_parse_csv_empty_file_raises():
    content = b""

    with pytest.raises(StatementParseError):
        parse_csv(content, MAPPING)


def test_parse_csv_header_only_raises():
    content = b"date,amount\n"

    with pytest.raises(StatementParseError):
        parse_csv(content, MAPPING)


def test_parse_csv_missing_date_value_raises_with_row_number():
    content = b"date,amount\n,10.00\n"

    with pytest.raises(StatementParseError) as exc_info:
        parse_csv(content, MAPPING)
    assert exc_info.value.row_number == 2


def test_parse_csv_invalid_date_format_raises_with_row_number():
    content = b"date,amount\n01-01-2026,10.00\n"

    with pytest.raises(StatementParseError) as exc_info:
        parse_csv(content, MAPPING)
    assert exc_info.value.row_number == 2


def test_parse_csv_invalid_amount_raises_with_row_number():
    content = b"date,amount\n2026-01-01,not-a-number\n"

    with pytest.raises(StatementParseError) as exc_info:
        parse_csv(content, MAPPING)
    assert exc_info.value.row_number == 2


def test_parse_csv_stops_at_first_bad_row():
    content = b"date,amount\n2026-01-01,10.00\n2026-01-02,bad\n"

    with pytest.raises(StatementParseError) as exc_info:
        parse_csv(content, MAPPING)
    assert exc_info.value.row_number == 3
