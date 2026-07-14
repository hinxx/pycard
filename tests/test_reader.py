from __future__ import annotations

import pytest

from pycard.models import ADMIN_CARD_ID, CARD_DEFAULT_PIN, CARD_MAGIC0, CARD_MAGIC2, CARD_RECORD_OFFSET, USER_CARD_ID, CardRecord, Info, encode_card_record
from pycard.pcsc import PinVerificationError
from pycard.reader import ReaderService


class RecordingTransport:
    def __init__(self, *, reject_pin: bool = False, readback: bytes | None = None) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.reject_pin = reject_pin
        self.readback = readback
        self.written_payload = b""

    def present_pin(self, pin: tuple[int, int, int]) -> None:
        self.calls.append(("present_pin", pin))
        if self.reject_pin:
            raise PinVerificationError(0x03)

    def change_pin(self, pin: tuple[int, int, int]) -> None:
        self.calls.append(("change_pin", pin))

    def write_memory_card(self, address: int, payload: bytes) -> None:
        self.written_payload = payload
        self.calls.append(("write_memory_card", address, payload))

    def read_memory_card(self, address: int, length: int) -> bytes:
        self.calls.append(("read_memory_card", address, length))
        return self.readback if self.readback is not None else self.written_payload


@pytest.mark.parametrize("card_id", [USER_CARD_ID, ADMIN_CARD_ID])
def test_personalize_blank_card_changes_pin_and_writes_selected_type(card_id: int) -> None:
    transport = RecordingTransport()
    personalized_pin = (0x11, 0x22, 0x33)
    service = ReaderService(transport, personalized_pin)  # type: ignore[arg-type]
    info = Info(magic=CARD_MAGIC0)
    expected_payload = encode_card_record(
        CardRecord(magic=CARD_MAGIC2, id=card_id, total=0, value=0)
    )

    assert service.personalize(info, card_id)

    assert transport.calls == [
        ("present_pin", CARD_DEFAULT_PIN),
        ("change_pin", personalized_pin),
        ("write_memory_card", CARD_RECORD_OFFSET, expected_payload),
        ("read_memory_card", CARD_RECORD_OFFSET, len(expected_payload)),
    ]
    assert info.unlocked
    assert not info.personalized_during_unlock
    assert (info.magic, info.id, info.total, info.value) == (CARD_MAGIC2, card_id, 0, 0)


def test_uninitialized_card_does_not_change_pin_after_failed_verification() -> None:
    transport = RecordingTransport(reject_pin=True)
    service = ReaderService(transport, (0x11, 0x22, 0x33))  # type: ignore[arg-type]
    info = Info(magic=CARD_MAGIC0)

    assert not service.personalize(info, USER_CARD_ID)

    assert transport.calls == [("present_pin", CARD_DEFAULT_PIN)]
    assert not info.unlocked
    assert info.error
    assert info.pin_verification_failed
    assert info.pin_error_counter == 0x03


def test_uninitialized_card_reports_partial_failure_when_personalization_readback_differs() -> None:
    transport = RecordingTransport(readback=b"\xFF" * 16)
    service = ReaderService(transport, (0x11, 0x22, 0x33))  # type: ignore[arg-type]
    info = Info(magic=CARD_MAGIC0)

    assert not service.personalize(info, USER_CARD_ID)

    assert "PIN was changed" in info.error_str
    assert not info.unlocked
    assert not info.personalized_during_unlock


def test_blank_card_cannot_be_unlocked_as_an_ordinary_update() -> None:
    transport = RecordingTransport()
    service = ReaderService(transport, (0x11, 0x22, 0x33))  # type: ignore[arg-type]
    info = Info(magic=CARD_MAGIC0)

    assert not service.unlock(info)

    assert transport.calls == []
    assert "must be personalized" in info.error_str


def test_personalization_requires_non_default_configured_pin() -> None:
    transport = RecordingTransport()
    service = ReaderService(transport, CARD_DEFAULT_PIN)  # type: ignore[arg-type]
    info = Info(magic=CARD_MAGIC0)

    assert not service.personalize(info, USER_CARD_ID)

    assert transport.calls == []
    assert "non-default" in info.error_str


def test_card_removal_clears_all_cached_card_state() -> None:
    class EmptyTransport:
        reader_name = "test reader"

        def is_reader_present(self) -> bool:
            return True

        def is_card_present(self) -> bool:
            return False

    service = ReaderService(EmptyTransport(), (0x11, 0x22, 0x33))  # type: ignore[arg-type]
    info = Info(
        present=True,
        unlocked=True,
        pin_error_counter=0x03,
        magic=CARD_MAGIC2,
        id=ADMIN_CARD_ID,
        total=40,
        value=40,
    )

    assert not service.detect(info)

    assert not info.present
    assert not info.unlocked
    assert info.pin_error_counter == 0xFF
    assert (info.magic, info.id, info.total, info.value) == (CARD_MAGIC0, USER_CARD_ID, 0, 0)
