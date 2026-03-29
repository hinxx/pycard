from __future__ import annotations

from dataclasses import dataclass
import struct


CARD_MAGIC0 = 0xFFFFFFFF
CARD_MAGIC1 = 6969
CARD_MAGIC2 = 6970

CARD_DEFAULT_PIN = (0xFF, 0xFF, 0xFF)

CARD_RECORD_OFFSET = 64
CARD_RECORD_SIZE = 16
ADMIN_CARD_ID = 1
USER_CARD_ID = 9999
DEFAULT_TOP_UP = 2


@dataclass(slots=True)
class Info:
    force: bool = False
    present: bool = False
    change: bool = False
    error: bool = False
    unlocked: bool = False
    error_str: str = ""
    pin_error_counter: int = 0xFF
    magic: int = CARD_MAGIC0
    id: int = USER_CARD_ID
    total: int = 0
    value: int = 0
    reader_present: bool = False
    reader_name: str = ""


@dataclass(frozen=True, slots=True)
class CardRecord:
    magic: int
    id: int
    total: int
    value: int


def decode_card_record(payload: bytes) -> CardRecord:
    if len(payload) != CARD_RECORD_SIZE:
        raise ValueError(f"expected {CARD_RECORD_SIZE} bytes, got {len(payload)}")
    magic, card_id, total, value = struct.unpack("<IIII", payload)
    return CardRecord(magic=magic, id=card_id, total=total, value=value)


def encode_card_record(record: CardRecord) -> bytes:
    return struct.pack("<IIII", record.magic, record.id, record.total, record.value)


def calculate_new_total(current_value: int, requested_delta: str) -> int:
    try:
        delta = int(requested_delta)
    except (TypeError, ValueError):
        return 0
    if delta <= 0:
        return 0
    return current_value + delta
