import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.services.parsed_transaction import ParsedTransaction

DATE_FORMAT = "%Y-%m-%d"


class StatementParseError(Exception):
    def __init__(self, message, row_number=None):
        super().__init__(message)
        self.row_number = row_number


def parse_csv(content: bytes, mapping: dict[str, str]) -> list[ParsedTransaction]:

    result: list[ParsedTransaction] = []

    with io.StringIO(content.decode("utf-8-sig")) as csvfile:
        reader = csv.DictReader(csvfile)

        required_fields = {"transaction_date", "amount"}
        reader.fieldnames = [h.strip().lower() for h in reader.fieldnames or []]
        found_fields = {h: mapping.get(h) for h in reader.fieldnames}
        missing = required_fields - set(found_fields.values())
        if missing:
            raise StatementParseError(f"Missing required column(s) for: {missing}")

        field_to_column = {v: k for k, v in found_fields.items()}
        description_column = field_to_column.get("description")
        payee_column = field_to_column.get("payee")

        for row_number, row in enumerate(reader, start=2):
            raw_date = (row.get(field_to_column["transaction_date"]) or "").strip()
            raw_amount = (row.get(field_to_column["amount"]) or "").strip()

            if not raw_date:
                raise StatementParseError(
                    "Missing transaction date", row_number=row_number
                )
            if not raw_amount:
                raise StatementParseError("Missing amount", row_number=row_number)

            try:
                transaction_date = datetime.strptime(raw_date, DATE_FORMAT).date()
            except ValueError:
                raise StatementParseError(
                    f"Invalid date '{raw_date}', expected format {DATE_FORMAT}",
                    row_number=row_number,
                )

            try:
                amount = Decimal(raw_amount)
            except InvalidOperation:
                raise StatementParseError(
                    f"Invalid amount '{raw_amount}'", row_number=row_number
                )

            description = (row.get(description_column) or "").strip() or None
            payee = (row.get(payee_column) or "").strip() or None

            result.append(
                ParsedTransaction(
                    transaction_date=transaction_date,
                    amount=amount,
                    description=description,
                    payee=payee,
                )
            )

    if not result:
        raise StatementParseError("CSV file contains no transaction rows")

    return result
