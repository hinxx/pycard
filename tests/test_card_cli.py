from __future__ import annotations

import pytest

import card_cli
from card_cli import PinSelection, apply_pin_change, available_attempts, format_hex_dump, initialize_wallet_record, parse_pin, read_card_snapshot
from pycard.models import CARD_DEFAULT_PIN, CARD_MAGIC2, CARD_RECORD_OFFSET, CARD_RECORD_SIZE, USER_CARD_ID, CardRecord, encode_card_record
from pycard.pcsc import CardCommunicationError, CardResetError


class RecordingTransport:
    def __init__(self, readback: bytes | None = None) -> None:
        self.readback = readback
        self.calls: list[tuple[object, ...]] = []

    def write_memory_card(self, address: int, payload: bytes) -> None:
        self.calls.append(("write", address, payload))

    def read_memory_card(self, address: int, length: int) -> bytes:
        self.calls.append(("read", address, length))
        return self.readback if self.readback is not None else b"\xFF" * length

    def change_pin(self, pin: tuple[int, int, int]) -> None:
        self.calls.append(("change_pin", pin))

    def select_memory_card(self) -> None:
        self.calls.append(("select",))

    def get_error_count(self) -> int:
        self.calls.append(("counter",))
        return 0x07

    def present_pin(self, pin: tuple[int, int, int]) -> None:
        self.calls.append(("present_pin", pin))

    def disconnect_card(self) -> None:
        self.calls.append(("disconnect",))


def test_parse_pin_accepts_three_hex_bytes() -> None:
    assert parse_pin("11 a2 FF") == (0x11, 0xA2, 0xFF)


@pytest.mark.parametrize("value", ["", "11 22", "11 22 333", "GG 22 33", "0x11 22 33"])
def test_parse_pin_rejects_invalid_input(value: str) -> None:
    with pytest.raises(ValueError):
        parse_pin(value)


def test_format_hex_dump_includes_record_address_and_ascii() -> None:
    dump = format_hex_dump(b"AB\x00\xFF", 0x40)

    assert dump == "0040  41 42 00 FF                                      |AB..|"


@pytest.mark.parametrize(
    ("counter", "attempts"),
    [(0x07, 3), (0x03, 2), (0x01, 1), (0x00, 0), (0x06, 2)],
)
def test_available_attempts_counts_free_counter_bits(counter: int, attempts: int) -> None:
    assert available_attempts(counter) == attempts


def test_personalized_pin_change_preserves_wallet_record() -> None:
    transport = RecordingTransport()

    assert not apply_pin_change(transport, (0x11, 0x22, 0x33))  # type: ignore[arg-type]

    assert transport.calls == [("change_pin", (0x11, 0x22, 0x33))]


def test_default_pin_erases_and_verifies_wallet_record_before_pin_change() -> None:
    transport = RecordingTransport()
    erased_record = b"\xFF" * CARD_RECORD_SIZE

    assert apply_pin_change(transport, CARD_DEFAULT_PIN)  # type: ignore[arg-type]

    assert transport.calls == [
        ("write", CARD_RECORD_OFFSET, erased_record),
        ("read", CARD_RECORD_OFFSET, CARD_RECORD_SIZE),
        ("change_pin", CARD_DEFAULT_PIN),
    ]


def test_default_pin_is_not_changed_when_erase_verification_fails() -> None:
    transport = RecordingTransport(readback=b"\x00" * CARD_RECORD_SIZE)

    with pytest.raises(CardCommunicationError, match="PIN was not changed"):
        apply_pin_change(transport, CARD_DEFAULT_PIN)  # type: ignore[arg-type]

    assert all(call[0] != "change_pin" for call in transport.calls)


def test_initialize_wallet_record_writes_user_identity_and_zero_values() -> None:
    expected = encode_card_record(
        CardRecord(magic=CARD_MAGIC2, id=USER_CARD_ID, total=0, value=0)
    )
    transport = RecordingTransport(readback=expected)

    assert initialize_wallet_record(transport) == expected  # type: ignore[arg-type]

    assert transport.calls == [
        ("write", CARD_RECORD_OFFSET, expected),
        ("read", CARD_RECORD_OFFSET, CARD_RECORD_SIZE),
    ]


def test_initialize_wallet_record_rejects_failed_readback() -> None:
    transport = RecordingTransport(readback=b"\xFF" * CARD_RECORD_SIZE)

    with pytest.raises(CardCommunicationError, match="initialization verification failed"):
        initialize_wallet_record(transport)  # type: ignore[arg-type]


