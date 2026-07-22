from enum import Enum


class AccountType(Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    CASH = "cash"


class FileFormat(Enum):
    CSV = "csv"
    MT940 = "mt940"
    OFX = "ofx"


class CategorizationSource(Enum):
    RULE = "rule"
    ML = "ml"
    MANUAL = "manual"


class FileTransferStatus(Enum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"


def get_enum_values(enum_class):
    return [member.value for member in enum_class]
