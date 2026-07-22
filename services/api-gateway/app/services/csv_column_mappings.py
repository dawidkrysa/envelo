DEFAULT_COLUMN_MAPPING = {
    "date": "transaction_date",
    "amount": "amount",
    "description": "description",
    "payee": "payee",
}

COLUMN_MAPPINGS = {"default": DEFAULT_COLUMN_MAPPING}


def get_column_mapping(bank: str | None = None) -> dict[str, str]:
    return COLUMN_MAPPINGS.get(bank or "default", DEFAULT_COLUMN_MAPPING)