def test_presenting_config_pin_does_not_offer_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    record = encode_card_record(
        CardRecord(magic=CARD_MAGIC2, id=USER_CARD_ID, total=0, value=0)
    )
    transport = RecordingTransport(readback=record)
    selections = iter(
        [
            PinSelection((0x11, 0x22, 0x33), "config", "config PIN"),
            None,
        ]
    )
    initialization_calls: list[object] = []
    monkeypatch.setattr(card_cli, "prompt_for_pin", lambda *_args, **_kwargs: next(selections))
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")
    monkeypatch.setattr(
        card_cli,
        "prompt_to_initialize_wallet",
        lambda value: initialization_calls.append(value),
    )

    assert card_cli.inspect_and_verify(transport, None) == 0  # type: ignore[arg-type]

    assert initialization_calls == []


def test_changing_pin_to_config_offers_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = RecordingTransport()
    initialization_calls: list[object] = []
    monkeypatch.setattr(
        card_cli,
        "prompt_for_pin",
        lambda *_args, **_kwargs: PinSelection((0x11, 0x22, 0x33), "config", "config PIN"),
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")
    monkeypatch.setattr(
        card_cli,
        "prompt_to_initialize_wallet",
        lambda value: initialization_calls.append(value),
    )

    assert card_cli.prompt_and_change_pin(transport, None) == 0  # type: ignore[arg-type]

    assert initialization_calls == [transport]


def test_wait_for_card_retries_transient_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class RetryingTransport:
        reader_name = "ACS test reader"

        def __init__(self) -> None:
            self.card_checks = 0
            self.disconnects = 0

        def is_reader_present(self) -> bool:
            return True

        def is_card_present(self) -> bool:
            self.card_checks += 1
            if self.card_checks == 1:
                raise CardCommunicationError("protocol mismatch")
            return True

        def disconnect_card(self) -> None:
            self.disconnects += 1

    transport = RetryingTransport()
    monkeypatch.setattr(card_cli.time, "sleep", lambda _seconds: None)

    card_cli.wait_for_card(transport, 0.5)  # type: ignore[arg-type]

    assert transport.card_checks == 2
    assert transport.disconnects == 1


def test_initial_snapshot_reconnects_after_invalid_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RetryingSnapshotTransport(RecordingTransport):
        reader_name = "ACS test reader"

        def __init__(self) -> None:
            super().__init__(readback=b"\x12" * CARD_RECORD_SIZE)
            self.counter_reads = 0

        def get_error_count(self) -> int:
            self.counter_reads += 1
            self.calls.append(("counter",))
            if self.counter_reads == 1:
                raise CardCommunicationError("invalid PIN counter FF")
            return 0x07

        def is_reader_present(self) -> bool:
            return True

        def is_card_present(self) -> bool:
            return True

    transport = RetryingSnapshotTransport()
    monkeypatch.setattr(card_cli.time, "sleep", lambda _seconds: None)

    counter, payload = read_card_snapshot(transport, 0.5)  # type: ignore[arg-type]

    assert counter == 0x07
    assert payload == b"\x12" * CARD_RECORD_SIZE
    assert transport.counter_reads == 2
    assert ("disconnect",) in transport.calls


def test_pin_presentation_reset_requires_reconnect_and_reconfirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ResetOnceTransport(RecordingTransport):
        def __init__(self, readback: bytes) -> None:
            super().__init__(readback=readback)
            self.present_calls = 0

        def is_card_present(self) -> bool:
            self.calls.append(("is_card_present",))
            return True

        def present_pin(self, pin: tuple[int, int, int]) -> None:
            self.present_calls += 1
            self.calls.append(("present_pin", pin))
            if self.present_calls == 1:
                raise CardResetError("card reset")

    record = encode_card_record(
        CardRecord(magic=CARD_MAGIC2, id=USER_CARD_ID, total=0, value=0)
    )
    transport = ResetOnceTransport(record)
    selections = iter(
        [
            PinSelection(CARD_DEFAULT_PIN, "default", "default PIN"),
            None,
        ]
    )
    confirmations = iter(["y", "y"])
    monkeypatch.setattr(card_cli, "prompt_for_pin", lambda *_args, **_kwargs: next(selections))
    monkeypatch.setattr("builtins.input", lambda _prompt: next(confirmations))

    assert card_cli.inspect_and_verify(transport, None) == 0  # type: ignore[arg-type]

    assert transport.present_calls == 2
    assert ("disconnect",) in transport.calls
    assert ("is_card_present",) in transport.calls
